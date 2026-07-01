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


def _upthrust(data: pd.DataFrame, i: int, dist_high_idx: int, config: WyckoffConfig) -> bool:
    if dist_high_idx < 0 or i <= dist_high_idx:
        return False
    range_since = i - dist_high_idx
    if range_since > 15:
        return False
    resistance = data.iloc[dist_high_idx]["high"]
    break_above = data.iloc[i]["high"] > resistance + config.spring_depth_atr * data.iloc[i]["atr"]
    close_below = data.iloc[i]["close"] < data.iloc[i]["open"]
    return break_above and close_below


def _sign_of_weakness(data: pd.DataFrame, i: int, dist_low_idx: int, vol_ma: pd.Series, config: WyckoffConfig) -> bool:
    if dist_low_idx < 0 or i <= dist_low_idx:
        return False
    range_since = i - dist_low_idx
    if range_since > 20:
        return False
    below_dist_low = data.iloc[i]["close"] < data.iloc[dist_low_idx]["low"]
    vol_ok = data.iloc[i]["tick_volume"] >= vol_ma.iloc[i] * config.volume_threshold
    range_atr = (data.iloc[i]["high"] - data.iloc[i]["low"]) >= data.iloc[i]["atr"] * config.sos_min_atr
    return below_dist_low and vol_ok and range_atr


def _last_point_supply(data: pd.DataFrame, i: int, dist_high_idx: int, sow_idx: int, vol_ma: pd.Series, config: WyckoffConfig) -> bool:
    if dist_high_idx < 0 or sow_idx < 0 or i <= sow_idx:
        return False
    range_since_sow = i - sow_idx
    if range_since_sow > 15:
        return False
    below_dist_high = data.iloc[i]["high"] < data.iloc[dist_high_idx]["high"]
    bounce_range = (data.iloc[i]["high"] - data.iloc[i]["low"]) <= data.iloc[i]["atr"] * config.lps_max_atr
    low_vol = data.iloc[i]["tick_volume"] <= vol_ma.iloc[i] * config.volume_threshold
    return below_dist_high and bounce_range and low_vol


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
    return "ACCUMULATION_A" if has_sc else "NONE"


def _detect_distribution_phase(data: pd.DataFrame, idx: int, config: WyckoffConfig) -> str:
    if idx < config.phase_lookback:
        return "NONE"
    window = data.iloc[idx - config.phase_lookback : idx + 1]
    has_ut = window["wyckoff_upthrust"].any()
    has_sow = window["wyckoff_sow"].any()
    has_lpsy = window["wyckoff_lpsy"].any()

    if has_ut and has_sow and has_lpsy:
        return "DISTRIBUTION_E"
    if has_ut and has_sow:
        return "DISTRIBUTION_D"
    if has_ut:
        return "DISTRIBUTION_C"
    return "DISTRIBUTION_B" if (has_sow or has_lpsy) else "NONE"


def _detect_markup_phase(data: pd.DataFrame, idx: int, config: WyckoffConfig) -> bool:
    if idx < config.swing_lookback + 2:
        return False
    window = data.iloc[idx - config.swing_lookback * 2 : idx + 1]
    if "swing_label" not in window.columns:
        return False
    labels = window["swing_label"].dropna()
    has_hh = any("HH" in str(l) for l in labels)
    has_hl = any("HL" in str(l) for l in labels)
    bias = str(window["macro_direction"].iloc[-1]) if "macro_direction" in window.columns else "RANGING"
    return bias == "BULLISH" and has_hh and has_hl


def _detect_markdown_phase(data: pd.DataFrame, idx: int, config: WyckoffConfig) -> bool:
    if idx < config.swing_lookback + 2:
        return False
    window = data.iloc[idx - config.swing_lookback * 2 : idx + 1]
    if "swing_label" not in window.columns:
        return False
    labels = window["swing_label"].dropna()
    has_lh = any("LH" in str(l) for l in labels)
    has_ll = any("LL" in str(l) for l in labels)
    bias = str(window["macro_direction"].iloc[-1]) if "macro_direction" in window.columns else "RANGING"
    return bias == "BEARISH" and has_lh and has_ll


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
    data["wyckoff_upthrust"] = False
    data["wyckoff_sow"] = False
    data["wyckoff_lpsy"] = False
    data["wyckoff_phase"] = "NONE"
    data["wyckoff_accumulation"] = False
    data["wyckoff_distribution"] = False
    data["wyckoff_markup"] = False
    data["wyckoff_markdown"] = False

    if len(data) < max(config.swing_lookback * 2 + 2, config.phase_lookback):
        return data

    if "atr" not in data.columns:
        data["atr"] = 1.0
    vol_ma = data["tick_volume"].rolling(20).mean().fillna(1.0)

    last_sc_idx = -1
    last_ar_idx = -1
    last_sos_idx = -1
    last_dist_high_idx = -1
    last_dist_low_idx = -1
    last_sow_idx = -1

    for i in range(config.swing_lookback + 2, len(data)):
        hi = data.iloc[i]["high"]
        lo = data.iloc[i]["low"]
        if last_dist_high_idx < 0 or hi > data.iloc[last_dist_high_idx]["high"]:
            last_dist_high_idx = i
        if last_dist_low_idx < 0 or lo < data.iloc[last_dist_low_idx]["low"]:
            last_dist_low_idx = i

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

        if last_dist_high_idx >= 0 and _upthrust(data, i, last_dist_high_idx, config):
            data.at[data.index[i], "wyckoff_upthrust"] = True
            continue

        if last_dist_low_idx >= 0 and _sign_of_weakness(data, i, last_dist_low_idx, vol_ma, config):
            data.at[data.index[i], "wyckoff_sow"] = True
            last_sow_idx = i
            continue

        if last_sow_idx >= 0 and _last_point_supply(data, i, last_dist_high_idx, last_sow_idx, vol_ma, config):
            data.at[data.index[i], "wyckoff_lpsy"] = True
            continue

    for i in range(len(data)):
        phase = _detect_accumulation_phase(data, i, config)
        dist_phase = _detect_distribution_phase(data, i, config)
        is_markup = _detect_markup_phase(data, i, config)
        is_markdown = _detect_markdown_phase(data, i, config)

        if phase != "NONE":
            data.at[data.index[i], "wyckoff_phase"] = phase
            data.at[data.index[i], "wyckoff_accumulation"] = True
        elif dist_phase != "NONE":
            data.at[data.index[i], "wyckoff_phase"] = dist_phase
            data.at[data.index[i], "wyckoff_distribution"] = True
        elif is_markup:
            data.at[data.index[i], "wyckoff_phase"] = "MARKUP"
            data.at[data.index[i], "wyckoff_markup"] = True
        elif is_markdown:
            data.at[data.index[i], "wyckoff_phase"] = "MARKDOWN"
            data.at[data.index[i], "wyckoff_markdown"] = True

    return data
