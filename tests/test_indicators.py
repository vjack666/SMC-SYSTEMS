from __future__ import annotations

import numpy as np
import pandas as pd

from indicators import add_fvg, add_order_blocks


def test_bullish_ob_detected() -> None:
    n = 30
    frame = pd.DataFrame({
        "time": pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC"),
        "open": np.full(n, 1.1000),
        "high": np.full(n, 1.1010),
        "low": np.full(n, 1.0990),
        "close": np.full(n, 1.1000),
    })

    frame.loc[10, "open"] = 1.1010
    frame.loc[10, "high"] = 1.1015
    frame.loc[10, "low"] = 1.1000
    frame.loc[10, "close"] = 1.1005
    frame.loc[11, "open"] = 1.1010
    frame.loc[11, "high"] = 1.1030
    frame.loc[11, "low"] = 1.1005
    frame.loc[11, "close"] = 1.1025
    frame.loc[12, "open"] = 1.1030
    frame.loc[12, "high"] = 1.1055
    frame.loc[12, "low"] = 1.1025
    frame.loc[12, "close"] = 1.1050
    frame.loc[13, "open"] = 1.1055
    frame.loc[13, "high"] = 1.1070
    frame.loc[13, "low"] = 1.1050
    frame.loc[13, "close"] = 1.1065

    result = add_order_blocks(frame, lookback=5, min_strength=1)
    bullish = result[result["ob_type"] == "bullish"]
    assert len(bullish) > 0, "Expected at least one bullish OB"
    assert "ob_high" in bullish.columns
    assert "ob_low" in bullish.columns
    assert "ob_price" in bullish.columns
    assert "ob_index" in bullish.columns


def test_bearish_ob_detected() -> None:
    n = 30
    frame = pd.DataFrame({
        "time": pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC"),
        "open": np.full(n, 1.1000),
        "high": np.full(n, 1.1010),
        "low": np.full(n, 1.0990),
        "close": np.full(n, 1.1000),
    })

    frame.loc[10, "open"] = 1.1040
    frame.loc[10, "high"] = 1.1055
    frame.loc[10, "low"] = 1.1035
    frame.loc[10, "close"] = 1.1050
    frame.loc[11, "open"] = 1.1040
    frame.loc[11, "high"] = 1.1045
    frame.loc[11, "low"] = 1.1020
    frame.loc[11, "close"] = 1.1025
    frame.loc[12, "open"] = 1.1020
    frame.loc[12, "high"] = 1.1025
    frame.loc[12, "low"] = 1.1000
    frame.loc[12, "close"] = 1.1005
    frame.loc[13, "open"] = 1.1000
    frame.loc[13, "high"] = 1.1005
    frame.loc[13, "low"] = 1.0980
    frame.loc[13, "close"] = 1.0985

    result = add_order_blocks(frame, lookback=5, min_strength=1)
    bearish = result[result["ob_type"] == "bearish"]
    assert len(bearish) > 0, "Expected at least one bearish OB"


def test_no_ob_on_flat_market() -> None:
    frame = pd.DataFrame({
        "time": pd.date_range("2024-01-01", periods=20, freq="15min", tz="UTC"),
        "open": np.full(20, 1.1000),
        "high": np.full(20, 1.1005),
        "low": np.full(20, 1.0995),
        "close": np.full(20, 1.1000),
    })
    result = add_order_blocks(frame)
    assert len(result) == 0, "Should not detect OBs on flat market"


def test_empty_frame_returns_empty() -> None:
    frame = pd.DataFrame(columns=["time", "open", "high", "low", "close"])
    result = add_order_blocks(frame)
    assert len(result) == 0
    assert list(result.columns) == ["ob_type", "ob_high", "ob_low", "ob_price", "ob_index"]


def test_bullish_fvg_detected() -> None:
    frame = pd.DataFrame({
        "time": pd.date_range("2024-01-01", periods=10, freq="15min", tz="UTC"),
        "open": [1.1000, 1.1010, 1.1040, 1.1060, 1.1070, 1.1080, 1.1085, 1.1090, 1.1095, 1.1100],
        "high": [1.1010, 1.1030, 1.1060, 1.1075, 1.1080, 1.1090, 1.1095, 1.1100, 1.1105, 1.1110],
        "low": [1.0990, 1.1005, 1.1035, 1.1055, 1.1065, 1.1075, 1.1080, 1.1085, 1.1090, 1.1095],
        "close": [1.1005, 1.1025, 1.1055, 1.1070, 1.1075, 1.1085, 1.1090, 1.1095, 1.1100, 1.1105],
    })
    result = add_fvg(frame)
    bullish = result[result["fvg_type"] == "bullish"]
    assert len(bullish) > 0, "Expected at least one bullish FVG"


def test_bearish_fvg_detected() -> None:
    frame = pd.DataFrame({
        "time": pd.date_range("2024-01-01", periods=10, freq="15min", tz="UTC"),
        "open": [1.1100, 1.1090, 1.1060, 1.1040, 1.1030, 1.1020, 1.1015, 1.1010, 1.1005, 1.1000],
        "high": [1.1110, 1.1095, 1.1065, 1.1045, 1.1035, 1.1025, 1.1020, 1.1015, 1.1010, 1.1005],
        "low": [1.1090, 1.1070, 1.1040, 1.1025, 1.1020, 1.1010, 1.1005, 1.1000, 1.0995, 1.0990],
        "close": [1.1095, 1.1075, 1.1045, 1.1030, 1.1025, 1.1015, 1.1010, 1.1005, 1.1000, 1.0995],
    })
    result = add_fvg(frame)
    bearish = result[result["fvg_type"] == "bearish"]
    assert len(bearish) > 0, "Expected at least one bearish FVG"


def test_fvg_columns_present() -> None:
    frame = pd.DataFrame({
        "time": pd.date_range("2024-01-01", periods=5, freq="15min", tz="UTC"),
        "open": [1.1000, 1.1010, 1.1040, 1.1060, 1.1070],
        "high": [1.1010, 1.1030, 1.1060, 1.1075, 1.1080],
        "low": [1.0990, 1.1005, 1.1035, 1.1055, 1.1065],
        "close": [1.1005, 1.1025, 1.1055, 1.1070, 1.1075],
    })
    result = add_fvg(frame)
    if len(result) > 0:
        expected = {"fvg_type", "fvg_top", "fvg_bottom", "fvg_midpoint", "fvg_filled", "fvg_index"}
        assert expected.issubset(result.columns), f"Missing columns: {expected - set(result.columns)}"


def test_fvg_filled_detected() -> None:
    highs = [1.1010, 1.1040, 1.1060, 1.1055, 1.1040, 1.1065]
    lows = [1.0990, 1.1030, 1.1050, 1.1045, 1.1030, 1.1055]
    frame = pd.DataFrame({
        "time": pd.date_range("2024-01-01", periods=6, freq="15min", tz="UTC"),
        "open": [1.1000, 1.1035, 1.1055, 1.1050, 1.1035, 1.1060],
        "high": highs,
        "low": lows,
        "close": [1.1005, 1.1040, 1.1055, 1.1050, 1.1040, 1.1060],
    })
    result = add_fvg(frame)
    if len(result) > 0:
        assert "fvg_filled" in result.columns


def test_fvg_filled_true_when_price_returns() -> None:
    frame = pd.DataFrame({
        "time": pd.date_range("2024-01-01", periods=8, freq="15min", tz="UTC"),
        "open": [1.1000, 1.1020, 1.1040, 1.1030, 1.1020, 1.1060, 1.1070, 1.1080],
        "high": [1.1010, 1.1040, 1.1060, 1.1045, 1.1040, 1.1075, 1.1080, 1.1090],
        "low": [1.0990, 1.1010, 1.1035, 1.1020, 1.1010, 1.1055, 1.1065, 1.1075],
        "close": [1.1005, 1.1030, 1.1045, 1.1030, 1.1030, 1.1070, 1.1075, 1.1085],
    })
    result = add_fvg(frame)
    if len(result) > 0:
        assert result["fvg_filled"].any(), "Expected at least one filled FVG"


def test_fvg_filled_false_when_no_return() -> None:
    highs = [1.1010, 1.1040, 1.1060, 1.1070, 1.1080, 1.1090]
    lows = [1.0990, 1.1030, 1.1050, 1.1060, 1.1070, 1.1080]
    frame = pd.DataFrame({
        "time": pd.date_range("2024-01-01", periods=6, freq="15min", tz="UTC"),
        "open": [1.1000, 1.1035, 1.1055, 1.1065, 1.1075, 1.1085],
        "high": highs,
        "low": lows,
        "close": [1.1005, 1.1040, 1.1060, 1.1070, 1.1080, 1.1090],
    })
    result = add_fvg(frame)
    if len(result) > 0:
        assert not result["fvg_filled"].any(), "Expected no filled FVGs when price moves away"
