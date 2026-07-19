"""RED — Fase 4: emisor M1 (Optimizacion/trigger fino) -> IN_TRADE.

emit_m1 es el ultimo filtro de timing: el plan ya esta en ENTRY_READY
(decision de M5). M1 confirma el trigger fino y dispara IN_TRADE.
M1 NO cambia direccion ni plan. Test FALLA hasta implementar emit_m1
y la transicion ENTRY_READY->IN_TRADE.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

from ict_backtest.plan_fsm import PlanFSM, PlanState, PlanVerdict
from ict_backtest.plan_emitters import emit_m5


def _trigger(direction, confirmed):
    return {"direction": direction, "confirmed": confirmed}


def test_emit_m1_in_trade_cuando_trigger_alcista():
    from ict_backtest.plan_emitters import emit_m1

    ev = emit_m1({"direction": 1}, _trigger(1, True))
    assert ev is not None
    assert ev.layer == "M1"
    assert ev.verdict is PlanVerdict.IN_TRADE


def test_emit_m1_none_cuando_sin_trigger():
    from ict_backtest.plan_emitters import emit_m1

    ev = emit_m1({"direction": 1}, _trigger(1, False))
    assert ev is None


def test_emit_m1_none_cuando_direccion_no_coincide():
    # M1 NO invierte la direccion del plan
    from ict_backtest.plan_emitters import emit_m1

    ev = emit_m1({"direction": 1}, _trigger(-1, True))
    assert ev is None


def test_fsm_entry_ready_a_in_trade_con_m1():
    from ict_backtest.plan_emitters import emit_m1

    fsm = PlanFSM()
    # M5 lleva a ENTRY_READY
    fsm.state = PlanState.ENTRY_READY
    ev = emit_m1({"direction": 1}, _trigger(1, True))
    fsm.transition(ev)
    assert fsm.state is PlanState.IN_TRADE
