"""RED — plan_driver: score_plan mide alineacion multi-TF (NO filtra).

El plan es HERRAMIENTA DE ANALISIS, no gate. score_plan adjunta un
alignment_score + desglose por capa a cada senal. M5/M1 son BONUS
(+0.5 c/u), nunca matan la operacion. Test FALLA hasta implementar
score_plan en ict_backtest/plan_driver.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

from ict_backtest.market_object import (
    MarketObject,
    ObjectState,
    ObjectType,
    Role,
)
from ict_backtest.plan_emitters import emit_d1, emit_h4, emit_h1, emit_m15


def _obj(t, d, tf, role=Role.REFINEMENT):
    return MarketObject(type=t, direction=d, origin_tf=tf, role=role, state=ObjectState.ACTIVE)


def _signal(phase_log):
    return {"phase_log": phase_log, "direction": 1}


def test_score_plan_suma_capas_base():
    from ict_backtest.plan_driver import score_plan

    sig = _signal(["SWEEP_DONE", "DISPLACE_DONE", "BOS_DONE", "ENTRY"])
    rep = score_plan(
        sig,
        d1_objs=[_obj(ObjectType.LIQUIDITY, 1, "D1", Role.CONTEXT)],
        h4_objs=[_obj(ObjectType.BOS, 1, "H4")],
        h1_objs=[_obj(ObjectType.ORDER_BLOCK, 1, "H1", Role.POI)],
        m15_signal=sig,
        m5_confirm={"direction": 1, "confirmed": True},
        m1_trigger={"direction": 1, "confirmed": True},
    )
    # D1+H4+H1+M15 = 4, M5+M1 bonus = +1 -> 5.0
    assert rep.score == 5.0
    assert rep.d1 and rep.h4 and rep.h1 and rep.m15
    assert rep.m5 and rep.m1


def test_score_plan_sin_m5_m1_no_se_borra():
    # M5/M1 ausentes: score 4 (base), la operacion SIGUE (bonus, no condicion)
    from ict_backtest.plan_driver import score_plan

    sig = _signal(["SWEEP_DONE", "DISPLACE_DONE", "BOS_DONE", "ENTRY"])
    rep = score_plan(
        sig,
        d1_objs=[_obj(ObjectType.LIQUIDITY, 1, "D1", Role.CONTEXT)],
        h4_objs=[_obj(ObjectType.BOS, 1, "H4")],
        h1_objs=[_obj(ObjectType.ORDER_BLOCK, 1, "H1", Role.POI)],
        m15_signal=sig,
        m5_confirm={"direction": 1, "confirmed": False},
        m1_trigger={"direction": 1, "confirmed": False},
    )
    assert rep.score == 4.0
    assert rep.m5 is False and rep.m1 is False
    # La senal NO se descarta: el reporte existe y es valido para analisis
    assert rep is not None


def test_score_plan_sin_contexto_base_es_bajo():
    # Sin D1/H4/H1: solo M15 (1). M5/M1 NO suman bonus (no hay plan que refinar).
    # score 1.0 = operacion debil, se marca para analisis (no se borra).
    from ict_backtest.plan_driver import score_plan

    sig = _signal(["SWEEP_DONE", "DISPLACE_DONE", "BOS_DONE", "ENTRY"])
    rep = score_plan(
        sig,
        d1_objs=[],
        h4_objs=[],
        h1_objs=[],
        m15_signal=sig,
        m5_confirm={"direction": 1, "confirmed": True},
        m1_trigger={"direction": 1, "confirmed": True},
    )
    assert rep.score == 1.0
    assert rep.m5 is True and rep.m1 is True  # confirman, pero no aportan score sin base
