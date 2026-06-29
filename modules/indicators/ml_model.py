from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from modules.indicators.core import add_atr, add_ema, add_rsi


FEATURE_COLUMNS = ["ema_spread_atr", "rsi", "atr_ratio", "momentum_5", "body_ratio"]


def build_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy().reset_index(drop=True)
    data["atr"] = add_atr(data, 14)
    ema_fast = add_ema(data, 20)
    ema_slow = add_ema(data, 50)
    data["ema_spread_atr"] = (ema_fast - ema_slow) / data["atr"].replace(0.0, np.nan)
    data["rsi"] = add_rsi(data, 14).fillna(50.0)
    data["atr_ratio"] = (data["atr"] / data["atr"].rolling(20).mean().replace(0.0, np.nan)).fillna(0.0)
    data["momentum_5"] = (data["close"] - data["close"].shift(5)) / data["atr"].replace(0.0, np.nan)
    rng = (data["high"] - data["low"]).replace(0.0, np.nan)
    data["body_ratio"] = ((data["close"] - data["open"]).abs() / rng).fillna(0.0)
    return data


def build_labels(frame: pd.DataFrame) -> pd.Series:
    data = frame.copy()
    direction = np.sign(data["ema_spread_atr"]).replace(0.0, 1.0)
    future = data["close"].shift(-8)
    move = direction * (future - data["close"])
    return (move >= (0.35 * data["atr"].replace(0.0, np.nan))).astype(int)


def train_model(frame: pd.DataFrame) -> RandomForestClassifier:
    data = build_feature_frame(frame)
    data["target"] = build_labels(data)
    data = data.dropna(subset=FEATURE_COLUMNS + ["target"])
    if len(data) < 200:
        raise ValueError("Not enough rows for Indicators model training.")

    model = RandomForestClassifier(
        n_estimators=80,
        max_depth=9,
        min_samples_leaf=2,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=1,
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
