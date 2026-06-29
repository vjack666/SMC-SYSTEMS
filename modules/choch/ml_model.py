from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from modules.choch.detector import CHOCH_BEARISH, CHOCH_BULLISH


FEATURE_COLUMNS = [
    "choch_bullish",
    "choch_bearish",
    "atr_ratio",
    "body_ratio",
    "range_ratio",
]


@dataclass(frozen=True)
class ChochMlConfig:
    horizon: int = 10
    min_move_atr: float = 0.5


def _compute_atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = frame["high"] - frame["low"]
    high_prev_close = (frame["high"] - frame["close"].shift(1)).abs()
    low_prev_close = (frame["low"] - frame["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def build_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy().reset_index(drop=True)
    data["atr"] = _compute_atr(data)
    data["choch_bullish"] = (data["choch_signal"] == CHOCH_BULLISH).astype(int)
    data["choch_bearish"] = (data["choch_signal"] == CHOCH_BEARISH).astype(int)
    rng = (data["high"] - data["low"]).replace(0.0, np.nan)
    data["body_ratio"] = ((data["close"] - data["open"]).abs() / rng).fillna(0.0)
    data["range_ratio"] = (rng / data["atr"].replace(0.0, np.nan)).fillna(0.0)
    data["atr_ratio"] = (data["atr"] / data["atr"].rolling(20).mean().replace(0.0, np.nan)).fillna(0.0)
    return data


def build_labels(frame: pd.DataFrame, config: ChochMlConfig | None = None) -> pd.Series:
    if config is None:
        config = ChochMlConfig()
    data = frame.copy()
    direction = pd.Series(0.0, index=data.index)
    direction[data["choch_signal"] == CHOCH_BULLISH] = 1.0
    direction[data["choch_signal"] == CHOCH_BEARISH] = -1.0
    future = data["close"].shift(-config.horizon)
    move = direction * (future - data["close"])
    threshold = config.min_move_atr * data["atr"].replace(0.0, np.nan)
    labels = (move >= threshold).astype(int)
    labels[direction == 0.0] = 0
    return labels


def train_model(frame: pd.DataFrame) -> RandomForestClassifier:
    data = build_feature_frame(frame)
    data["target"] = build_labels(data)
    data = data.dropna(subset=FEATURE_COLUMNS + ["target"])
    if len(data) < 200:
        raise ValueError("Not enough rows for CHOCH model training.")

    model = RandomForestClassifier(
        n_estimators=120,
        max_depth=10,
        min_samples_leaf=2,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(data[FEATURE_COLUMNS], data["target"].astype(int))
    return model


def score_frame(frame: pd.DataFrame, model: RandomForestClassifier) -> pd.DataFrame:
    data = build_feature_frame(frame)
    scoreable = data.dropna(subset=FEATURE_COLUMNS)
    if scoreable.empty:
        data["ml_confidence"] = 0.0
        return data

    probs = model.predict_proba(scoreable[FEATURE_COLUMNS])
    classes = [int(item) for item in getattr(model, "classes_", np.array([0])).tolist()]
    if 1 in classes:
        idx = classes.index(1)
        conf = probs[:, idx]
    else:
        conf = np.zeros(len(scoreable), dtype=float)

    data["ml_confidence"] = 0.0
    data.loc[scoreable.index, "ml_confidence"] = conf
    return data
