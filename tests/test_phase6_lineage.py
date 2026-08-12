"""HYP-002 Fase 6 — TESTS de trazabilidad causal del linaje del setup.

Consumidor puro del motor (run_sequence_traced) + verificador independiente
(research/hypotheses/HYP-002/phase6_verifier.py). Audita IDENTITY / LINK /
CAUSALITY / TEMPORALITY / GRAPH / CYCLES / ONTOLOGIA sobre el grafo real
emitido en signal["event_objects"].

NO usa WR/PF/edge. NO indicadores. Solo representacion + trazabilidad.
Dataset sintetico DETERMINISTA (flags de detectores controlados) para evidencia
reproducible local (el repo no tiene parquet reales en data/; la corrida de
nube de 60k velas queda registrada en PHASE6_AUDIT_CLOSURE.md).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Verificador independiente (archivo con guion en el nombre de carpeta).
_spec = importlib.util.spec_from_file_location(
    "phase6_verifier", str(ROOT / "research/hypotheses/HYP-002/phase6_verifier.py"))
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)

from engine.sequence import SequenceConfig, run_sequence_traced
from engine.poi_anchor import make_htf_poi_fn
from detectors import detect_fvg, detect_liquidity, detect_order_blocks
from detectors.liquidity_context import canonical_sweep, DEFAULT_SWEEP_LOOKBACK
from engine.bos.structure import detect_market_structure


def _build_partial(df):
    d = df.copy().reset_index(drop=True)
    ms = detect_market_structure(d, None)
    frame = ms.frame if hasattr(ms, "frame") else ms
    d["bos_dir"] = frame["bos_dir"].astype(int).values
    d["choch_dir"] = frame["choch_dir"].astype(int).values
    d["trend"] = frame["trend"].values
    d["atr"] = (d["high"] - d["low"]).clip(lower=0).rolling(50).mean().to_numpy()
    f = detect_fvg(d)
    for c in f.columns:
        d[c] = f[c].values
    o = detect_order_blocks(d)
    for c in o.columns:
        d[c] = o[c].values
    liq = detect_liquidity(d)
    d["bsl_price"] = liq["bsl_price"].values
    d["ssl_price"] = liq["ssl_price"].values
    swept = canonical_sweep(d, lookback=DEFAULT_SWEEP_LOOKBACK)
    d["liquidity_sweep_up"] = swept["liquidity_sweep_up"].values
    d["liquidity_sweep_down"] = swept["liquidity_sweep_down"].values
    return d


def _make_htf_df(n):
    htimes = pd.date_range("2026-03-01 00:00", periods=n, freq="15min", tz="UTC")
    hp = np.linspace(1.1000, 1.1085, n)
    hdf = pd.DataFrame({"time": htimes, "open": hp - 0.0003, "high": hp + 0.0005,
                       "low": hp - 0.0005, "close": hp + 0.0002, "volume": 100.0})
    hdf["trend"] = "BULLISH"
    hdf["bos_dir"] = 0
    hdf.loc[8, "bos_dir"] = 1
    for c in ("liquidity_sweep_up", "liquidity_sweep_down", "displacement_bullish",
              "displacement_bearish", "fvg_bullish", "fvg_bearish", "ob_bullish",
              "ob_bearish"):
        hdf[c] = False
    hdf["atr"] = 0.0008
    return hdf


def _make_ltf(n, sweep_i, disp_i, fvg_i, bos_i, ret_i):
    times = pd.date_range("2026-03-01 00:00", periods=n, freq="15min", tz="UTC")
    close = 1.1000 + np.linspace(0, 0.008, n)
    high = close + 0.0004
    low = close - 0.0004
    open_ = close.copy()
    low[sweep_i] = close[sweep_i] - 0.0015
    open_[sweep_i] = close[sweep_i - 1]
    close[sweep_i] = close[sweep_i - 1] - 0.0002
    high[sweep_i] = close[sweep_i - 1]
    close[disp_i] = close[disp_i - 1] + 0.0006
    open_[disp_i] = close[disp_i - 1]
    high[disp_i] = close[disp_i] + 0.0002
    low[disp_i] = open_[disp_i] - 0.0002
    close[disp_i + 1] = close[disp_i] - 0.0001
    open_[disp_i + 1] = close[disp_i]
    high[disp_i + 1] = close[disp_i] + 0.0002
    low[disp_i + 1] = close[disp_i] - 0.0003
    low[fvg_i] = high[disp_i] + 0.0004
    close[fvg_i] = low[fvg_i] + 0.0003
    open_[fvg_i] = low[fvg_i]
    high[fvg_i] = close[fvg_i] + 0.0002
    prev_max = max(high[20:disp_i].max(), high[10:20].max())
    high[bos_i] = prev_max + 0.0005
    close[bos_i] = high[bos_i] - 0.0002
    open_[bos_i] = close[bos_i - 1]
    zh = high[fvg_i]
    zl = low[fvg_i]
    close[ret_i] = (zh + zl) / 2
    high[ret_i] = max(zh, (zh + zl) / 2 + 0.0002)
    low[ret_i] = min(zl, (zh + zl) / 2 - 0.0002)
    open_[ret_i] = (zh + zl) / 2
    df = pd.DataFrame({"time": times, "open": open_, "high": high, "low": low,
                       "close": close, "volume": 100.0})
    ltf = _build_partial(df)
    # PISAR bos_dir del detector: BOS SOLO en bos_i (separa FVG de BOS).
    ltf["bos_dir"] = 0
    ltf.loc[disp_i, "displacement_bullish"] = True
    ltf.loc[bos_i, "bos_dir"] = 1
    return ltf


def _est_htf_fn(htf_df):
    def f(i):
        r = htf_df.iloc[min(i, len(htf_df) - 1)]
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": False, "sweep_down": False,
                "displacement_bullish": False, "displacement_bearish": False,
                "fvg_bullish": False, "fvg_bearish": False,
                "ob_bullish": False, "ob_bearish": False}
    return f


def _run_setup(htf_poi=False):
    n = 250
    ltf = _make_ltf(n, 40, 44, 46, 50, 80)
    hdf = _make_htf_df(n)
    est = _est_htf_fn(hdf)
    if htf_poi:
        fn = make_htf_poi_fn(ltf, {"H4": hdf})
        sigs, _, _ = run_sequence_traced(ltf, est, SequenceConfig(),
                                         htf_poi_fn=fn, ltf_tf="M15", htf="H4")
    else:
        sigs, _, _ = run_sequence_traced(ltf, est, SequenceConfig(),
                                         htf_poi_fn=None, ltf_tf="M15", htf=None)
    return sigs


# ---------------------------------------------------------------------------
# 1) IDENTIDAD + LINAJE COMPLETO (motor emite grafo real)
# ---------------------------------------------------------------------------
def test_setup_complete_lineage_emitted():
    sigs = _run_setup(htf_poi=True)
    assert sigs, "el motor debe emitir al menos 1 setup con el dataset determinista"
    sig = sigs[0]
    ids = sig["event_ids"]
    # Todos los nodos salvo POI deben existir.
    for ph in ("LIQUIDITY", "SWEEP", "DISPLACE", "BOS", "REFINEMENT", "RETURN"):
        assert ids.get(ph), f"falta id de {ph}"
    # POI anclado HTF presente (htf_poi_fn=True, htf=H4).
    assert ids.get("POI"), "POI HTF debe anclarse cuando htf_poi_fn=True y htf=H4"
    agg = V.verify_run(sigs)
    assert agg["identity_ok"] == agg["n_setups"]
    assert agg["link_ok"] == agg["n_setups"]
    assert agg["causality_ok"] == agg["n_setups"]
    assert agg["temporal_ok"] == agg["n_setups"]
    assert agg["graph_ok"] == agg["n_setups"]
    assert agg["cycles_total"] == 0
    assert agg["ontology_ok"] == agg["n_setups"]
    assert V.verdict(agg).startswith("A VALIDADA")


# ---------------------------------------------------------------------------
# 2) POI OPCIONAL / HONESTO (sin ancla HTF => REFINEMENT ancla a BOS)
# ---------------------------------------------------------------------------
def test_setup_without_poi_anchors_refinement_to_bos():
    sigs = _run_setup(htf_poi=False)
    assert sigs
    sig = sigs[0]
    assert not sig["event_ids"].get("POI"), "sin htf_poi_fn el POI NO debe crearse"
    # REFINEMENT debe apuntar a BOS (honesto, sin inventar POI).
    ref = sig["event_objects"][sig["event_ids"]["REFINEMENT"]]
    assert ref["parent_object"] == sig["event_ids"]["BOS"]
    agg = V.verify_run(sigs)
    assert agg["causality_ok"] == agg["n_setups"]


# ---------------------------------------------------------------------------
# 3) ANTI LOOK-AHEAD: padre futuro rechazado (padre idx > hijo idx)
# ---------------------------------------------------------------------------
def test_adversarial_parent_future_rejected():
    eo = {
        "L1": {"type": "LIQUIDITY", "role": "CONTEXT", "origin_tf": "M15", "parent_object": "", "bar_index": 5},
        "S1": {"type": "SWEEP", "role": "CONTEXT", "origin_tf": "M15", "parent_object": "L1", "bar_index": 1},
    }
    sig = {"event_ids": {"LIQUIDITY": "L1", "SWEEP": "S1"}, "event_objects": eo}
    r = V.verify_setup(sig)
    assert r["temporal"] == "PARENT_FUTURE"


# ---------------------------------------------------------------------------
# 4) PADRE FANTASMA: marcado, no crashea
# ---------------------------------------------------------------------------
def test_adversarial_ghost_parent_flagged():
    eo = {
        "L1": {"type": "LIQUIDITY", "role": "CONTEXT", "origin_tf": "M15", "parent_object": "", "bar_index": 0},
        "S1": {"type": "SWEEP", "role": "CONTEXT", "origin_tf": "M15", "parent_object": "GHOST", "bar_index": 1},
    }
    sig = {"event_ids": {"LIQUIDITY": "L1", "SWEEP": "S1"}, "event_objects": eo}
    r = V.verify_setup(sig)  # no debe lanzar
    assert r["link"] == "PARENT_MISSING"


# ---------------------------------------------------------------------------
# 5) PADRE INCORRECTO: dos candidatos, NO por proximidad
# ---------------------------------------------------------------------------
def test_adversarial_wrong_parent_not_chosen_by_proximity():
    eo = {
        "L1": {"type": "LIQUIDITY", "role": "CONTEXT", "origin_tf": "M15", "parent_object": "", "bar_index": 0},
        "S1": {"type": "SWEEP", "role": "CONTEXT", "origin_tf": "M15", "parent_object": "L1", "bar_index": 1},
        "D1": {"type": "DISPLACEMENT", "role": "CONTEXT", "origin_tf": "M15", "parent_object": "S1", "bar_index": 2},
        "B1": {"type": "BOS", "role": "CONTEXT", "origin_tf": "M15", "parent_object": "D1", "bar_index": 3},
        "P1": {"type": "BOS", "role": "POI", "origin_tf": "H4", "parent_object": "B1", "bar_index": 3},
        "R1": {"type": "FVG", "role": "REFINEMENT", "origin_tf": "M15", "parent_object": "P1", "bar_index": 3},
        "X1": {"type": "RETURN", "role": "CONTEXT", "origin_tf": "M15", "parent_object": "B1", "bar_index": 5},
    }
    ids = {"LIQUIDITY": "L1", "SWEEP": "S1", "DISPLACE": "D1", "BOS": "B1",
           "POI": "P1", "REFINEMENT": "R1", "RETURN": "X1"}
    sig = {"event_ids": ids, "event_objects": eo}
    r = V.verify_setup(sig)
    assert r["causality"] == "PARENT_MISMATCH"


# ---------------------------------------------------------------------------
# 6) ONTOLOGIA: POI solo HTF, REFINEMENT en LTF
# ---------------------------------------------------------------------------
def test_ontology_poi_only_htf():
    eo = {
        "P1": {"type": "BOS", "role": "POI", "origin_tf": "M15", "parent_object": "B1", "bar_index": 3},
    }
    sig = {"event_ids": {"POI": "P1"}, "event_objects": eo}
    r = V.verify_setup(sig)
    assert r["ontology"] == "POI_NO_HTF"


# ---------------------------------------------------------------------------
# 7) INVALIDACION: conserva historia (no borra nodos)
# ---------------------------------------------------------------------------
def test_invalidation_conserves_history():
    from engine.expediente import Expediente
    exp = Expediente.open(symbol="X", tf="M15", direction=1, birth_idx=1, birth_time="t")
    exp.advance("LIQUIDITY", 1, "t", event_id="l1")
    exp.advance("SWEEP", 2, "t", event_id="s1", parent_event_id="l1")
    exp.advance("DISPLACE", 3, "t", event_id="d1", parent_event_id="s1")
    exp.invalidate(4, "t", "BOS roto", event_id="inv1", parent_event_id="d1")
    assert exp.outcome == "INVALID"
    # Historia completa preservada (no se borra).
    assert len(exp.phase_events) == 4
    phases = [pe.phase for pe in exp.phase_events]
    assert phases == ["LIQUIDITY", "SWEEP", "DISPLACE", "INVALID"]


# ---------------------------------------------------------------------------
# 8) DOS SETUPS no comparten identidad
# ---------------------------------------------------------------------------
def test_two_setups_distinct_identity():
    sigs = _run_setup(htf_poi=True)
    if len(sigs) < 2:
        pytest.skip("dataset determina 1 setup; cubierto por multiples corridas en nube")
    all_ids = [v for s in sigs for v in s["event_ids"].values() if v]
    assert len(all_ids) == len(set(all_ids))
