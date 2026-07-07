from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from agents.wyckoff_agent import WyckoffAgent
from adapters.wyckoff_adapter import WyckoffAdapter
from fixtures.synthetic_ohlcv import generate_synthetic_ohlcv
from indicators import add_stochastic


@pytest.fixture
def synth_frame():
    return generate_synthetic_ohlcv(n_bars=500, seed=42)


@pytest.fixture
def trending_frame():
    rng = np.random.default_rng(42)
    n = 200
    prices = np.concatenate([
        np.linspace(1.10, 1.18, 80),
        np.linspace(1.18, 1.10, 80),
        np.linspace(1.10, 1.12, 40),
    ])
    prices += rng.normal(0.0, 0.001, n)
    return pd.DataFrame({
        "time": pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC"),
        "open": prices,
        "high": prices + abs(rng.normal(0.0, 0.002, n)),
        "low": prices - abs(rng.normal(0.0, 0.002, n)),
        "close": prices,
        "tick_volume": rng.integers(100, 10000, n),
    })


class TestAddStochastic:
    def test_add_stochastic_adds_columns(self, synth_frame):
        result = add_stochastic(synth_frame)
        assert "stoch_k" in result.columns
        assert "stoch_d" in result.columns
        assert "stoch_k_raw" in result.columns

    def test_stoch_values_in_range(self, synth_frame):
        result = add_stochastic(synth_frame)
        valid = result.dropna()
        assert (valid["stoch_k"] >= 0.0).all()
        assert (valid["stoch_k"] <= 100.0).all()
        assert (valid["stoch_d"] >= 0.0).all()
        assert (valid["stoch_d"] <= 100.0).all()

    def test_stoch_overbought_overshoot(self, trending_frame):
        result = add_stochastic(trending_frame)
        tail = result["stoch_k"].dropna()
        assert (tail > 80.0).any() or (tail < 20.0).any()


class TestWyckoffExhaustion:
    def _override_last_bars(self, frame: pd.DataFrame, stoch_before: float, stoch_after: float) -> pd.DataFrame:
        frame = frame.copy()
        stoch = add_stochastic(frame)
        k_vals = stoch["stoch_k"].values.copy()
        d_vals = stoch["stoch_d"].values.copy()
        idx = len(k_vals) - 2
        k_vals[idx] = stoch_before
        d_vals[idx] = stoch_before
        k_vals[idx + 1] = stoch_after
        d_vals[idx + 1] = stoch_after
        frame["stoch_k"] = k_vals
        frame["stoch_d"] = d_vals
        frame.loc[frame.index[-1], "tick_volume"] = int(frame["tick_volume"].mean() * 3)
        return frame

    def test_detect_exhaustion_bullish(self):
        frame = generate_synthetic_ohlcv(n_bars=100, seed=42)
        frame = self._override_last_bars(frame, stoch_before=15.0, stoch_after=25.0)
        agent = WyckoffAgent(lookback=40)
        result = agent.analyze(frame, len(frame) - 1)
        exhaustion = result.evidence.get("stoch_exhaustion")
        assert exhaustion is not None
        assert exhaustion["type"] == "BULLISH_EXHAUSTION"

    def test_detect_exhaustion_bearish(self):
        frame = generate_synthetic_ohlcv(n_bars=100, seed=42)
        frame = self._override_last_bars(frame, stoch_before=85.0, stoch_after=75.0)
        agent = WyckoffAgent(lookback=40)
        result = agent.analyze(frame, len(frame) - 1)
        exhaustion = result.evidence.get("stoch_exhaustion")
        assert exhaustion is not None
        assert exhaustion["type"] == "BEARISH_EXHAUSTION"

    def test_volume_confirmed(self):
        frame = generate_synthetic_ohlcv(n_bars=100, seed=42)
        frame = self._override_last_bars(frame, stoch_before=15.0, stoch_after=25.0)
        agent = WyckoffAgent(lookback=40)
        result = agent.analyze(frame, len(frame) - 1)
        exhaustion = result.evidence.get("stoch_exhaustion")
        assert exhaustion is not None
        assert exhaustion.get("volume_confirmed", False) is True

    def test_stoch_divergence_detected(self):
        frame = generate_synthetic_ohlcv(n_bars=100, seed=42)
        frame = self._override_last_bars(frame, stoch_before=15.0, stoch_after=25.0)
        frame.loc[frame.index[-1], "low"] = float(frame["low"].iloc[-2]) * 0.98
        agent = WyckoffAgent(lookback=40)
        result = agent.analyze(frame, len(frame) - 1)
        exhaustion = result.evidence.get("stoch_exhaustion")
        assert exhaustion is not None
        assert exhaustion.get("divergence", False), f"Expected divergence, got: {exhaustion}"

    def test_exhaustion_missed_when_stoch_mid(self):
        frame = generate_synthetic_ohlcv(n_bars=100, seed=42)
        stoch = add_stochastic(frame)
        k = stoch["stoch_k"].values.copy()
        d = stoch["stoch_d"].values.copy()
        idx = len(k) - 2
        k[idx] = 50.0; d[idx] = 50.0
        k[idx + 1] = 52.0; d[idx + 1] = 52.0
        frame["stoch_k"] = k
        frame["stoch_d"] = d
        agent = WyckoffAgent(lookback=40)
        result = agent.analyze(frame, len(frame) - 1)
        exhaustion = result.evidence.get("stoch_exhaustion")
        assert exhaustion is None, f"Expected None, got: {exhaustion}"


class TestWyckoffAdapter:
    def test_adapter_bullish_exhaustion(self):
        adapter = WyckoffAdapter()
        result = adapter.run([], {"scenario": "bullish_exhaustion"})
        assert result["status"] == "ok"
        assert result["stoch_exhaustion_type"] == "BULLISH_EXHAUSTION"
        assert result["volume_confirmed"] is True

    def test_adapter_bearish_exhaustion(self):
        adapter = WyckoffAdapter()
        result = adapter.run([], {"scenario": "bearish_exhaustion"})
        assert result["status"] == "ok"
        assert result["stoch_exhaustion_type"] == "BEARISH_EXHAUSTION"
        assert result["volume_confirmed"] is True

    def test_adapter_no_exhaustion(self):
        adapter = WyckoffAdapter()
        result = adapter.run([], {"scenario": "no_exhaustion"})
        assert result["status"] == "ok"
        assert result["stoch_exhaustion_type"] == ""
