from __future__ import annotations

import numpy as np
import pandas as pd

from modules.swing.swing_detector import SwingConfig, detect_swings
from modules.wyckoff.config import WyckoffConfig


def _selling_climax(data: pd.DataFrame, i: int, config: WyckoffConfig, vol_ma: pd.Series) -> bool:
    if i < config.swing_lookback + 2:
        return False
    range_size = data.iloc[i]["high"] - data.iloc[i]["low"]
    vol = data.iloc[i]["tick_volume"]
    close_pos = (data.iloc[i]["close"] - data.iloc[i]["low"]) / max(range_size, 1e-9)
    high_vol = vol >= vol_ma.iloc[i] * config.volume_threshold
    wide_spread = range_size >= data.iloc[i]["atr"] * 0.8
    closes_upper = close_pos >= 0.6
    return high_vol and wide_spread and closes_upper


def _automatic_rally(data: pd.DataFrame, i: int, sc_idx: int) -> bool:
    if sc_idx < 0 or i <= sc_idx:
        return False
    sc_low = data.iloc[sc_idx]["low"]
    range_since_sc = i - sc_idx
    if range_since_sc > 10:
        return False
    return data.iloc[i]["high"] > data.iloc[sc_idx]["high"]


def _secondary_test(data: pd.DataFrame, i: int, sc_idx: int, ar_idx: int, vol_ma: pd.Series, config: WyckoffConfig) -> bool:
    if sc_idx < 0 or ar_idx < 0 or i <= ar_idx:
        return False
    range_since_sc = i - sc_idx
    if range_since_sc > 25:
        return False
    near_sc_low = abs(data.iloc[i]["low"] - data.iloc[sc_idx]["low"]) <= data.iloc[i]["atr"] * 0.3
    lower_vol = data.iloc[i]["tick_volume"] <= vol_ma.iloc[i] * config.volume_threshold
    return near_sc_low and lower_vol


def _spring(data: pd.DataFrame, i: int, sc_idx: int, config: WyckoffConfig) -> bool:
    if sc_idx < 0 or i <= sc_idx:
        return False
    range_since_sc = i - sc_idx
    if range_since_sc > 15:
        return False
    sc_low = data.iloc[sc_idx]["low"]
    break_below = data.iloc[i]["low"] < sc_low - config.spring_depth_atr * data.iloc[i]["atr"]
    close_above = data.iloc[i]["close"] > data.iloc[i]["open"]
    return break_below and close_above


def _sign_of_strength(data: pd.DataFrame, i: int, sc_idx: int, vol_ma: pd.Series, config: WyckoffConfig) -> bool:
    if sc_idx < 0 or i <= sc_idx:
        return False
    range_since_sc = i - sc_idx
    if range_since_sc > 20:
        return False
    above_sc_high = data.iloc[i]["close"] > data.iloc[sc_idx]["high"]
    vol_ok = data.iloc[i]["tick_volume"] >= vol_ma.iloc[i] * config.volume_threshold
    range_atr = (data.iloc[i]["high"] - data.iloc[i]["low"]) >= data.iloc[i]["atr"] * config.sos_min_atr
    return above_sc_high and vol_ok and range_atr


def _last_point_support(data: pd.DataFrame, i: int, sc_idx: int, sos_idx: int, vol_ma: pd.Series, config: WyckoffConfig) -> bool:
    if sc_idx < 0 or sos_idx < 0 or i <= sos_idx:
        return False
    range_since_sos = i - sos_idx
    if range_since_sos > 15:
        return False
    above_sc_high = data.iloc[i]["low"] > data.iloc[sc_idx]["high"]
    pullback_range = (data.iloc[i]["high"] - data.iloc[i]["low"]) <= data.iloc[i]["atr"] * config.lps_max_atr
    low_vol = data.iloc[i]["tick_volume"] <= vol_ma.iloc[i] * config.volume_threshold
    return above_sc_high and pullback_range and low_vol


def _detect_accumulation_phase(data: pd.DataFrame, idx: int, config: WyckoffConfig) -> str:
    if idx < config.phase_lookback:
        return "NONE"
    window = data.iloc[idx - config.phase_lookback : idx + 1]
    has_sc = window["wyckoff_sc"].any()
    has_spring = window["wyckoff_spring"].any()
    has_sos = window["wyckoff_sos"].any()
    has_lps = window["wyckoff_lps"].any()

    if has_sc and has_spring and has_sos and has_lps:
        return "ACCUMULATION_E"
    if has_sc and has_spring and has_sos:
        return "ACCUMULATION_D"
    if has_sc and has_spring:
        return "ACCUMULATION_C"
    if has_sc:
        return "ACCUMULATION_B"
    if has_sc:
        return "ACCUMULATION_A"
    return "NONE"


def detect_wyckoff(
    frame: pd.DataFrame,
    config: WyckoffConfig | None = None,
) -> pd.DataFrame:
    if config is None:
        config = WyckoffConfig()

    swing_config = SwingConfig(left_window=config.swing_lookback, right_window=config.swing_lookback)
    data = detect_swings(frame, swing_config)

    data["wyckoff_sc"] = False
    data["wyckoff_ar"] = False
    data["wyckoff_st"] = False
    data["wyckoff_spring"] = False
    data["wyckoff_sos"] = False
    data["wyckoff_lps"] = False
    data["wyckoff_phase"] = "NONE"
    data["wyckoff_accumulation"] = False
    data["wyckoff_distribution"] = False

    if len(data) < max(config.swing_lookback * 2 + 2, config.phase_lookback):
        return data

    if "atr" not in data.columns:
        data["atr"] = 1.0
    vol_ma = data["tick_volume"].rolling(20).mean().fillna(1.0)

    last_sc_idx = -1
    last_ar_idx = -1
    last_sos_idx = -1

    for i in range(config.swing_lookback + 2, len(data)):
        if _selling_climax(data, i, config, vol_ma):
            data.at[data.index[i], "wyckoff_sc"] = True
            last_sc_idx = i
            continue

        if last_sc_idx >= 0 and _automatic_rally(data, i, last_sc_idx):
            data.at[data.index[i], "wyckoff_ar"] = True
            last_ar_idx = i
            continue

        if last_ar_idx >= 0 and _secondary_test(data, i, last_sc_idx, last_ar_idx, vol_ma, config):
            data.at[data.index[i], "wyckoff_st"] = True
            continue

        if last_sc_idx >= 0 and _spring(data, i, last_sc_idx, config):
            data.at[data.index[i], "wyckoff_spring"] = True
            continue

        if last_sc_idx >= 0 and _sign_of_strength(data, i, last_sc_idx, vol_ma, config):
            data.at[data.index[i], "wyckoff_sos"] = True
            last_sos_idx = i
            continue

        if last_sos_idx >= 0 and _last_point_support(data, i, last_sc_idx, last_sos_idx, vol_ma, config):
            data.at[data.index[i], "wyckoff_lps"] = True
            continue

    for i in range(len(data)):
        phase = _detect_accumulation_phase(data, i, config)
        data.at[data.index[i], "wyckoff_phase"] = phase
        if phase != "NONE":
            data.at[data.index[i], "wyckoff_accumulation"] = True

    return data
