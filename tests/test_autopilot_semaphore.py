"""Tests del semáforo de la pestaña Auto (single source of truth: motor grande).

El semáforo ya NO recalcula MT5/stochastic_signal: es un visor fiel de
engine.run_cycle. Estos tests verifican el mapeo _lights_from_cache(cache)
que traduce el veredicto del motor a las 4 luces.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from app_observador.ui.autopilot_widget import AutopilotWidget, _PHASES


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def _cache(extreme, cross, confirm, aligned, trigger="READY"):
    return {
        "bias": "LONG (comprar)" if aligned else "NEUTRAL (esperar)",
        "veredicto": {
            "context_alignment": {
                "alignment": "ALIGNED" if aligned else "DIVERGENT",
                "trigger": trigger,
            },
        },
        "stoch_m15": {"k": 15.0, "d": 18.0, "extreme": extreme, "cross": cross, "confirm": confirm},
    }


def _widget():
    # _lights_from_cache es @staticmethod: no necesita QApplication ni MT5.
    return AutopilotWidget.__new__(AutopilotWidget)


def test_phases_all_red_when_flat():
    w = _widget()
    states = w._lights_from_cache(_cache(False, False, False, False))
    assert states == {"extreme": False, "cross": False, "confirm": False, "trend": False}


def test_phase_extreme_in_oversold():
    w = _widget()
    states = w._lights_from_cache(_cache(True, False, False, True))
    assert states["extreme"] is True
    assert states["cross"] is False


def test_phase_cross_and_confirm_bull():
    w = _widget()
    states = w._lights_from_cache(_cache(True, True, True, True))
    assert states["extreme"] is True
    assert states["cross"] is True
    assert states["confirm"] is True


def test_confirm_false_when_trigger_pending():
    w = _widget()
    # cruce presente pero el motor no marca trigger READY -> SEÑAL FIRME off
    states = w._lights_from_cache(_cache(True, True, True, True, trigger="PENDING"))
    assert states["cross"] is True
    assert states["confirm"] is False


def test_trend_phase_needs_alignment():
    w = _widget()
    # estocástico en zona + cruce, pero contexto DIVERGENTE -> trend off
    states = w._lights_from_cache(_cache(True, True, True, False))
    assert states["trend"] is False


def test_four_phases_defined():
    assert len(_PHASES) == 4
    assert [p[0] for p in _PHASES] == ["extreme", "cross", "confirm", "trend"]
