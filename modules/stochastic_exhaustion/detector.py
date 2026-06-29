from __future__ import annotations

import numpy as np
import pandas as pd

from modules.indicators import add_rsi
from modules.stochastic_exhaustion.config import StochasticExhaustionConfig


def _count_oversold_cycles(rsi: pd.Series, threshold: float, min_cycles: int) -> pd.Series:
    oversold = (rsi < threshold).astype(int)
    transitions = oversold.diff().fillna(0)
    cycle_start = (transitions == 1).astype(int)
    return cycle_start.rolling(window=len(rsi), min_periods=1).sum()


def _count_overbought_cycles(rsi: pd.Series, threshold: float, min_cycles: int) -> pd.Series:
    overbought = (rsi > threshold).astype(int)
    transitions = overbought.diff().fillna(0)
    cycle_start = (transitions == 1).astype(int)
    return cycle_start.rolling(window=len(rsi), min_periods=1).sum()


def _price_no_new_lows(low: pd.Series, lookback: int, epsilon: float) -> pd.Series:
    rolling_min = low.rolling(lookback, min_periods=lookback).min().shift(1)
    return (low >= rolling_min - epsilon).astype(int)


def _price_no_new_highs(high: pd.Series, lookback: int, epsilon: float) -> pd.Series:
    rolling_max = high.rolling(lookback, min_periods=lookback).max().shift(1)
    return (high <= rolling_max + epsilon).astype(int)


def _price_compression(low: pd.Series, high: pd.Series, atr: pd.Series, ratio: float, period: int) -> pd.Series:
    range_pct = (high - low) / atr.replace(0.0, np.nan)
    compressed = (range_pct < ratio).astype(int)
    return compressed.rolling(period, min_periods=period).min()


def detect_exhaustion(
    frame: pd.DataFrame,
    config: StochasticExhaustionConfig | None = None,
) -> pd.DataFrame:
    if config is None:
        config = StochasticExhaustionConfig()

    data = frame.copy()
    data["rsi"] = add_rsi(data, config.rsi_period)

    data["exhaustion_bearish"] = False
    data["exhaustion_bullish"] = False
    data["exhaustion_cycles"] = 0
    data["exhaustion_score"] = 0
    data["price_compressed"] = False

    if len(data) < config.lookback + config.rsi_period:
        return data

    bull_cycles = _count_oversold_cycles(data["rsi"], config.oversold_threshold, config.min_cycles)
    bear_cycles = _count_overbought_cycles(data["rsi"], config.overbought_threshold, config.min_cycles)
    data["exhaustion_cycles"] = np.maximum(bull_cycles, bear_cycles)

    no_new_lows = _price_no_new_lows(data["low"], config.lookback, config.epsilon)
    no_new_highs = _price_no_new_highs(data["high"], config.lookback, config.epsilon)

    data["price_compressed"] = _price_compression(
        data["low"], data["high"], data["atr"], config.compression_ratio, 3
    ).astype(bool)

    rsi_bull = data["rsi"] < config.oversold_threshold
    rsi_bear = data["rsi"] > config.overbought_threshold
    cycles_met_bull = (bull_cycles >= config.min_cycles) & rsi_bull
    cycles_met_bear = (bear_cycles >= config.min_cycles) & rsi_bear
    divergence_bull = no_new_lows.astype(bool) & rsi_bull
    divergence_bear = no_new_highs.astype(bool) & rsi_bear

    data["exhaustion_bullish"] = cycles_met_bull & divergence_bull & data["price_compressed"]
    data["exhaustion_bearish"] = cycles_met_bear & divergence_bear & data["price_compressed"]

    data["exhaustion_score"] = (
        (bull_cycles >= config.min_cycles).astype(int)
        + (bear_cycles >= config.min_cycles).astype(int)
        + no_new_lows
        + no_new_highs
        + data["price_compressed"].astype(int)
    )

    return data
