from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

TrendLabel = Literal["BULLISH", "BEARISH", "RANGING"]


@dataclass(frozen=True)
class TrendConfig:
    swing_lookback: int = 5       # bars each side for swing detection
    atr_period: int = 14
    ema_fast: int = 20
    ema_slow: int = 50
    min_slope_atr: float = 0.01   # minimum swing slope in ATR units to qualify as trending


def _compute_atr(frame: pd.DataFrame, period: int) -> pd.Series:
    high_low = frame["high"] - frame["low"]
    high_prev_close = (frame["high"] - frame["close"].shift(1)).abs()
    low_prev_close = (frame["low"] - frame["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _swing_high_low(frame: pd.DataFrame, lookback: int) -> tuple[pd.Series, pd.Series]:
    """Return swing high / swing low series (NaN where not a pivot)."""
    window = lookback * 2 + 1
    rolling_max = frame["high"].rolling(window=window, center=True).max()
    rolling_min = frame["low"].rolling(window=window, center=True).min()
    swing_high = frame["high"].where(frame["high"] == rolling_max)
    swing_low = frame["low"].where(frame["low"] == rolling_min)
    return swing_high, swing_low


def _slope_of_last_two(series: pd.Series, bar_index: pd.Series) -> pd.Series:
    """
    For each position, compute the slope between the two most recent non-NaN
    values in `series`, normalised by the index distance (bars).
    Returns a float series aligned to the input index.
    """
    slopes = pd.Series(np.nan, index=series.index, dtype=float)
    filled = series.dropna()

    for i in range(1, len(filled)):
        curr_idx = filled.index[i]
        prev_idx = filled.index[i - 1]
        delta_price = float(filled.iloc[i]) - float(filled.iloc[i - 1])
        delta_bars = int(bar_index.loc[curr_idx]) - int(bar_index.loc[prev_idx])
        if delta_bars > 0:
            slopes.loc[curr_idx] = delta_price / delta_bars

    return slopes.ffill()


def _classify_trend(
    swing_high_slope: pd.Series,
    swing_low_slope: pd.Series,
    atr: pd.Series,
    min_slope_atr: float,
) -> pd.Series:
    """
    BULLISH  → swing highs rising AND swing lows rising (HH + HL)
    BEARISH  → swing highs falling AND swing lows falling (LH + LL)
    RANGING  → anything else
    """
    atr_safe = atr.replace(0.0, np.nan)
    threshold = atr_safe * min_slope_atr

    bullish = (swing_high_slope > threshold) & (swing_low_slope > threshold)
    bearish = (swing_high_slope < -threshold) & (swing_low_slope < -threshold)

    trend = pd.Series("RANGING", index=swing_high_slope.index, dtype=object)
    trend[bullish] = "BULLISH"
    trend[bearish] = "BEARISH"
    return trend


def detect_trend(
    frame: pd.DataFrame,
    config: TrendConfig | None = None,
) -> pd.DataFrame:
    """
    Add trend columns to a single-timeframe DataFrame.

    New columns added:
    - ``atr``               : Average True Range
    - ``swing_high``        : Most recent swing high value (forward-filled)
    - ``swing_low``         : Most recent swing low value (forward-filled)
    - ``swing_high_slope``  : Slope between last two swing highs (price / bar)
    - ``swing_low_slope``   : Slope between last two swing lows (price / bar)
    - ``ema_fast``          : Fast EMA
    - ``ema_slow``          : Slow EMA
    - ``ema_spread``        : (ema_fast − ema_slow) / atr  — normalised momentum
    - ``trend``             : "BULLISH" | "BEARISH" | "RANGING"
    - ``trend_int``         : 1 / -1 / 0  (numeric encoding of trend)
    """
    if config is None:
        config = TrendConfig()

    data = frame.copy().reset_index(drop=True)
    bar_index = pd.Series(data.index, index=data.index)

    data["atr"] = _compute_atr(data, config.atr_period)
    raw_sh, raw_sl = _swing_high_low(data, config.swing_lookback)

    data["swing_high"] = raw_sh.ffill()
    data["swing_low"] = raw_sl.ffill()

    data["swing_high_slope"] = _slope_of_last_two(raw_sh, bar_index)
    data["swing_low_slope"] = _slope_of_last_two(raw_sl, bar_index)

    data["ema_fast"] = data["close"].ewm(span=config.ema_fast, adjust=False).mean()
    data["ema_slow"] = data["close"].ewm(span=config.ema_slow, adjust=False).mean()
    data["ema_spread"] = (data["ema_fast"] - data["ema_slow"]) / data["atr"].replace(0.0, np.nan)

    data["trend"] = _classify_trend(
        data["swing_high_slope"],
        data["swing_low_slope"],
        data["atr"],
        config.min_slope_atr,
    )
    data["trend_int"] = data["trend"].map({"BULLISH": 1, "BEARISH": -1, "RANGING": 0}).astype(int)

    return data
