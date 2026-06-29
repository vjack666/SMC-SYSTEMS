from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BosConfig:
    swing_lookback: int = 5
    atr_period: int = 14
    followthrough_bars: int = 8
    liquidity_lookback: int = 20


def _compute_atr(frame: pd.DataFrame, period: int) -> pd.Series:
    high_low = frame["high"] - frame["low"]
    high_prev_close = (frame["high"] - frame["close"].shift(1)).abs()
    low_prev_close = (frame["low"] - frame["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _swing_points(frame: pd.DataFrame, lookback: int) -> tuple[pd.Series, pd.Series]:
    window = lookback * 2 + 1
    rolling_high = frame["high"].rolling(window=window, center=True)
    rolling_low = frame["low"].rolling(window=window, center=True)

    swing_high = frame["high"].where(frame["high"] == rolling_high.max())
    swing_low = frame["low"].where(frame["low"] == rolling_low.min())
    return swing_high.ffill(), swing_low.ffill()


def detect_bos(frame: pd.DataFrame, config: BosConfig | None = None) -> pd.DataFrame:
    if config is None:
        config = BosConfig()

    data = frame.copy()
    data["atr"] = _compute_atr(data, config.atr_period)
    data["swing_high"] , data["swing_low"] = _swing_points(data, config.swing_lookback)

    prior_low = data["low"].rolling(config.liquidity_lookback).min().shift(1)
    prior_high = data["high"].rolling(config.liquidity_lookback).max().shift(1)
    data["liquidity_sweep_down"] = (data["low"] < prior_low) & (data["close"] > prior_low)
    data["liquidity_sweep_up"] = (data["high"] > prior_high) & (data["close"] < prior_high)

    data["recent_sweep_down"] = (
        data["liquidity_sweep_down"].astype(int).rolling(config.followthrough_bars, min_periods=1).max().astype(bool)
    )
    data["recent_sweep_up"] = (
        data["liquidity_sweep_up"].astype(int).rolling(config.followthrough_bars, min_periods=1).max().astype(bool)
    )

    bullish_break = data["close"] > data["swing_high"].shift(1)
    bearish_break = data["close"] < data["swing_low"].shift(1)

    data["bos_direction"] = np.select(
        [bullish_break, bearish_break],
        [1, -1],
        default=0,
    )

    data["bos_level"] = np.where(
        data["bos_direction"] == 1,
        data["swing_high"].shift(1),
        np.where(data["bos_direction"] == -1, data["swing_low"].shift(1), np.nan),
    )

    return data