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

    ob_highs = data["ob_top"].where(data["ob_bullish"] | data["ob_bearish"]).ffill().infer_objects()
    ob_lows = data["ob_bottom"].where(data["ob_bullish"] | data["ob_bearish"]).ffill().infer_objects()
    mask = ob_highs.notna()
    high_dist = (data["close"] - ob_highs).abs()
    low_dist = (data["close"] - ob_lows).abs()
    data["ob_distance"] = np.where(mask, np.minimum(high_dist, low_dist), 0.0)

    # --- Item E: invalidacion + envejecimiento ---
    data["ob_status"], data["ob_age"] = _track_ob_validity(data, max_age=20)

    return data


def _track_ob_validity(data: pd.DataFrame, max_age: int) -> tuple[pd.Series, pd.Series]:
    n = len(data)
    status = pd.Series(["none"] * n, index=data.index, dtype=object)
    age = pd.Series([0] * n, index=data.index, dtype=int)
    last_dir = 0
    last_top = float("nan")
    last_bottom = float("nan")
    last_idx = -1
    active = False
    close = data["close"].to_numpy()
    ob_bull = data["ob_bullish"].to_numpy()
    ob_bear = data["ob_bearish"].to_numpy()
    ob_top = data["ob_top"].to_numpy()
    ob_bottom = data["ob_bottom"].to_numpy()
    for i in range(1, n):
        bull = bool(ob_bull[i])
        bear = bool(ob_bear[i])
        if bull or bear:
            last_dir = 1 if bull else -1
            last_top = float(ob_top[i]) if pd.notna(ob_top[i]) else last_top
            last_bottom = float(ob_bottom[i]) if pd.notna(ob_bottom[i]) else last_bottom
            last_idx, active = i, True
        if active:
            age.iloc[i] = i - last_idx
            broke = (
                (last_dir == 1 and close[i] < last_bottom)   # OB alcista: cierra debajo
                or (last_dir == -1 and close[i] > last_top)  # OB bajista: cierra encima
            )
            if broke:
                status.iloc[i], active = "invalidated", False
            elif age.iloc[i] > max_age:
                status.iloc[i], active = "aged", False
            else:
                status.iloc[i] = "active"
    return status, age
