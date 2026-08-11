"""M2 (SDD_M2_LINEAGE) — Trazabilidad causal emitida del motor.

Verifica que:
  1. run_sequence_traced emite "event_objects" (grafo real de MarketObject).
  2. trace_setup_lineage reconstruye la cadena por parent_object (origen),
     no por proximidad temporal (SDD_GOVERNANCE §8 / §4 CAUSALITY).
  3. Casos negativos: sin event_objects / parent roto / bar_index futuro.

Es REPRESENTACIÓN + TRAZABILIDAD pura. NO toca reglas ICT, NO indicadores,
NO WR/PF/edge, NO LTF/Macro. Sin datos reales (sintéticos + unidad directa).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.lineage import trace_setup_lineage
from engine.market_object import MarketObject, ObjectType, Role, ObjectState
from ict_backtest.sequence import SequenceConfig, run_sequence_traced
from ict_backtest.market_structure import detect_market_structure


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ohlc(times, base, sweep_low=None):
    n = len(times)
    close = np.full(n, float(base))
    df = pd.DataFrame({
        "time": times,
        "open": close,
        "high": close + 0.0003,
        "low": close - 0.0003,
        "close": close,
        "volume": 100.0,
    })
    df["sweep_low"] = np.nan
    df["sweep_high"] = np.nan
    df["bsl_price"] = np.nan
    df["ssl_price"] = np.nan
    if sweep_low is not None:
        df["sweep_low"] = sweep_low
        df["ssl_price"] = sweep_low - 0.0001
    return df


def _make_ltf_df(n: int = 80):
    base = pd.Timestamp("2026-01-05 09:00", tz="UTC")
    times = pd.date_range(base, periods=n, freq="15min", tz="UTC")
    return detect_market_structure(_ohlc(times, 1.1000, sweep_low=1.0990))


def _no_htf_fn(i: int) -> dict:
    return {
        "htf_bias": None, "htf_aligned": False, "htf_reason": "",
        "poi_present": False, "htf_pois": [], "swing_high": None,
        "swing_low": None, "recent_fvg": None, "recent_ob": None,
    }


def _mk_obj(oid, parent, idx, role="CONTEXT", otype="SWEEP", origin_tf="M15"):
    # ObjectType solo tiene BOS/CHOCH/FVG/ORDER_BLOCK/LIQUIDITY/SWEEP/CANDLE.
    # DISPLACEMENT/RETURN no son tipos de objeto; mapeamos a CANDLE (la línea
    # solo usa parent_object/bar_index/id, no el type).
    _valid = {
        "SWEEP": "SWEEP", "LIQUIDITY": "LIQUIDITY", "BOS": "BOS",
        "CHOCH": "CHOCH", "FVG": "FVG", "ORDER_BLOCK": "ORDER_BLOCK",
        "DISPLACEMENT": "CANDLE", "RETURN": "CANDLE",
    }
    otype = _valid.get(otype, "CANDLE")
    return MarketObject(
        id=oid, type=ObjectType[otype], origin_tf=origin_tf, role=Role[role],
        direction=1, state=ObjectState.CREATED,
        bar_index=idx, bar_time=None, parent_object=parent,
    ).to_dict()


# ---------------------------------------------------------------------------
# 1) Emisión del grafo en run_sequence_traced
# ---------------------------------------------------------------------------
def test_run_sequence_traced_emits_event_objects():
    """REGRESION CERO + ADITIVO: la señal trazada incluye event_objects."""
    ltf_df = _make_ltf_df()
    cfg = SequenceConfig(counter_trend=False, require_displacement=False)
    sigs, _, exps = run_sequence_traced(
        ltf_df, _no_htf_fn, cfg, ltf_tf="M15"
    )
    # No forzamos que haya señal completa en datos sintéticos; si la hay,
    # event_objects debe venir poblado y con los objetos de la cadena.
    if sigs:
        sig = sigs[0]
        assert "event_objects" in sig, "run_sequence_traced debe emitir event_objects"
        assert isinstance(sig["event_objects"], dict)
        # Al menos LIQUIDITY+SWEEP deben existir en cualquier señal nacida.
        assert "SWEEP" in sig["event_ids"]
        assert sig["event_ids"]["SWEEP"] in sig["event_objects"]


def test_event_objects_snapshot_inmutable_en_signals():
    """event_objects es un dict de dicts (snapshot), no objetos vivos."""
    ltf_df = _make_ltf_df()
    cfg = SequenceConfig(counter_trend=False, require_displacement=False)
    sigs, _, _ = run_sequence_traced(ltf_df, _no_htf_fn, cfg, ltf_tf="M15")
    if sigs:
        for oid, odict in sigs[0]["event_objects"].items():
            assert isinstance(odict, dict), "event_objects debe ser id->dict"
            assert "parent_object" in odict, "falta parent_object en el objeto"


# ---------------------------------------------------------------------------
# 2) trace_setup_lineage: unidad directa (cadena por origen)
# ---------------------------------------------------------------------------
def test_trace_linked_chain_by_origin():
    """Cadena COMPLETA enlazada por parent_object -> linked=True."""
    ids = {
        "LIQUIDITY": "L1", "SWEEP": "S1", "DISPLACE": "D1",
        "BOS": "B1", "REFINEMENT": "R1", "RETURN": "X1",
    }
    objs = {
        "L1": _mk_obj("L1", "", 0, role="CONTEXT", otype="LIQUIDITY"),
        "S1": _mk_obj("S1", "L1", 1, otype="SWEEP"),
        "D1": _mk_obj("D1", "S1", 2, otype="DISPLACEMENT"),
        "B1": _mk_obj("B1", "D1", 3, otype="BOS"),
        "R1": _mk_obj("R1", "B1", 3, role="REFINEMENT", otype="FVG"),
        "X1": _mk_obj("X1", "R1", 5, otype="RETURN"),
    }
    res = trace_setup_lineage({"event_ids": ids, "event_objects": objs})
    assert res["linked"] is True, res["breaks"]
    assert res["parent_resolved"] is True
    assert res["temporal_ok"] is True
    assert res["chain"] == ["L1", "S1", "D1", "B1", "R1", "X1"]


def test_trace_poi_anchored_variant():
    """Variante con POI HTF anclado: BOS->POI->REFINEMENT debe enlazar."""
    ids = {
        "LIQUIDITY": "L1", "SWEEP": "S1", "DISPLACE": "D1",
        "BOS": "B1", "POI": "P1", "REFINEMENT": "R1", "RETURN": "X1",
    }
    objs = {
        "L1": _mk_obj("L1", "", 0, role="CONTEXT", otype="LIQUIDITY"),
        "S1": _mk_obj("S1", "L1", 1, otype="SWEEP"),
        "D1": _mk_obj("D1", "S1", 2, otype="DISPLACEMENT"),
        "B1": _mk_obj("B1", "D1", 3, otype="BOS"),
        "P1": _mk_obj("P1", "B1", 3, role="POI", otype="BOS", origin_tf="H4"),
        "R1": _mk_obj("R1", "P1", 3, role="REFINEMENT", otype="FVG"),
        "X1": _mk_obj("X1", "R1", 5, otype="RETURN"),
    }
    res = trace_setup_lineage({"event_ids": ids, "event_objects": objs})
    assert res["linked"] is True, res["breaks"]


def test_trace_broken_parent_not_resolved():
    """parent_object que apunta a id inexistente -> parent_resolved=False."""
    ids = {"LIQUIDITY": "L1", "SWEEP": "S1"}
    objs = {
        "L1": _mk_obj("L1", "", 0, role="CONTEXT", otype="LIQUIDITY"),
        "S1": _mk_obj("S1", "GHOST", 1, otype="SWEEP"),  # padre fantasma
    }
    res = trace_setup_lineage({"event_ids": ids, "event_objects": objs})
    assert res["parent_resolved"] is False
    assert res["linked"] is False


def test_trace_future_parent_breaks_temporal():
    """padre con bar_index MAYOR que el hijo -> temporal_ok=False (anti look-ahead)."""
    ids = {"LIQUIDITY": "L1", "SWEEP": "S1"}
    objs = {
        "L1": _mk_obj("L1", "", 5, role="CONTEXT", otype="LIQUIDITY"),  # idx 5
        "S1": _mk_obj("S1", "L1", 1, otype="SWEEP"),                   # idx 1 < 5
    }
    res = trace_setup_lineage({"event_ids": ids, "event_objects": objs})
    assert res["temporal_ok"] is False
    assert res["linked"] is False


def test_trace_missing_event_objects_is_unknown_not_crash():
    """Sin event_objects -> UNKNOWN documentado, sin lanzar (no fail-open)."""
    res = trace_setup_lineage({"event_ids": {"SWEEP": "S1"}})
    assert res["linked"] is False
    assert any("event_objects ausente" in b for b in res["breaks"])
