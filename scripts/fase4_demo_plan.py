"""Fase 4 — Demo sintetica: cascada COMPLETA hasta IN_TRADE (Optimizacion M1).

Muestra el flujo entero Plan->Setup->Ejecucion->Optimizacion. M1 es el
ultimo filtro de timing: dispara IN_TRADE si confirma en la misma
direccion; si no, el plan se queda en ENTRY_READY. Sin datos reales.
Correr: python scripts/fase4_demo_plan.py
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
from ict_backtest.plan_emitters import (
    emit_d1,
    emit_h4,
    emit_h1,
    emit_m15,
    emit_m5,
    emit_m1,
)
from ict_backtest.plan_fsm import PlanFSM, PlanState


def _obj(t, d, tf, role=Role.REFINEMENT):
    return MarketObject(type=t, direction=d, origin_tf=tf, role=role, state=ObjectState.ACTIVE)


def _signal(phase_log):
    return {"phase_log": phase_log}


def _armar_hasta_entry(fsm):
    fsm.transition(emit_d1([_obj(ObjectType.LIQUIDITY, 1, "D1", Role.CONTEXT)]))
    fsm.transition(emit_h4([_obj(ObjectType.BOS, 1, "H4")]))
    fsm.transition(emit_h1([_obj(ObjectType.ORDER_BLOCK, 1, "H1", Role.POI)]))
    fsm.transition(emit_m15([_signal(["SWEEP_DONE", "DISPLACE_DONE", "BOS_DONE", "ENTRY"])]))
    fsm.transition(emit_m5({"direction": 1}, {"direction": 1, "confirmed": True}))


print("=== Fase 4: cascada COMPLETA hasta IN_TRADE ===")

# Escenario A: M1 confirma -> IN_TRADE
fsm = PlanFSM()
_armar_hasta_entry(fsm)
print(f"  Tras M5: {fsm.state.value} (esperado ENTRY_READY)")
ev = emit_m1({"direction": 1}, {"direction": 1, "confirmed": True})
fsm.transition(ev)
print(f"  M1 trigger: {ev.verdict.value:14} -> plan = {fsm.state.value}")
assert fsm.state is PlanState.IN_TRADE

# Escenario B: M1 NO confirma -> plan se queda en ENTRY_READY
fsm = PlanFSM()
_armar_hasta_entry(fsm)
ev = emit_m1({"direction": 1}, {"direction": 1, "confirmed": False})
if ev is not None:
    fsm.transition(ev)
print(f"  M1 sin trigger: plan = {fsm.state.value} (esperado ENTRY_READY, entra despues)")
assert fsm.state is PlanState.ENTRY_READY

print("\nFase 4 (Optimizacion M1) validada. Flujo COMPLETO: NO_TRADE -> CONTEXT_OK"
      " -> ZONE_ARMED -> SETUP_LIVE/STRUCTURE_OK -> ENTRY_READY -> IN_TRADE.")
