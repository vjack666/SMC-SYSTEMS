"""RED — Fase 1 (Arquitectura de Plan): PlanFSM + emisores D1/H4/H1.

TDD estricto. Este test FALLA hasta que se implementa `ict_backtest/plan_fsm.py`.
No toca producción (run_backtest / sequence / data_feed). Es una capa nueva.

Contrato (ver docs/plan/ARQUITECTURA_TEMPORALIDADES.md + ROADMAP_CAPACIDADES.md):
- PlanFSM es un reductor PURO (state, event) -> new_state. Sin bar_index ni timers.
- Cualquier *_INVALID devuelve a NO_TRADE.
- Emisores por TF son funciones puras que reciben SOLO sus MarketObjects.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

import pytest

from ict_backtest.plan_fsm import (
    PlanEvent,
    PlanFSM,
    PlanState,
    PlanVerdict,
)


def _event(layer: str, verdict: PlanVerdict, bar_index: int = 0) -> PlanEvent:
    return PlanEvent(layer=layer, verdict=verdict, payload=None, bar_index=bar_index, time=None)


def test_partida_siempre_en_no_trade():
    fsm = PlanFSM()
    assert fsm.state is PlanState.NO_TRADE


def test_cascada_plan_d1_h4_h1_llega_a_zone_armed():
    fsm = PlanFSM()
    # D1 + H4 arman contexto
    fsm.transition(_event("D1", PlanVerdict.CONTEXT_OK))
    assert fsm.state is PlanState.NO_TRADE  # falta H4
    fsm.transition(_event("H4", PlanVerdict.CONTEXT_OK))
    assert fsm.state is PlanState.CONTEXT_OK
    # H1 confirma el POI -> ZONE_ARMED
    fsm.transition(_event("H1", PlanVerdict.ZONE_ARMED))
    assert fsm.state is PlanState.ZONE_ARMED


def test_h1_invalida_vuelve_a_no_trade():
    fsm = PlanFSM()
    fsm.transition(_event("D1", PlanVerdict.CONTEXT_OK))
    fsm.transition(_event("H4", PlanVerdict.CONTEXT_OK))
    assert fsm.state is PlanState.CONTEXT_OK
    # H1 dice "esto ya quedó invalidado"
    fsm.transition(_event("H1", PlanVerdict.ZONE_INVALID))
    assert fsm.state is PlanState.NO_TRADE


def test_context_invalid_vuelve_a_no_trade():
    fsm = PlanFSM()
    fsm.transition(_event("D1", PlanVerdict.CONTEXT_INVALID))
    assert fsm.state is PlanState.NO_TRADE


def test_no_avanza_a_zone_armed_sin_context_ok():
    fsm = PlanFSM()
    # H1 no puede armar ZONE_ARMED si no hubo CONTEXT_OK
    fsm.transition(_event("H1", PlanVerdict.ZONE_ARMED))
    assert fsm.state is PlanState.NO_TRADE


def test_transicion_es_pura_no_mutua_estado_interno():
    # La FSM debe poder resetearse; transicionar es idempotente en reset.
    fsm = PlanFSM()
    fsm.transition(_event("D1", PlanVerdict.CONTEXT_OK))
    fsm.transition(_event("H4", PlanVerdict.CONTEXT_OK))
    fsm.transition(_event("H1", PlanVerdict.ZONE_INVALID))
    assert fsm.state is PlanState.NO_TRADE
    # tras reset, vuelve a armar plan
    fsm.transition(_event("D1", PlanVerdict.CONTEXT_OK))
    fsm.transition(_event("H4", PlanVerdict.CONTEXT_OK))
    assert fsm.state is PlanState.CONTEXT_OK
