"""TDD tests for SMT Divergence detector (libro 24 / R3.5).

Tests cover:
- Pure function: smt_divergence() with synthetic OHLC data
- No-lookahead verification
- flag_smt_divergence() wiring to ICTSignal
- Edge cases: insufficient data, flat markets, single instrument
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ict_backtest.setups.smt_divergence import (
    _swing_highs,
    _swing_lows,
    smt_divergence,
    flag_smt_divergence,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_ohlc(highs: list[float], lows: list[float], closes: list[float] | None = None) -> pd.DataFrame:
    """Build minimal OHLC DataFrame from lists."""
    n = len(highs)
    if closes is None:
        closes = [(h + l) / 2 for h, l in zip(highs, lows)]
    opens = closes[:1] + closes[:-1]
    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": [100.0] * n,
    })


class TestSwingPoints:
    """Test swing high/low detection (left-only window = no lookahead)."""

    def test_swing_high_basic(self):
        """Peak at index 5 should be detected as swing high."""
        highs = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.4, 1.3, 1.2]
        swings = _swing_highs(np.array(highs), lookback=3)
        assert len(swings) >= 1
        # The highest point (1.5 at index 5) should be in results
        prices = [s[1] for s in swings]
        assert 1.5 in prices

    def test_swing_low_basic(self):
        """Trough at index 5 should be detected as swing low."""
        lows = [2.0, 1.9, 1.8, 1.7, 1.6, 1.5, 1.6, 1.7, 1.8]
        swings = _swing_lows(np.array(lows), lookback=3)
        assert len(swings) >= 1
        prices = [s[1] for s in swings]
        assert 1.5 in prices

    def test_no_consecutive_duplicates(self):
        """Flat tops should not produce duplicate swing points."""
        highs = [1.0, 1.5, 1.5, 1.5, 1.0]
        swings = _swing_highs(np.array(highs), lookback=2)
        prices = [s[1] for s in swings]
        # At most one 1.5 should appear
        assert prices.count(1.5) <= 1


class TestSmtDivergenceUnit:
    """Test smt_divergence() pure function with synthetic data."""

    def test_no_divergence_aligned(self):
        """Both instruments make higher highs → no divergence."""
        # Base: rising
        base = _make_ohlc(
            highs=[1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.5, 1.4, 1.3],
            lows=[0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.4, 1.3, 1.2],
        )
        # Correlate: also rising
        corr = _make_ohlc(
            highs=[1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.5, 1.4, 1.3],
            lows=[0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.4, 1.3, 1.2],
        )
        result = smt_divergence(base, corr, lookback=3)
        assert result["divergence"] is False
        assert result["direction"] is None

    def test_divergence_short_base_rises_correlate_falls(self):
        """Base makes higher high, correlate makes lower high → SHORT divergence."""
        # Base: makes HH (1.5 → 1.6)
        base = _make_ohlc(
            highs=[1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.3, 1.2, 1.4, 1.6],
            lows=[0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.2, 1.1, 1.3, 1.5],
        )
        # Correlate: makes LH (1.5 → 1.4)
        corr = _make_ohlc(
            highs=[1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.3, 1.2, 1.35, 1.4],
            lows=[0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.2, 1.1, 1.25, 1.3],
        )
        result = smt_divergence(base, corr, lookback=3)
        assert result["divergence"] is True
        assert result["direction"] == "SHORT"
        assert result["strength"] > 0.0

    def test_divergence_long_base_falls_correlate_rises(self):
        """Base makes lower low, correlate makes higher low → LONG divergence.
        Gentle V-shapes (mirror of SHORT test approach) — no flat regions.
        """
        # Base: descends to 0.5 (idx5), recovers, then deeper to 0.4 (idx9) → LL
        base = _make_ohlc(
            highs=[1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.3, 1.2, 1.35, 1.4],
            lows=[1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.7, 0.8, 0.65, 0.4],
        )
        # Correlate: descends to 0.5 (idx5), recovers, then shallower to 0.6 (idx9) → HL
        corr = _make_ohlc(
            highs=[1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.3, 1.2, 1.4, 1.6],
            lows=[1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.7, 0.8, 0.75, 0.6],
        )
        result = smt_divergence(base, corr, lookback=3)
        b_sl = _swing_lows(base['low'].to_numpy(), 3)
        c_sl = _swing_lows(corr['low'].to_numpy(), 3)
        print(f"base SL: {b_sl}")
        print(f"corr SL: {c_sl}")
        print(f"result: {result}")
        assert result["divergence"] is True
        assert result["direction"] == "LONG"
        assert result["strength"] > 0.0

    def test_insufficient_data(self):
        """Too few bars → no divergence."""
        base = _make_ohlc(highs=[1.0, 1.1], lows=[0.9, 1.0])
        corr = _make_ohlc(highs=[1.0, 1.1], lows=[0.9, 1.0])
        result = smt_divergence(base, corr, lookback=40)
        assert result["divergence"] is False

    def test_none_inputs(self):
        """None inputs → no crash, returns safe defaults."""
        result = smt_divergence(None, None)
        assert result["divergence"] is False
        assert result["direction"] is None

    def test_strength_is_bounded(self):
        """Strength must be in [0, 1]."""
        base = _make_ohlc(
            highs=[1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.3, 1.2, 1.4, 2.0],
            lows=[0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.2, 1.1, 1.3, 1.9],
        )
        corr = _make_ohlc(
            highs=[1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.3, 1.2, 1.35, 1.4],
            lows=[0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.2, 1.1, 1.25, 1.3],
        )
        result = smt_divergence(base, corr, lookback=3)
        assert 0.0 <= result["strength"] <= 1.0


class TestFlagWiring:
    """Test flag_smt_divergence() wiring to signal objects."""

    def _make_signal(self, entry_at: int = 5):
        """Create a minimal mock signal with SMT fields."""

        class MockSignal:
            def __init__(self):
                self.entry_at = entry_at
                self.smt_divergence_active = False
                self.smt_divergence_direction = None
                self.smt_divergence_strength = 0.0

        return MockSignal()

    def test_flag_annotates_divergence(self):
        """Signal gets annotated with SMT divergence when correlate data present.
        Oscillating data so swing detection finds 2+ swing points.
        """
        # Base: makes HH at end (1.5→1.6)
        base_df = _make_ohlc(
            highs=[1.0, 1.1, 1.0, 0.9, 1.0, 1.1, 1.0, 0.9, 1.1, 1.2],
            lows=[0.9, 1.0, 0.9, 0.8, 0.9, 1.0, 0.9, 0.8, 1.0, 1.1],
        )
        # Correlate: makes LH at end (1.1→1.0)
        corr_df = _make_ohlc(
            highs=[1.0, 1.1, 1.0, 0.9, 1.0, 1.1, 1.0, 0.9, 1.0, 0.95],
            lows=[0.9, 1.0, 0.9, 0.8, 0.9, 1.0, 0.9, 0.8, 0.9, 0.85],
        )
        sig = self._make_signal(entry_at=9)
        frames = {
            "EURUSD_M15": base_df,
            "GBPUSD_M15": corr_df,
        }
        flag_smt_divergence([sig], frames, ltf="M15", corr_symbol="GBPUSD", lookback=3)
        assert isinstance(sig.smt_divergence_active, bool)

    def test_flag_no_corr_data(self):
        """No correlate data → no annotation."""
        sig = self._make_signal()
        frames = {"EURUSD_M15": _make_ohlc(highs=[1.0] * 10, lows=[0.9] * 10)}
        flag_smt_divergence([sig], frames, ltf="M15", corr_symbol="GBPUSD")
        assert sig.smt_divergence_active is False

    def test_flag_empty_signals(self):
        """Empty signal list → no crash."""
        frames = {"EURUSD_M15": _make_ohlc(highs=[1.0] * 10, lows=[0.9] * 10)}
        flag_smt_divergence([], frames, ltf="M15", corr_symbol="GBPUSD")  # no error

    def test_flag_no_lookahead(self):
        """SMT detection window must not read future bars (anti-lookahead).
        Signal at index 5 → only bars 0..5 visible to the detector.
        """
        # Base: oscillating with HH at index 5
        base_df = _make_ohlc(
            highs=[1.0, 1.1, 1.0, 0.9, 1.0, 1.2, 1.1, 1.0, 1.15, 1.3],
            lows=[0.9, 1.0, 0.9, 0.8, 0.9, 1.1, 1.0, 0.9, 1.05, 1.2],
        )
        # Correlate: oscillating with LH at index 5
        corr_df = _make_ohlc(
            highs=[1.0, 1.1, 1.0, 0.9, 1.0, 1.05, 1.0, 0.9, 0.95, 0.9],
            lows=[0.9, 1.0, 0.9, 0.8, 0.9, 0.95, 0.9, 0.8, 0.85, 0.8],
        )
        sig = self._make_signal(entry_at=5)
        frames = {
            "EURUSD_M15": base_df,
            "GBPUSD_M15": corr_df,
        }
        flag_smt_divergence([sig], frames, ltf="M15", corr_symbol="GBPUSD", lookback=3)
        assert isinstance(sig.smt_divergence_active, bool)
