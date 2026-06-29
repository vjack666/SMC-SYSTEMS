from __future__ import annotations

import numpy as np
import pandas as pd


def detect_fvg(frame: pd.DataFrame) -> pd.DataFrame:
    """Detect 3-candle fair value gaps with zone metadata."""
    data = frame.copy().reset_index(drop=True)
    data["fvg_bullish"] = False
    data["fvg_bearish"] = False
    data["fvg_zone_low"] = np.nan
    data["fvg_zone_high"] = np.nan
    data["fvg_direction"] = 0

    if len(data) < 3:
        return data

    prev2_high = data["high"].shift(2)
    prev2_low = data["low"].shift(2)

    bullish = data["low"] > prev2_high
    bearish = data["high"] < prev2_low

    data["fvg_bullish"] = bullish
    data["fvg_bearish"] = bearish

    data.loc[bullish, "fvg_zone_low"] = prev2_high[bullish]
    data.loc[bullish, "fvg_zone_high"] = data["low"][bullish]
    data.loc[bullish, "fvg_direction"] = 1

    data.loc[bearish, "fvg_zone_low"] = data["high"][bearish]
    data.loc[bearish, "fvg_zone_high"] = prev2_low[bearish]
    data.loc[bearish, "fvg_direction"] = -1

    data["fvg_mid"] = pd.NA
    bullish_mid = (data["low"] + prev2_high) / 2.0
    bearish_mid = (data["high"] + prev2_low) / 2.0
    data.loc[bullish, "fvg_mid"] = bullish_mid[bullish]
    data.loc[bearish, "fvg_mid"] = bearish_mid[bearish]
    return data
