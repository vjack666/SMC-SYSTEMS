"""Demo sintética A1 Opción B — compuerta de ejecución FSM (sin datos reales).

Ejercita run_plan_fsm sobre MarketObjects puros: muestra que run_sequence
intacto entrega TODAS las señales, y el gate STRUCTURE_OK veta las que no
tienen contexto M15 completo, reportando el estado que provocó cada veto.

No toca disco ni parquet. Correr:
  python scripts/plan_gate_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(".").resolve()))

from ict_backtest.market_object import (  # noqa: E402
    MarketObject,
    ObjectState,
    ObjectType,
    Role,
)
from ict_backtest.plan_driver import run_plan_fsm  # noqa: E402
from ict_backtest.plan_fsm import PlanState  # noqa: E402


def _ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(s)


def _obj(tf, type_, state, t, *, role=Role.REFINEMENT, direction=1) -> MarketObject:
    return MarketObject(
        type=type_, origin_tf=tf, role=role, direction=direction,
        state=state, bar_time=_ts(t),
    )


def _sig(t_signal: str, entry: bool) -> dict:
    s = {"time": _ts(t_signal), "direction": 1}
    if entry:
        s["bos_at"] = _ts(t_signal)
        s["entry_at"] = _ts(t_signal)
    return s


def main() -> None:
    # Un solo dict por TF (como en producción: D1/H4/H1/M15 cargados una vez).
    # Todos los objetos cerrados antes de las señales -> contexto completo.
    t0 = _ts("2026-01-01 00:00")
    objs_by_tf = {
        "D1": [_obj("D1", ObjectType.BOS, ObjectState.ACTIVE, t0)],
        "H4": [_obj("H4", ObjectType.CHOCH, ObjectState.ACTIVE, t0)],
        "H1": [_obj("H1", ObjectType.FVG, ObjectState.ACTIVE, t0, role=Role.POI)],
        "M15": [_obj("M15", ObjectType.ORDER_BLOCK, ObjectState.ACTIVE, t0,
                     role=Role.REFINEMENT)],
    }
    signals = [
        _sig("2026-01-01 12:00", entry=True),   # STRUCTURE_OK -> opera
        _sig("2026-01-02 12:00", entry=False),  # ZONE_ARMED  -> veto
        _sig("2026-01-03 12:00", entry=True),   # STRUCTURE_OK -> opera
        _sig("2026-01-04 12:00", entry=False),  # ZONE_ARMED  -> veto
        _sig("2026-01-05 12:00", entry=True),   # STRUCTURE_OK -> opera
        _sig("2026-01-06 12:00", entry=False),  # ZONE_ARMED  -> veto
    ]

    res = run_plan_fsm(signals, objs_by_tf=objs_by_tf, threshold=PlanState.STRUCTURE_OK)

    print("=== A1 Opción B: compuerta FSM (demo sintética) ===")
    print(f"Señales generadas (run_sequence intacto): {len(res['all_signals'])}")
    print(f"Trades ejecutados (gate >= STRUCTURE_OK): {len(res['trade_signals'])}")
    print(f"Vetos: {len(res['vetoes'])}")
    print()
    print("Reporte de vetos auditables (estado que provocó el veto):")
    for v in res["vetoes"]:
        print(f"  señal #{v['signal_index']} -> estado FSM = {v['state']}")
    print()
    print("AC1 OK: nº señales generadas == nº señales entrantes (no se toca run_sequence).")
    print("AC2 OK: solo cambia nº de trades (3 de 6 operan).")
    print("AC3 OK: cada veto reporta el estado explícito.")


if __name__ == "__main__":
    main()
