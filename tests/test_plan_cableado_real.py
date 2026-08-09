"""RED — Fase 5: el cableado REAL del loop driver debe producir score > 0.

Estos tests FALLAN hoy porque el CALL SITE real (run_backtest) no produce
MarketObjects para los emisores, emit_m15 espera phase_log (que ICTSignal no
trae) y poi_anchor compara bar_index cross-TF. Prueban el CONTRATO real:
  - objs_by_tf real (MarketObject sellados) -> attach_alignment -> score>0
  - emit_m15 infiere desde ICTSignal (entry_at/bos_at)
  - poi_anchor ancla por bar_time entre HTF y LTF
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(".").resolve()))

from ict_backtest.market_object import (
    MarketObject,
    ObjectState,
    ObjectType,
    Role,
)


def _mk(tf, otype, direction, t, role=None, zone=None):
    return MarketObject(
        type=otype,
        origin_tf=tf,
        direction=direction,
        role=role if role is not None else Role.REFINEMENT,
        state=ObjectState.ACTIVE,
        bar_index=0,
        bar_time=t,
        zone_high=zone[1] if zone else 0.0,
        zone_low=zone[0] if zone else 0.0,
    )


def test_emit_m15_desde_ictsignal_real():
    """emit_m15 debe inferir STRUCTURE_OK desde ICTSignal (entry_at presente)."""
    from ict_backtest.plan_emitters import emit_m15
    from ict_backtest.plan_fsm import PlanVerdict

    # ICTSignal real: sin phase_log, trae entry_at/bos_at/direction
    sig = {"entry_at": 10, "bos_at": 5, "direction": 1}
    ev = emit_m15([sig])
    assert ev is not None, "emit_m15 debe emitir desde ICTSignal real"
    assert ev.verdict is PlanVerdict.STRUCTURE_OK

    sig_setup = {"bos_at": 5, "direction": 1}  # sin entry -> setup vivo
    ev2 = emit_m15([sig_setup])
    assert ev2 is not None
    assert ev2.verdict is PlanVerdict.SETUP_LIVE


@pytest.mark.skip(reason="API OBSOLETA (2026-08-07): anchor_objects() fue descartada en el "
                        "rescate POI. engine/poi_anchor.py expone build_htf_structure_index/"
                        "make_htf_poi_fn/poi_present. Reescribir contra la API nueva.")
def test_poi_anchor_por_bartime_cross_tf():
    """poi_anchor debe anclar un FVG M15 a un BOS H4 por bar_time (no bar_index)."""
    from engine.poi_anchor import anchor_objects

    t_htf = datetime(2024, 1, 1, 0, 0)
    t_ltf = datetime(2024, 1, 1, 4, 0)  # despues del HTF, mismo dia
    h4 = [_mk("H4", ObjectType.BOS, 1, t_htf, role=Role.CONTEXT, zone=(1.10, 1.09))]
    m15 = [_mk("M15", ObjectType.FVG, 1, t_ltf, zone=(1.095, 1.092))]
    out = anchor_objects(m15, {"H4": h4})
    assert out[0].meta.get("anchored") is True, "debe anclar por bar_time cross-TF"


def test_attach_alignment_score_positivo_con_objetos_reales():
    """attach_alignment con objs_by_tf reales (no dicts) debe dar score > 0."""
    from ict_backtest.plan_attach import attach_alignment

    base = datetime(2024, 1, 1, 0, 0)
    objs_by_tf = {
        "D1": [_mk("D1", ObjectType.BOS, 1, base, role=Role.CONTEXT)],
        "H4": [_mk("H4", ObjectType.BOS, 1, base, role=Role.CONTEXT)],
        "H1": [_mk("H1", ObjectType.ORDER_BLOCK, 1, base, role=Role.POI)],
        "M15": [_mk("M15", ObjectType.FVG, 1, base + timedelta(minutes=15),
                    zone=(1.0900, 1.0950))],
        "M5": [_mk("M5", ObjectType.BOS, 1, base + timedelta(minutes=5))],
        "M1": [_mk("M1", ObjectType.CHOCH, 1, base + timedelta(minutes=1))],
    }
    sig = {"direction": 1, "time": base + timedelta(minutes=15), "entry_at": 15}
    swing = (1.1000, 1.0800)
    out = attach_alignment(sig, objs_by_tf, swing=swing)
    rep = out["alignment"]
    assert rep["score"] > 0, f"score debe ser > 0 con objetos reales, fue {rep['score']}"
    assert rep["d1"] and rep["h4"] and rep["h1"] and rep["m15"], (
        f"capas base deben marcar, rep={rep}")
