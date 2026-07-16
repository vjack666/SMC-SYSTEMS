"""tests/test_r10c_event_engine.py — Fase E (R10.C): EventEngine + run_semantic.

RED 1 (regla 3, anti-reloj): el modulo ict_backtest.event_engine NO debe
referenciar bos_gap / confirmation_window ni restar indices (i - idx > N).
Si el modulo no existe, el import falla (RED por ausencia).

RED 2 (equivalencia SUBSET) se agrega despues de GREEN 1, sobre datos H4.
"""
from __future__ import annotations

import inspect

import pytest


def test_event_engine_module_exists_and_is_clock_free():
    """RED: falla por ImportError hasta que exista event_engine.py.

    Luego (GREEN) verifica conductualmente que no hay reloj disfrazado:
    cero referencias a bos_gap / confirmation_window / resta de indices.
    """
    from ict_backtest.event_engine import EventEngine, run_semantic

    src = inspect.getsource(run_semantic) + inspect.getsource(EventEngine)
    body = "\n".join(
        ln for ln in src.splitlines() if not ln.strip().startswith("#")
    )
    assert "bos_gap" not in body, "run_semantic no debe usar bos_gap (reloj)"
    assert "confirmation_window" not in body, "run_semantic no debe usar confirmation_window"
    assert "-" not in body or "idx" not in body, "run_semantic no debe restar indices (i - idx)"
    assert " - " not in body, "run_semantic no debe restar indices (i - idx)"
    # Las funciones deben existir y ser invocables.
    assert callable(run_semantic)
    assert callable(EventEngine)
