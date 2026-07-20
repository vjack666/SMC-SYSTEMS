"""RED — Brecha A1 (Opción B): compuerta de ejecución FSM en run_backtest.

TDD estricto. Este test FALLA hasta que se implemente el cableado real de
A1 nivel 2:
  - ict_backtest/plan_driver.py  -> run_plan_fsm(...) (dueño de PlanFSM)
  - ict_backtest/run_backtest.py -> run_sequence_backtest(plan_gate=True)

Criterios de aceptación de Ruben (2026-07-20):
  AC1. El nº de señales generadas por run_sequence es IDÉNTICO al baseline
       (la FSM NO toca generación, solo ejecución).
  AC2. Solo puede cambiar el nº de TRADES ejecutados.
  AC3. Cada trade descartado (veto) debe reportar EXPLÍCITAMENTE el estado
       de la FSM que provocó el veto (NO_TRADE / CONTEXT_OK / ZONE_ARMED /
       ...), para auditoría del gate.

Diseño aprobado (Opción B, umbral STRUCTURE_OK):
  - run_sequence intacto: genera la lista completa de señales como hoy.
  - Una sola instancia PlanFSM vive durante TODO el backtest (no se resetea
    por señal).
  - Por cada señal, en su t=sig.time, se alimentan emit_d1/h4/h1/m15 (y
    m5/m1 si existen) con MarketObjects cerrados <= t; fsm.transition.
  - Si fsm.state >= STRUCTURE_OK -> la señal OPERA. Si no -> VETO, se salta
    el trade y se registra el estado en m["vetoes"].

Sintético: NO toca disco ni parquet. Usa MarketObject puro.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(".").resolve()))

from ict_backtest.market_object import (  # noqa: E402
    MarketObject,
    ObjectState,
    ObjectType,
    Role,
)


# ---------------------------------------------------------------------------
# Helpers sintéticos (sin datos reales)
# ---------------------------------------------------------------------------

def _ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(s)


def _obj(tf: str, type_, state, t, *, role=Role.REFINEMENT, direction: int = 1) -> MarketObject:
    return MarketObject(
        type=type_,
        origin_tf=tf,
        role=role,
        direction=direction,
        state=state,
        bar_time=_ts(t),
    )


def _aligned_objs(t_signal: str) -> dict:
    """Contexto COMPLETO cerrado <= t: D1+H4 CONTEXT_OK, H1 ZONE_ARMED, M15 entry."""
    t = _ts(t_signal)
    return {
        "D1": [_obj("D1", ObjectType.BOS, ObjectState.ACTIVE, t)],
        "H4": [_obj("H4", ObjectType.CHOCH, ObjectState.ACTIVE, t)],
        "H1": [_obj("H1", ObjectType.FVG, ObjectState.ACTIVE, t, role=Role.POI)],
    }


def _partial_objs(t_signal: str) -> dict:
    """Contexto PARCIAL: D1 + H4 OK, pero H1 SIN POI -> FSM queda en CONTEXT_OK."""
    t = _ts(t_signal)
    return {
        "D1": [_obj("D1", ObjectType.BOS, ObjectState.ACTIVE, t)],
        "H4": [_obj("H4", ObjectType.CHOCH, ObjectState.ACTIVE, t)],
        # sin H1 -> ZONE no se arma -> estado CONTEXT_OK (veto con estado intermedio)
    }


def _sig(t_signal: str, entry: bool) -> dict:
    """Señal M15 sintética.
    entry=True  => entry_at presente (STRUCTURE_OK).
    entry=False => sin bos ni entry (M15 sin setup -> queda en ZONE_ARMED).
    """
    s = {
        "time": _ts(t_signal),
        "direction": 1,
    }
    if entry:
        s["bos_at"] = _ts(t_signal)
        s["entry_at"] = _ts(t_signal)
    return s


# ---------------------------------------------------------------------------
# AC3 + comportamiento del gate (run_plan_fsm)
# ---------------------------------------------------------------------------

def test_run_plan_fsm_rechaza_senal_sin_alineacion_y_reporta_estado():
    """Import falla hoy (RED). GREEN: run_plan_fsm decide y reporta veto."""
    from ict_backtest.plan_driver import run_plan_fsm
    from ict_backtest.plan_fsm import PlanState

    # Dict global de objetos (como en producción: D1/H4/H1 siempre cargados).
    # Contexto alineado hasta H1 (ZONE_ARMED).
    base_objs = {
        "D1": [_obj("D1", ObjectType.BOS, ObjectState.ACTIVE, "2026-01-05 12:00")],
        "H4": [_obj("H4", ObjectType.CHOCH, ObjectState.ACTIVE, "2026-01-05 12:00")],
        "H1": [_obj("H1", ObjectType.FVG, ObjectState.ACTIVE, "2026-01-05 12:00", role=Role.POI)],
    }
    signals = [
        _sig("2026-01-05 12:00", entry=True),    # M15 entry -> STRUCTURE_OK -> opera
        _sig("2026-01-06 12:00", entry=False),   # M15 SIN setup -> queda ZONE_ARMED -> veto
    ]
    res = run_plan_fsm(signals, objs_by_tf=base_objs, threshold=PlanState.STRUCTURE_OK)

    # AC1: no se pierde ninguna señal generada
    assert len(res["all_signals"]) == 2
    # AC2: solo 1 trade opera
    assert len(res["trade_signals"]) == 1
    # AC3: el veto reporta el estado explícito que lo provocó (ZONE_ARMED)
    assert len(res["vetoes"]) == 1
    veto = res["vetoes"][0]
    assert veto["signal_index"] == 1
    assert veto["state"] == PlanState.ZONE_ARMED.value


def test_run_plan_fsm_mantiene_conteo_de_senales_generadas():
    """AC1: run_sequence intacto -> el gate recibe TODAS las señales."""
    from ict_backtest.plan_driver import run_plan_fsm
    from ict_backtest.plan_fsm import PlanState

    signals = [_sig(f"2026-01-{d:02d} 12:00", entry=True) for d in range(1, 6)]
    objs_list = [_aligned_objs(f"2026-01-{d:02d} 12:00") for d in range(1, 6)]

    res = run_plan_fsm(signals, objs_by_tf=objs_list, threshold=PlanState.STRUCTURE_OK)

    # Generación idéntica al baseline: 5 señales entran, 5 salen del gate.
    assert len(res["all_signals"]) == 5
    # Con alineación completa, las 5 operan.
    assert len(res["trade_signals"]) == 5
    assert res["vetoes"] == []


# ---------------------------------------------------------------------------
# AC: firma de run_sequence_backtest acepta plan_gate (cableado en loop)
# ---------------------------------------------------------------------------

def test_run_sequence_backtest_acepta_plan_gate():
    """Hoy run_sequence_backtest NO tiene el kwarg plan_gate -> TypeError (RED)."""
    import inspect

    from ict_backtest import run_backtest

    sig = inspect.signature(run_backtest.run_sequence_backtest)
    assert "plan_gate" in sig.parameters, (
        "run_sequence_backtest debe aceptar plan_gate (Opción B A1)"
    )
    assert sig.parameters["plan_gate"].default is False, (
        "plan_gate debe ser False por defecto (baseline intacto)"
    )


def test_run_sequence_backtest_plan_gate_call_site_real():
    """AUDITORÍA DE CALL SITE: el gate se ejecuta DENTRO del loop real de
    run_backtest (no solo la función aislada). Parchea generate_sequence_signals
    y _build_objs_by_tf con datos sintéticos (sin tocar parquet/run_sequence).

    AC1: nº señales generadas (len signals) NO cambia con plan_gate.
    AC2: nº trades baja cuando el gate veta.
    AC3: m['vetoes'] reporta el estado que provocó cada veto.
    """
    import pandas as pd
    from unittest import mock

    from ict_backtest import run_backtest
    from ict_backtest.market_object import (
        MarketObject, ObjectState, ObjectType, Role,
    )

    # Señales sintéticas como ICTSignal reales (el loop espera objetos con
    # .time str y .entry_at int|None). 2 con entry (STRUCTURE_OK), 1 sin.
    from ict_backtest.engine import ICTSignal

    s_ok = ICTSignal(symbol="XAUUSD", time="2026-01-01 12:00", direction=1,
                     entry=1.0, stop_loss=0.9, take_profit=1.3,
                     entry_at=0, bos_at=0)
    s_bad = ICTSignal(symbol="XAUUSD", time="2026-01-02 12:00", direction=1,
                      entry=1.0, stop_loss=0.9, take_profit=1.3,
                      entry_at=None, bos_at=None)

    def _fake_signals(*a, **k):
        return [s_ok, s_bad, s_ok]

    t0 = pd.Timestamp("2026-01-01 00:00")
    objs = {
        "D1": [MarketObject(type=ObjectType.BOS, origin_tf="D1", state=ObjectState.ACTIVE, bar_time=t0)],
        "H4": [MarketObject(type=ObjectType.CHOCH, origin_tf="H4", state=ObjectState.ACTIVE, bar_time=t0)],
        "H1": [MarketObject(type=ObjectType.FVG, origin_tf="H1", role=Role.POI, state=ObjectState.ACTIVE, bar_time=t0)],
        "M15": [MarketObject(type=ObjectType.ORDER_BLOCK, origin_tf="M15", role=Role.REFINEMENT, state=ObjectState.ACTIVE, bar_time=t0)],
    }

    def _fake_objs(*a, **k):
        return objs

    def _fake_frames(*a, **k):
        return {"M15": pd.DataFrame({"time": [pd.Timestamp("2026-01-01 12:00"),
                                             pd.Timestamp("2026-01-02 12:00")]})}

    def _fake_ms(df, *a, **k):
        return df

    with mock.patch.object(run_backtest, "generate_sequence_signals", _fake_signals), \
         mock.patch.object(run_backtest, "_build_objs_by_tf", _fake_objs), \
         mock.patch.object(run_backtest, "load_frames", _fake_frames), \
         mock.patch.object(run_backtest, "detect_market_structure", _fake_ms), \
         mock.patch("ict_backtest.v2.context_mtf.build_context_stack", lambda *a, **k: None), \
         mock.patch.object(run_backtest, "simulate_trade_with_context",
                           lambda *a, **k: (type("T", (), {"pnl_r": 1.0})(), {"exit_reason": "test"}, None)):
        # Sin gate (baseline)
        m_base = run_backtest.run_sequence_backtest(
            "XAUUSD", "D1", "M15", 16, plan_gate=False)
        # Con gate
        m_gate = run_backtest.run_sequence_backtest(
            "XAUUSD", "D1", "M15", 16, plan_gate=True)

    # AC1: run_sequence generó 3 señales en ambos (intacto). El gate reporta
    # explícitamente signals_total; el baseline opera todas (3 trades).
    assert m_gate["signals_total"] == 3
    # AC2: sin gate operan 3; con gate solo 2 (1 veto).
    assert m_base["trades"] == 3
    assert m_gate["trades"] == 2
    # AC3: el veto reporta estado explícito.
    assert len(m_gate["vetoes"]) == 1
    assert m_gate["vetoes"][0]["signal_index"] == 1
    assert m_gate["vetoes"][0]["state"] == "ZONE_ARMED"
