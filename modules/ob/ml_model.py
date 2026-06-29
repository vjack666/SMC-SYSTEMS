from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier


FEATURE_COLUMNS = ["ob_bullish", "ob_bearish", "ob_height_atr", "atr_ratio", "body_ratio"]


def _compute_atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = frame["high"] - frame["low"]
    high_prev_close = (frame["high"] - frame["close"].shift(1)).abs()
    low_prev_close = (frame["low"] - frame["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def build_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy().reset_index(drop=True)
    data["atr"] = _compute_atr(data)
    data["ob_bullish"] = data["ob_bullish"].astype(int)
    data["ob_bearish"] = data["ob_bearish"].astype(int)
    ob_height = (data["high"] - data["low"]).abs()
    data["ob_height_atr"] = ob_height / data["atr"].replace(0.0, np.nan)
    rng = (data["high"] - data["low"]).replace(0.0, np.nan)
    data["body_ratio"] = ((data["close"] - data["open"]).abs() / rng).fillna(0.0)
    data["atr_ratio"] = (data["atr"] / data["atr"].rolling(20).mean().replace(0.0, np.nan)).fillna(0.0)
    return data


def build_labels(frame: pd.DataFrame) -> pd.Series:
    data = frame.copy()
    future = data["close"].shift(-8)
    direction = data["ob_bullish"].astype(int) - data["ob_bearish"].astype(int)
    move = direction * (future - data["close"])
    return (move >= (0.4 * data["atr"].replace(0.0, np.nan))).astype(int)


def train_model(frame: pd.DataFrame) -> RandomForestClassifier:
    data = build_feature_frame(frame)
    data["target"] = build_labels(data)
    data = data.dropna(subset=FEATURE_COLUMNS + ["target"])
    if len(data) < 200:
        raise ValueError("Not enough rows for OB model training.")

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=9,
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
