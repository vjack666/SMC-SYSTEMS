"""Fase 1 — Demo sintética de la FSM de plan (sin datos reales).

Muestra la cascada D1->H4->H1->ZONE_ARMED y el veto de H1.
No toca produccion. Solo construye MarketObjects de mentira y corre
PlanFSM + emisores. Correr: python scripts/fase1_demo_plan.py
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
from ict_backtest.plan_emitters import emit_d1, emit_h4, emit_h1
from ict_backtest.plan_fsm import PlanFSM, PlanState


def _obj(t, d, tf, role=Role.REFINEMENT):
    return MarketObject(type=t, direction=d, origin_tf=tf, role=role, state=ObjectState.ACTIVE)


def _demo(titulo, d1, h4, h1):
    print(f"\n=== {titulo} ===")
    fsm = PlanFSM()
    for emisor, objs, nombre in ((emit_d1, d1, "D1"), (emit_h4, h4, "H4"), (emit_h1, h1, "H1")):
        ev = emisor(objs)
        fsm.transition(ev)
        print(f"  {nombre:3} -> {ev.verdict.value:16} | plan = {fsm.state.value}")
    print(f"  RESULTADO: {fsm.state.value}")
    return fsm.state


# Escenario A: plan valido (D1 contexto + H4 bias + H1 POI)
_d1 = [_obj(ObjectType.LIQUIDITY, 1, "D1", Role.CONTEXT)]
_h4 = [_obj(ObjectType.BOS, 1, "H4")]
_h1 = [_obj(ObjectType.ORDER_BLOCK, 1, "H1", Role.POI)]
assert _demo("Plan VALIDO (D1+H4+H1)", _d1, _h4, _h1) is PlanState.ZONE_ARMED

# Escenario B: H1 veto (mismo arriba pero H1 sin POI)
_h1_vacio = []
assert _demo("H1 VETA el plan (sin POI en H1)", _d1, _h4, _h1_vacio) is PlanState.NO_TRADE

# Escenario C: H4 sin bias -> no hay contexto
_h4_vacio = []
assert _demo("H4 sin bias -> NO hay plan", _d1, _h4_vacio, _h1) is PlanState.NO_TRADE

print("\nTodos los escenarios pasaron. Fase 1 (Plan) validada por demo sintetica.")
