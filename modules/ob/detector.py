from __future__ import annotations

import pandas as pd


def detect_order_blocks(frame: pd.DataFrame) -> pd.DataFrame:
    """Detect simple order blocks from impulse candles."""
    data = frame.copy().reset_index(drop=True)
    data["ob_bullish"] = False
    data["ob_bearish"] = False

    body = (data["close"] - data["open"]).abs()
    candle_range = (data["high"] - data["low"]).replace(0.0, pd.NA)
    body_ratio = (body / candle_range).fillna(0.0)

    bearish_candle = data["close"] < data["open"]
    bullish_candle = data["close"] > data["open"]
    strong_impulse = body_ratio > 0.7

    bullish_followthrough = data["close"].shift(-1) > data["high"]
    bearish_followthrough = data["close"].shift(-1) < data["low"]

    data["ob_bullish"] = bearish_candle & strong_impulse & bullish_followthrough
    data["ob_bearish"] = bullish_candle & strong_impulse & bearish_followthrough

    data["ob_top"] = pd.NA
    data["ob_bottom"] = pd.NA
    data.loc[data["ob_bullish"] | data["ob_bearish"], "ob_top"] = data["high"]
    data.loc[data["ob_bullish"] | data["ob_bearish"], "ob_bottom"] = data["low"]
    return data
