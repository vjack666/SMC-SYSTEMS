"""Fase 3 — Demo sintetica: cascada completa hasta ENTRY_READY (Ejecucion).

Muestra que tras STRUCTURE_OK (Fase 2), el emisor M5 decide SI entrar.
M5 NO invierte la direccion del plan: solo confirma en la misma.
Sin datos reales, sin tocar produccion.
Correr: python scripts/fase3_demo_plan.py
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
from ict_backtest.plan_emitters import emit_d1, emit_h4, emit_h1, emit_m15, emit_m5
from ict_backtest.plan_fsm import PlanFSM, PlanState


def _obj(t, d, tf, role=Role.REFINEMENT):
    return MarketObject(type=t, direction=d, origin_tf=tf, role=role, state=ObjectState.ACTIVE)


def _signal(phase_log):
    return {"phase_log": phase_log}


def _armar_plan_y_setup(fsm):
    fsm.transition(emit_d1([_obj(ObjectType.LIQUIDITY, 1, "D1", Role.CONTEXT)]))
    fsm.transition(emit_h4([_obj(ObjectType.BOS, 1, "H4")]))
    fsm.transition(emit_h1([_obj(ObjectType.ORDER_BLOCK, 1, "H1", Role.POI)]))
    fsm.transition(emit_m15([_signal(["SWEEP_DONE", "DISPLACE_DONE", "BOS_DONE", "ENTRY"])]))


print("=== Fase 3: Plan + Setup + Ejecucion ===")

# Escenario A: M5 confirma -> ENTRY_READY
fsm = PlanFSM()
_armar_plan_y_setup(fsm)
print(f"  Tras Setup: {fsm.state.value} (esperado STRUCTURE_OK)")
setup = {"direction": 1}
ev = emit_m5(setup, {"direction": 1, "confirmed": True})
fsm.transition(ev)
print(f"  M5 confirma: {ev.verdict.value:14} -> plan = {fsm.state.value}")
assert fsm.state is PlanState.ENTRY_READY

# Escenario B: M5 NO confirma -> plan se queda en STRUCTURE_OK
fsm = PlanFSM()
_armar_plan_y_setup(fsm)
ev = emit_m5({"direction": 1}, {"direction": 1, "confirmed": False})
if ev is not None:
    fsm.transition(ev)
print(f"  M5 sin confirm: plan = {fsm.state.value} (esperado STRUCTURE_OK, setup descartado)")
assert fsm.state is PlanState.STRUCTURE_OK

# Escenario C: M5 intenta invertir direccion -> None (no puede)
fsm = PlanFSM()
_armar_plan_y_setup(fsm)
ev = emit_m5({"direction": 1}, {"direction": -1, "confirmed": True})
if ev is not None:
    fsm.transition(ev)
print(f"  M5 invierte dir: plan = {fsm.state.value} (esperado STRUCTURE_OK, M5 no manda)")
assert fsm.state is PlanState.STRUCTURE_OK

print("\nFase 3 (Ejecucion) validada por demo sintetica. M5 decide SI entrar, no la direccion.")
