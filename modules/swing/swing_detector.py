from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class SwingConfig:
    left_window: int = 5
    right_window: int = 5
    min_distance: int = 3


def _is_swing_high(frame: pd.DataFrame, idx: int, left: int, right: int) -> bool:
    current = float(frame.iloc[idx]["high"])
    left_max = float(frame.iloc[idx - left:idx]["high"].max())
    right_max = float(frame.iloc[idx + 1:idx + 1 + right]["high"].max())
    return current > left_max and current > right_max


def _is_swing_low(frame: pd.DataFrame, idx: int, left: int, right: int) -> bool:
    current = float(frame.iloc[idx]["low"])
    left_min = float(frame.iloc[idx - left:idx]["low"].min())
    right_min = float(frame.iloc[idx + 1:idx + 1 + right]["low"].min())
    return current < left_min and current < right_min


def detect_swings(frame: pd.DataFrame, config: SwingConfig | None = None) -> pd.DataFrame:
    """Detect swing highs/lows using pivot logic with left/right windows."""
    if config is None:
        config = SwingConfig()

    if config.left_window < 1 or config.right_window < 1:
        raise ValueError("left_window and right_window must be >= 1")

    data = frame.copy().reset_index(drop=True)
    data["swing_high"] = False
    data["swing_low"] = False

    start = config.left_window
    end = len(data) - config.right_window

    last_high_idx = -10_000
    last_low_idx = -10_000

    for idx in range(start, max(start, end)):
        if idx - last_high_idx >= config.min_distance:
            if _is_swing_high(data, idx, config.left_window, config.right_window):
                data.at[idx, "swing_high"] = True
                last_high_idx = idx

        if idx - last_low_idx >= config.min_distance:
            if _is_swing_low(data, idx, config.left_window, config.right_window):
                data.at[idx, "swing_low"] = True
                last_low_idx = idx

    return data
