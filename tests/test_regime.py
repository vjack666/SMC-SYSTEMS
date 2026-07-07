from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from regime import RegimeConfig, classify_row, detect_regimes


def _frame(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
) -> pd.DataFrame:
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes})


class TestDetectRegimes:
    def test_adds_market_regime_column(self):
        df = _frame(
            opens=[100.0] * 80, highs=[102.0] * 80, lows=[98.0] * 80, closes=[101.0] * 80,
        )
        df["atr"] = 1.0
        df["atr_ratio"] = 1.0
        df["ema_fast"] = 100.5
        df["ema_slow"] = 100.0
        result = detect_regimes(df)
        assert "market_regime" in result.columns

    def test_high_vol_detected(self):
        closes = list(np.linspace(100.0, 110.0, 30))
        df = _frame(
            opens=[c - 0.5 for c in closes],
            highs=[c + 5.0 for c in closes],
            lows=[c - 5.0 for c in closes],
            closes=closes,
        )
        df["atr"] = 5.0
        df["atr_ratio"] = 2.0
        df["ema_fast"] = df["close"].ewm(span=10, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=30, adjust=False).mean()
        result = detect_regimes(df, RegimeConfig(high_vol_atr_ratio=1.5, chaotic_efficiency_threshold=0.01))
        high_vol = (result["market_regime"] == "HIGH_VOL").sum()
        assert high_vol > 0

    def test_low_vol_detected(self):
        df = _frame(
            opens=[100.0] * 30, highs=[101.0] * 30, lows=[99.0] * 30, closes=[100.0] * 30,
        )
        df["atr"] = 0.5
        df["atr_ratio"] = 0.5
        df["ema_fast"] = 100.0
        df["ema_slow"] = 100.0
        result = detect_regimes(df, RegimeConfig(low_vol_atr_ratio=0.6))
        low_vol = (result["market_regime"] == "LOW_VOL").sum()
        assert low_vol > 0

    def test_trending_detected(self):
        n = 80
        closes = np.linspace(100.0, 110.0, n)
        df = _frame(
            opens=closes - 0.2, highs=closes + 0.5, lows=closes - 0.5, closes=list(closes),
        )
        df["atr"] = 1.0
        df["atr_ratio"] = 1.0
        df["ema_fast"] = df["close"].ewm(span=10, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=30, adjust=False).mean()
        result = detect_regimes(df, RegimeConfig(trend_slope_threshold=0.01, high_vol_atr_ratio=3.0))
        assert "TRENDING" in result["market_regime"].unique()

    def test_chaotic_detected(self):
        highs = [100.0 + np.random.default_rng(42).uniform(-5, 5) for _ in range(30)]
        lows = [h - 10.0 for h in highs]
        closes = [(h + l) / 2 + np.random.default_rng(42 + i).uniform(-2, 2) for i, (h, l) in enumerate(zip(highs, lows))]
        df = _frame(
            opens=closes, highs=highs, lows=lows, closes=closes,
        )
        df["atr"] = 8.0
        df["atr_ratio"] = 2.0
        df["ema_fast"] = 100.0
        df["ema_slow"] = 100.0
        result = detect_regimes(df, RegimeConfig(high_vol_atr_ratio=1.5, chaotic_efficiency_threshold=0.5))
        assert "CHAOTIC" in result["market_regime"].unique()

    def test_adds_derived_columns(self):
        df = _frame(
            opens=[100.0] * 30, highs=[102.0] * 30, lows=[98.0] * 30, closes=[101.0] * 30,
        )
        df["atr"] = 1.0
        df["atr_ratio"] = 1.0
        df["ema_fast"] = 100.5
        df["ema_slow"] = 100.0
        result = detect_regimes(df)
        assert "ema_slope" in result.columns
        assert "directional_efficiency" in result.columns
        assert "range_compression" in result.columns

    def test_classify_row_various(self):
        cfg = RegimeConfig()
        row_chaotic = pd.Series({"atr_ratio": 2.0, "ema_slope": 0.1, "directional_efficiency": 0.05, "range_compression": 1.0})
        assert classify_row(row_chaotic, cfg) == "CHAOTIC"

        row_high_vol = pd.Series({"atr_ratio": 2.0, "ema_slope": 0.1, "directional_efficiency": 0.5, "range_compression": 1.0})
        assert classify_row(row_high_vol, cfg) == "HIGH_VOL"

        row_low_vol = pd.Series({"atr_ratio": 0.5, "ema_slope": 0.1, "directional_efficiency": 0.5, "range_compression": 1.0})
        assert classify_row(row_low_vol, cfg) == "LOW_VOL"

        row_trending = pd.Series({"atr_ratio": 1.0, "ema_slope": 0.5, "directional_efficiency": 0.5, "range_compression": 1.0})
        assert classify_row(row_trending, cfg) == "TRENDING"

        row_ranging = pd.Series({"atr_ratio": 1.0, "ema_slope": 0.0, "directional_efficiency": 0.5, "range_compression": 1.0})
        assert classify_row(row_ranging, cfg) == "RANGING"

    def test_classify_row_missing_fields(self):
        row = pd.Series({})
        result = classify_row(row)
        assert result in ("TRENDING", "RANGING", "HIGH_VOL", "LOW_VOL", "CHAOTIC")

    def test_missing_columns_does_not_crash(self):
        df = pd.DataFrame({"close": [100.0, 101.0, 102.0]})
        result = detect_regimes(df)
        assert "market_regime" in result.columns
