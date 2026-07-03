from __future__ import annotations

import numpy as np
import pandas as pd


def detect_order_blocks(frame: pd.DataFrame) -> pd.DataFrame:
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

    ob_highs = data["ob_top"].where(data["ob_bullish"] | data["ob_bearish"]).ffill().infer_objects(copy=False)
    ob_lows = data["ob_bottom"].where(data["ob_bullish"] | data["ob_bearish"]).ffill().infer_objects(copy=False)
    mask = ob_highs.notna()
    high_dist = (data["close"] - ob_highs).abs()
    low_dist = (data["close"] - ob_lows).abs()
    data["ob_distance"] = np.where(mask, np.minimum(high_dist, low_dist), 0.0)
    return data
