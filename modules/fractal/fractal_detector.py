from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class FractalConfig:
    window: int = 2


def detect_fractals(frame: pd.DataFrame, config: FractalConfig | None = None) -> pd.DataFrame:
    """Detect simple Bill Williams style fractals."""
    if config is None:
        config = FractalConfig()

    if config.window < 2:
        raise ValueError("window must be >= 2")

    data = frame.copy().reset_index(drop=True)
    data["fractal_high"] = False
    data["fractal_low"] = False

    left = config.window
    right = config.window

    for idx in range(left, len(data) - right):
        center_high = float(data.iloc[idx]["high"])
        center_low = float(data.iloc[idx]["low"])

        left_highs = data.iloc[idx - left:idx]["high"]
        right_highs = data.iloc[idx + 1:idx + 1 + right]["high"]
        left_lows = data.iloc[idx - left:idx]["low"]
        right_lows = data.iloc[idx + 1:idx + 1 + right]["low"]

        if center_high > float(left_highs.max()) and center_high > float(right_highs.max()):
            data.at[idx, "fractal_high"] = True
        if center_low < float(left_lows.min()) and center_low < float(right_lows.min()):
            data.at[idx, "fractal_low"] = True

    return data
