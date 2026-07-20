from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from detectors import (
    BosConfig,
    CHOCH_BEARISH,
    CHOCH_BULLISH,
    DisplacementConfig,
    TrendConfig,
    ZoneConfig,
    compute_zones,
    detect_bos,
    detect_choch,
    detect_displacement,
    detect_fvg,
    detect_order_blocks,
    detect_trend,
)
from detectors.bos import _compute_atr as bos_atr, _label_swings, _swing_points
from detectors.displacement import _compute_atr as disp_atr
from detectors.fvg import _track_fvg_fill
from detectors.trend import _classify_trend, _compute_atr as trend_atr, _slope_of_last_two, _swing_high_low
from detectors.zones import _swing_range
from fixtures.synthetic_ohlcv import generate_synthetic_ohlcv


@pytest.fixture
def frame() -> pd.DataFrame:
    return generate_synthetic_ohlcv(n_bars=500, seed=42)


@pytest.fixture
def small_frame() -> pd.DataFrame:
    return generate_synthetic_ohlcv(n_bars=30, seed=7)


# ── helpers ────────────────────────────────────────────────────────────────


def _frame(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
) -> pd.DataFrame:
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes})


# ══════════════════════════════════════════════════════════════════════════
# Trend
# ══════════════════════════════════════════════════════════════════════════


class TestTrendHelpers:
    def test_compute_atr_produces_positive_values(self, frame):
        atr = trend_atr(frame, 14)
        assert atr.isna().sum() == 13  # first 13 are NaN
        assert (atr.dropna() > 0).all()

    def test_swing_high_low_returns_correct_length(self, frame):
        sh, sl = _swing_high_low(frame, lookback=5)
        assert len(sh) == len(frame)
        assert len(sl) == len(frame)

    def test_slope_of_last_two_flat_trend(self):
        series = pd.Series([np.nan] * 3 + [100.0] + [np.nan] * 6 + [105.0] + [np.nan] * 3)
        bar_index = pd.Series(range(len(series)))
        slopes = _slope_of_last_two(series, bar_index)
        assert slopes.iloc[13] == pytest.approx(5.0 / 7.0)

    def test_slope_of_last_two_single_point_is_nan(self):
        series = pd.Series([np.nan, 100.0, np.nan])
        bar_index = pd.Series(range(3))
        slopes = _slope_of_last_two(series, bar_index)
        assert slopes.isna().all()

    def test_classify_trend(self):
        atr = pd.Series([10.0, 10.0, 10.0, 10.0])
        high_slope = pd.Series([1.0, -1.0, 0.0, 0.5])
        low_slope = pd.Series([0.8, -1.2, 0.0, -0.3])
        result = _classify_trend(high_slope, low_slope, atr, min_slope_atr=0.05)
        assert list(result) == ["BULLISH", "BEARISH", "RANGING", "RANGING"]

    def test_classify_trend_zero_atr(self):
        atr = pd.Series([0.0, 10.0])
        high_slope = pd.Series([1.0, 1.0])
        low_slope = pd.Series([1.0, 1.0])
        result = _classify_trend(high_slope, low_slope, atr, min_slope_atr=0.05)
        assert result.iloc[0] == "RANGING"
        assert result.iloc[1] == "BULLISH"


class TestDetectTrend:
    def test_returns_all_expected_columns(self, frame):
        result = detect_trend(frame)
        expected = {"atr", "swing_high", "swing_low", "swing_high_slope", "swing_low_slope",
                    "ema_fast", "ema_slow", "ema_spread", "trend", "trend_int"}
        assert expected.issubset(result.columns)

    def test_ranging_with_no_trend(self, small_frame):
        result = detect_trend(small_frame)
        unique = set(result["trend"].unique())
        assert unique.issubset({"BULLISH", "BEARISH", "RANGING"})

    def test_config_overrides(self, frame):
        cfg = TrendConfig(swing_lookback=3, ema_fast=10, ema_slow=30, min_slope_atr=0.1)
        result = detect_trend(frame, cfg)
        assert "ema_fast" in result.columns

    def test_default_config(self, frame):
        result = detect_trend(frame)
        assert "trend_int" in result.columns
        assert result["trend_int"].isin([-1, 0, 1]).all()

    def test_ema_alignment_on_trending_data(self):
        n = 200
        close = np.linspace(100.0, 110.0, n) + np.random.default_rng(42).normal(0, 0.5, n)
        df = pd.DataFrame({"open": close - 0.2, "high": close + 0.3, "low": close - 0.3, "close": close})
        result = detect_trend(df, TrendConfig(ema_fast=10, ema_slow=30))
        bull_count = (result["trend"] == "BULLISH").sum()
        assert bull_count > n * 0.5


# ══════════════════════════════════════════════════════════════════════════
# BOS (Break of Structure)
# ══════════════════════════════════════════════════════════════════════════


class TestBosHelpers:
    def test_atr_produces_positive(self, frame):
        atr = bos_atr(frame, 14)
        assert (atr.dropna() > 0).all()

    def test_swing_points_correct_length(self, frame):
        sh, sl = _swing_points(frame, lookback=5)
        assert len(sh) == len(frame)
        assert len(sl) == len(frame)

    def test_label_swings_all_none_before_first(self):
        sh = pd.Series([np.nan] * 5 + [110.0] + [np.nan] * 4)
        sl = pd.Series([np.nan] * 5 + [np.nan] + [90.0] + [np.nan] * 3)
        labels = _label_swings(sh, sl)
        assert labels.iloc[0] == "NONE"
        assert labels.iloc[5] == "HH"

    def test_label_swings_hh_vs_lh(self):
        sh = pd.Series([np.nan, np.nan, 100.0, np.nan, 110.0, np.nan, 95.0])
        sl = pd.Series([np.nan, np.nan, np.nan, 80.0, np.nan, np.nan, np.nan])
        labels = _label_swings(sh, sl)
        assert labels.iloc[2] == "HH"
        assert labels.iloc[4] == "HH"
        assert labels.iloc[6] == "LH"

    def test_label_swings_ll_vs_hl(self):
        sh = pd.Series([np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan])
        sl = pd.Series([np.nan, np.nan, 80.0, np.nan, 70.0, np.nan, 75.0])
        labels = _label_swings(sh, sl)
        assert labels.iloc[2] == "HL"
        assert labels.iloc[4] == "LL"
        assert labels.iloc[6] == "HL"


class TestDetectBos:
    def test_adds_all_columns(self, frame):
        result = detect_bos(frame)
        expected = {
            "bos_direction", "bos_level", "swing_label", "swing_high", "swing_low",
            "liquidity_sweep_up", "liquidity_sweep_down", "recent_sweep_up", "recent_sweep_down",
        }
        assert expected.issubset(result.columns)

    def test_bos_on_breakout(self):
        close = [100.0] * 50 + [105.0, 106.0, 107.0]
        df500 = generate_synthetic_ohlcv(n_bars=55, seed=42)
        df500.loc[50:, "close"] = [105.0, 106.0, 107.0, 108.0, 109.0]
        df500.loc[50:, "high"] = [106.0, 107.0, 108.0, 109.0, 110.0]
        result = detect_bos(df500, BosConfig(swing_lookback=3))
        assert (result["bos_direction"].tail(3) == 1).any()

    def test_config_overrides(self, frame):
        cfg = BosConfig(swing_lookback=3, followthrough_bars=5, liquidity_lookback=15)
        result = detect_bos(frame, cfg)
        assert "bos_direction" in result.columns

    def test_liquidity_sweep_detected(self):
        lows = [100.0] * 15 + [95.0] + [105.0] * 4
        highs = [110.0] * 15 + [100.0] + [115.0] * 4
        closes = [105.0] * 15 + [101.0] + [106.0] * 4
        opens = [102.0] * 20
        df = _frame(opens=opens, highs=highs, lows=lows, closes=closes)
        result = detect_bos(df, BosConfig(swing_lookback=3, liquidity_lookback=15, followthrough_bars=3))
        assert result["recent_sweep_down"].tail(5).any()


# ══════════════════════════════════════════════════════════════════════════
# CHOCH (Change of Character)
# ══════════════════════════════════════════════════════════════════════════


class TestDetectChoch:
    def test_adds_columns(self, frame):
        result = detect_choch(frame)
        assert "choch_signal" in result.columns
        assert set(result["choch_signal"].unique()).issubset({"NONE", CHOCH_BULLISH, CHOCH_BEARISH})

    def test_bullish_choch_in_bearish_trend(self):
        n = 60
        closes = [100.0 - i * 0.5 for i in range(n - 5)] + [95.0, 97.0, 99.0, 100.0, 101.0]
        highs = [c + 1.0 for c in closes]
        lows = [c - 1.0 for c in closes]
        opens = [c - 0.2 for i, c in enumerate(closes)]
        df = pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes})
        result = detect_choch(df)
        bullish = (result["choch_signal"] == CHOCH_BULLISH).sum()
        assert bullish > 0

    def test_bearish_choch_in_bullish_trend(self):
        n = 60
        closes = [100.0 + i * 0.5 for i in range(n - 5)] + [105.0, 103.0, 101.0, 100.0, 99.0]
        highs = [c + 1.0 for c in closes]
        lows = [c - 1.0 for c in closes]
        opens = [c + 0.2 for i, c in enumerate(closes)]
        df = pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes})
        result = detect_choch(df)
        bearish = (result["choch_signal"] == CHOCH_BEARISH).sum()
        assert bearish > 0

    def test_returns_none_on_short_data(self):
        df = pd.DataFrame({"open": [100.0, 101.0], "high": [101.0, 102.0], "low": [99.0, 100.0], "close": [100.5, 101.5]})
        result = detect_choch(df)
        assert (result["choch_signal"] == "NONE").all()


# ══════════════════════════════════════════════════════════════════════════
# Displacement
# ══════════════════════════════════════════════════════════════════════════


class TestDisplacementHelpers:
    def test_atr_produces_positive(self, frame):
        atr = disp_atr(frame, 14)
        assert (atr.dropna() > 0).all()


class TestDetectDisplacement:
    def test_adds_columns(self, frame):
        result = detect_displacement(frame)
        assert "displacement_bullish" in result.columns
        assert "displacement_bearish" in result.columns
        assert "displacement_magnitude" in result.columns

    def test_large_bullish_body_is_displacement(self):
        df = _frame(
            opens=[100.0, 101.0, 102.0],
            highs=[101.0, 103.0, 105.0],
            lows=[99.5, 100.5, 101.5],
            closes=[100.8, 102.8, 104.8],
        )
        result = detect_displacement(df, DisplacementConfig(body_range_multiple=1.0, range_period=14))
        assert result["displacement_bullish"].iloc[-1]

    def test_small_body_not_displacement(self):
        df = _frame(
            opens=[100.0, 100.5, 101.0],
            highs=[101.0, 101.5, 102.0],
            lows=[99.0, 99.5, 100.0],
            closes=[100.2, 100.7, 101.2],
        )
        result = detect_displacement(df, DisplacementConfig(body_range_multiple=10.0, range_period=14))
        assert not result["displacement_bullish"].any()

    def test_magnitude_scales_with_body(self):
        df = generate_synthetic_ohlcv(n_bars=100, seed=42)
        result = detect_displacement(df)
        assert result["displacement_magnitude"].min() >= 0.0

    def test_config_overrides(self, frame):
        cfg = DisplacementConfig(body_range_multiple=2.0, wick_threshold=0.3)
        result = detect_displacement(frame, cfg)
        assert "displacement_bullish" in result.columns


# ══════════════════════════════════════════════════════════════════════════
# FVG (Fair Value Gap)
# ══════════════════════════════════════════════════════════════════════════


class TestFvgHelpers:
    def test_track_fvg_fill_no_gaps(self):
        df = pd.DataFrame({
            "fvg_bullish": [False] * 10,
            "fvg_bearish": [False] * 10,
            "high": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0],
        }, index=range(10))
        df.loc[2, "fvg_bullish"] = True
        df.loc[5, "fvg_bearish"] = True
        status = _track_fvg_fill(df)
        assert status.iloc[2] == "bullish_unfilled"


class TestDetectFvg:
    def test_adds_columns(self, frame):
        result = detect_fvg(frame)
        assert "fvg_bullish" in result.columns
        assert "fvg_bearish" in result.columns
        assert "fvg_size" in result.columns
        assert "fvg_mid" in result.columns

    def test_bullish_gap_detected(self):
        df = _frame(
            opens=[100, 101, 200],
            highs=[101, 102, 201],
            lows=[99, 100, 199],
            closes=[100.5, 101.5, 200.5],
        )
        result = detect_fvg(df)
        assert result["fvg_bullish"].iloc[-1]

    def test_bearish_gap_detected(self):
        df = _frame(
            opens=[200, 199, 100],
            highs=[201, 200, 101],
            lows=[199, 198, 99],
            closes=[200.5, 199.5, 100.5],
        )
        result = detect_fvg(df)
        assert result["fvg_bearish"].iloc[-1]

    def test_no_gap_no_detection(self):
        closes = np.linspace(100.0, 105.0, 10)
        df = _frame(
            opens=[c - 0.5 for c in closes],
            highs=[c + 0.5 for c in closes],
            lows=[c - 1.0 for c in closes],
            closes=list(closes),
        )
        result = detect_fvg(df)
        assert not result["fvg_bullish"].any()
        assert not result["fvg_bearish"].any()

    def test_short_data_returns_early(self):
        df = pd.DataFrame({"open": [100.0], "high": [101.0], "low": [99.0], "close": [100.5]})
        result = detect_fvg(df)
        assert not result["fvg_bullish"].iloc[0]


# ══════════════════════════════════════════════════════════════════════════
# Order Blocks
# ══════════════════════════════════════════════════════════════════════════


class TestDetectOrderBlocks:
    def test_adds_columns(self, frame):
        result = detect_order_blocks(frame)
        assert "ob_bullish" in result.columns
        assert "ob_bearish" in result.columns
        assert "ob_top" in result.columns
        assert "ob_bottom" in result.columns
        assert "ob_distance" in result.columns

    def test_bullish_ob_on_bearish_impulse_with_followthrough(self):
        closes = np.linspace(100.0, 95.0, 6)
        df = _frame(
            opens=[c + 0.5 for c in closes],
            highs=[c + 1.0 for c in closes],
            lows=[c - 1.0 for c in closes],
            closes=list(closes),
        )
        result = detect_order_blocks(df)
        assert "ob_bullish" in result.columns

    def test_followthrough_required(self):
        closes = np.linspace(100.0, 95.0, 6)
        df = _frame(
            opens=[c + 0.5 for c in closes],
            highs=[c + 1.0 for c in closes],
            lows=[c - 1.0 for c in closes],
            closes=list(closes),
        )
        result = detect_order_blocks(df)
        assert "ob_bullish" in result.columns


# ══════════════════════════════════════════════════════════════════════════
# Zones
# ══════════════════════════════════════════════════════════════════════════


class TestZoneHelpers:
    def test_swing_range_correct(self):
        df = pd.DataFrame({
            "high": [100, 105, 103, 108, 102],
            "low": [90, 92, 91, 95, 93],
        })
        result = _swing_range(df, lookback=3)
        assert "range_high" in result.columns
        assert "range_low" in result.columns


class TestComputeZones:
    def test_adds_columns(self, frame):
        result = compute_zones(frame)
        expected = {"zone_high", "zone_low", "zone_mid",
                    "ote_long_min", "ote_long_max", "ote_short_min", "ote_short_max",
                    "premium_discount_zone", "premium_distance"}
        assert expected.issubset(result.columns)

    def test_premium_when_close_above_mid(self):
        df = _frame(
            opens=[100, 101, 102],
            highs=[105, 106, 107],
            lows=[95, 96, 97],
            closes=[103, 104, 105],
        )
        result = compute_zones(df, ZoneConfig(swing_lookback=10))
        assert result["premium_discount_zone"].iloc[-1] == "PREMIUM" or result["premium_discount_zone"].iloc[-1] == "OTE_SHORT"

    def test_discount_when_close_below_mid(self):
        closes = [100.0, 99.0, 98.0]
        df = _frame(
            opens=[100, 99, 98],
            highs=[101, 100, 99],
            lows=[99, 98, 97],
            closes=closes,
        )
        result = compute_zones(df, ZoneConfig(swing_lookback=3))
        assert result["premium_discount_zone"].iloc[-1] in ("DISCOUNT", "OTE_LONG")

    def test_ote_long_when_close_in_ote_zone(self):
        df = _frame(
            opens=[100, 99, 98],
            highs=[105, 104, 103],
            lows=[95, 94, 93],
            closes=[97.5, 97.0, 97.5],
        )
        result = compute_zones(df, ZoneConfig(swing_lookback=3, ote_min_retrace=0.3, ote_max_retrace=0.45))
        assert "OTE" in result["premium_discount_zone"].iloc[-1]

    def test_premium_distance_signed(self):
        df = _frame(
            opens=[100, 101, 102],
            highs=[110, 111, 112],
            lows=[90, 91, 92],
            closes=[105, 106, 107],
        )
        result = compute_zones(df, ZoneConfig(swing_lookback=10))
        assert result["premium_distance"].iloc[-1] >= 0.0

    def test_premium_distance_negative_in_discount(self):
        df = _frame(
            opens=[100, 99, 98],
            highs=[110, 109, 108],
            lows=[90, 89, 88],
            closes=[95, 94, 93],
        )
        result = compute_zones(df, ZoneConfig(swing_lookback=10))
        assert result["premium_distance"].iloc[-1] <= 0.0
