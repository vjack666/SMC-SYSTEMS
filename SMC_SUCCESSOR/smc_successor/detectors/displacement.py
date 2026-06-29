from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DisplacementConfig:
    body_atr_multiple: float = 1.5
    wick_threshold: float = 0.4
    atr_period: int = 14


def _compute_atr(frame: pd.DataFrame, period: int) -> pd.Series:
    high_low = frame["high"] - frame["low"]
    high_prev_close = (frame["high"] - frame["close"].shift(1)).abs()
    low_prev_close = (frame["low"] - frame["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def detect_displacement(
    frame: pd.DataFrame,
    config: DisplacementConfig | None = None,
) -> pd.DataFrame:
    if config is None:
        config = DisplacementConfig()

    data = frame.copy()
    data["atr"] = _compute_atr(data, config.atr_period)

    body = (data["close"] - data["open"]).abs()
    candle_range = (data["high"] - data["low"]).replace(0, pd.NA)
    body_ratio = (body / candle_range).fillna(0.0)
    wick_ratio = 1.0 - body_ratio

    bullish_body = data["close"] > data["open"]
    bearish_body = data["close"] < data["open"]
    atr = data["atr"].fillna(1e-9)

    large_body = body > atr * config.body_atr_multiple
    small_wick = wick_ratio < config.wick_threshold

    data["displacement_bullish"] = bullish_body & large_body & small_wick
    data["displacement_bearish"] = bearish_body & large_body & small_wick

    data["displacement_magnitude"] = np.where(
        data["displacement_bullish"] | data["displacement_bearish"],
        body / atr,
        0.0,
    )

    return data
