from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier


@dataclass(frozen=True)
class BosMlConfig:
    horizon_bars: int = 8
    min_move_atr: float = 0.6


FEATURE_COLUMNS: List[str] = [
    "atr",
    "tick_volume",
    "range_ratio",
    "body_ratio",
    "close_to_break",
    "ema_spread",
]


def _engineer_features(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    candle_range = (data["high"] - data["low"]).replace(0.0, np.nan)
    body = (data["close"] - data["open"]).abs()

    data["range_ratio"] = candle_range / data["atr"].replace(0.0, np.nan)
    data["body_ratio"] = body / candle_range
    data["close_to_break"] = (data["close"] - data["bos_level"]).abs() / data["atr"].replace(0.0, np.nan)

    ema_fast = data["close"].ewm(span=20, adjust=False).mean()
    ema_slow = data["close"].ewm(span=50, adjust=False).mean()
    data["ema_spread"] = (ema_fast - ema_slow) / data["atr"].replace(0.0, np.nan)

    data[FEATURE_COLUMNS] = data[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan)
    return data


def build_training_set(frame: pd.DataFrame, config: BosMlConfig | None = None) -> pd.DataFrame:
    if config is None:
        config = BosMlConfig()

    data = _engineer_features(frame)
    future_close = data["close"].shift(-config.horizon_bars)
    move = (future_close - data["close"]) / data["atr"].replace(0.0, np.nan)

    bullish_success = (data["bos_direction"] == 1) & (move >= config.min_move_atr)
    bearish_success = (data["bos_direction"] == -1) & (move <= -config.min_move_atr)
    data["target"] = (bullish_success | bearish_success).astype(int)

    return data


def train_model(frame: pd.DataFrame) -> GradientBoostingClassifier:
    events = frame.loc[frame["bos_direction"] != 0].dropna(subset=FEATURE_COLUMNS + ["target"])
    if len(events) < 200:
        raise ValueError("Not enough BOS events to train model (minimum 200).")

    x = events[FEATURE_COLUMNS]
    y = events["target"].astype(int)

    model = GradientBoostingClassifier(random_state=42)
    model.fit(x, y)
    return model


def score_events(frame: pd.DataFrame, model: GradientBoostingClassifier) -> pd.DataFrame:
    data = _engineer_features(frame)
    probs = pd.Series(np.nan, index=data.index, dtype=float)

    events = data.loc[data["bos_direction"] != 0].dropna(subset=FEATURE_COLUMNS)
    if not events.empty:
        probs.loc[events.index] = model.predict_proba(events[FEATURE_COLUMNS])[:, 1]

    data["ml_confidence"] = probs.to_numpy()
    return data