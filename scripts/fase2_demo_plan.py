"""Fase 2 — Demo sintetica: cascada completa D1->H4->H1->M15 (Setup).

Muestra que tras ZONE_ARMED (Fase 1), el emisor M15 lleva el plan a
SETUP_LIVE y luego STRUCTURE_OK. run_sequence se simula con senales
sinteticas (no se corre el real). Sin datos reales, sin tocar produccion.
Correr: python scripts/fase2_demo_plan.py
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
from ict_backtest.plan_fsm import PlanFSM, PlanState, PlanVerdict


def _obj(t, d, tf, role=Role.REFINEMENT):
    return MarketObject(type=t, direction=d, origin_tf=tf, role=role, state=ObjectState.ACTIVE)


def _signal(phase_log):
    return {"phase_log": phase_log}


def _armar_plan(fsm):
    fsm.transition(emit_d1([_obj(ObjectType.LIQUIDITY, 1, "D1", Role.CONTEXT)]))
    fsm.transition(emit_h4([_obj(ObjectType.BOS, 1, "H4")]))
    fsm.transition(emit_h1([_obj(ObjectType.ORDER_BLOCK, 1, "H1", Role.POI)]))


print("=== Fase 2: Plan + Setup ===")

# Escenario A: setup llega a BOS (SETUP_LIVE)
fsm = PlanFSM()
_armar_plan(fsm)
print(f"  Tras Plan: {fsm.state.value} (esperado ZONE_ARMED)")
ev = emit_m15([_signal(["SWEEP_DONE", "DISPLACE_DONE", "BOS_DONE"])])
fsm.transition(ev)
print(f"  M15 setup (BOS): {ev.verdict.value:14} -> plan = {fsm.state.value}")
assert fsm.state is PlanState.SETUP_LIVE

# Escenario B: setup llega a ENTRY (STRUCTURE_OK)
fsm = PlanFSM()
_armar_plan(fsm)
ev = emit_m15([_signal(["SWEEP_DONE", "DISPLACE_DONE", "BOS_DONE", "ENTRY"])])
fsm.transition(ev)
print(f"  M15 setup (ENTRY): {ev.verdict.value:14} -> plan = {fsm.state.value}")
assert fsm.state is PlanState.STRUCTURE_OK

# Escenario C: plan armar pero M15 no encuentra setup -> se queda en ZONE_ARMED
fsm = PlanFSM()
_armar_plan(fsm)
ev = emit_m15([])
if ev is not None:
    fsm.transition(ev)
print(f"  M15 sin setup: plan = {fsm.state.value} (esperado ZONE_ARMED, no avanza)")
assert fsm.state is PlanState.ZONE_ARMED

print("\nFase 2 (Setup) validada por demo sintetica. run_sequence se simulo.")
