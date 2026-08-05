"""Tests del semáforo de la pestaña Auto (lógica de fases, sin MT5)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app_observador.ui.autopilot_widget import AutopilotWidget, _PHASES


def _make_m15(k_vals, d_vals):
    n = len(k_vals)
    t = pd.date_range("2026-01-01", periods=n, freq="15min")
    return pd.DataFrame(
        {
            "time": t,
            "open": np.arange(n, dtype=float),
            "high": np.arange(n, dtype=float) + 1,
            "low": np.arange(n, dtype=float) - 1,
            "close": np.arange(n, dtype=float),
            "tick_volume": np.ones(n),
            "stoch_k": np.array(k_vals, dtype=float),
            "stoch_d": np.array(d_vals, dtype=float),
        }
    )


def _widget():
    # no QApplication needed: mockeamos la parte de MT5
    w = AutopilotWidget.__new__(AutopilotWidget)
    w._mt5_ready = False
    w._ctx_cache = None
    w._ctx_age = 0.0
    w._lights = {}
    w._mt5 = None
    return w


def test_phases_all_red_when_flat():
    w = _widget()
    # estocástico en el medio, sin zona ni cruce
    m15 = _make_m15([50, 50, 50, 50, 50], [50, 50, 50, 50, 50])
    states = w._eval_phases(m15)
    assert states == {"extreme": False, "cross": False, "confirm": False, "trend": False}


def test_phase_extreme_in_oversold():
    w = _widget()
    # ambos < 20 -> sobreventa (extreme on), pero sin cruce
    m15 = _make_m15([15, 15, 15, 15, 15], [15, 15, 15, 15, 15])
    states = w._eval_phases(m15)
    assert states["extreme"] is True
    assert states["cross"] is False


def test_phase_cross_and_confirm_bull():
    w = _widget()
    # sobreventa (ambos <20) + K cruza al alza con separación>=1 y momentum
    # prev: K<=D ; last: K>D, ambos <20, sep>=MIN_SEP, K sube, K queda <30
    m15 = _make_m15([15, 15, 15, 17, 19], [16, 16, 16, 19.5, 18])
    states = w._eval_phases(m15)
    assert states["extreme"] is True
    assert states["cross"] is True
    assert states["confirm"] is True


def test_phase_confirm_false_when_cross_is_noise():
    w = _widget()
    # cruce pero separación < MIN_SEP (roce)
    m15 = _make_m15([18, 18, 18, 19.0, 19.4], [19, 19, 19, 19.1, 19.1])
    states = w._eval_phases(m15)
    assert states["cross"] is True
    assert states["confirm"] is False  # sep < MIN_SEP


def test_trend_phase_needs_context():
    w = _widget()
    m15 = _make_m15([18, 18, 18, 17, 24], [19, 19, 19, 19, 22])
    states = w._eval_phases(m15)
    # sin contexto cacheado, trend queda False aunque el cruce sea BUY
    assert states["trend"] is False


def test_four_phases_defined():
    assert len(_PHASES) == 4
    assert [p[0] for p in _PHASES] == ["extreme", "cross", "confirm", "trend"]
