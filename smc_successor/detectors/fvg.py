from __future__ import annotations

import numpy as np
import pandas as pd


def detect_fvg(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy().reset_index(drop=True)
    data["fvg_bullish"] = False
    data["fvg_bearish"] = False

    if len(data) < 3:
        return data

    prev2_high = data["high"].shift(2)
    prev2_low = data["low"].shift(2)

    data["fvg_bullish"] = data["low"] > prev2_high
    data["fvg_bearish"] = data["high"] < prev2_low

    data["fvg_size"] = np.where(
        data["fvg_bullish"],
        (data["low"] - prev2_high).clip(lower=0),
        np.where(
            data["fvg_bearish"],
            (prev2_low - data["high"]).clip(lower=0),
            0.0,
        ),
    )

    data["fvg_mid"] = pd.NA
    bullish_mid = (data["low"] + prev2_high) / 2.0
    bearish_mid = (data["high"] + prev2_low) / 2.0
    data.loc[data["fvg_bullish"], "fvg_mid"] = bullish_mid[data["fvg_bullish"]]
    data.loc[data["fvg_bearish"], "fvg_mid"] = bearish_mid[data["fvg_bearish"]]

    data["fvg_fill_status"] = _track_fvg_fill(data)
    return data


def _track_fvg_fill(data: pd.DataFrame) -> pd.Series:
    n = len(data)
    status = pd.Series(["none"] * n, index=data.index)
    active_bull_top: float | None = None
    active_bull_bot: float | None = None
    active_bear_top: float | None = None
    active_bear_bot: float | None = None
    bull_unfilled = False
    bear_unfilled = False

    for i in range(2, n):
        row = data.iloc[i]
        prev2_high = data.iloc[i - 2]["high"]
        prev2_low = data.iloc[i - 2]["low"]

        if row["fvg_bullish"]:
            active_bull_top = float(prev2_high)
            active_bull_bot = float(row["low"])
            bull_unfilled = True

        if row["fvg_bearish"]:
            active_bear_top = float(row["high"])
            active_bear_bot = float(prev2_low)
            bear_unfilled = True

        if bull_unfilled and active_bull_top is not None and float(row["low"]) <= active_bull_top:
            bull_unfilled = False

        if bear_unfilled and active_bear_bot is not None and float(row["high"]) >= active_bear_bot:
            bear_unfilled = False

        if bull_unfilled:
            status.iloc[i] = "bullish_unfilled"
        elif bear_unfilled:
            status.iloc[i] = "bearish_unfilled"
        elif row["fvg_bullish"] or row["fvg_bearish"]:
            status.iloc[i] = "just_created"
        else:
            status.iloc[i] = "none"

    return status
