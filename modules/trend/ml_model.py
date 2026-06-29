from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier


@dataclass(frozen=True)
class TrendMlConfig:
    horizon_bars: int = 20
    min_move_atr: float = 0.5
    train_size: int = 2500
    test_size: int = 800
    step_size: int = 1600


FEATURE_COLUMNS: List[str] = [
    "atr_ratio",
    "swing_amplitude_atr",
    "candle_body_ratio_10",
    "distance_from_last_swing_atr",
    "volume_trend_slope_10",
    "d1_h4_agreement",
    "micro_state_encoded",
    "consecutive_structure_count",
]

DEFAULT_MODEL_PATH = Path("modules/trend/models/trend_classifier.pkl")


def _compute_atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = frame["high"] - frame["low"]
    high_prev_close = (frame["high"] - frame["close"].shift(1)).abs()
    low_prev_close = (frame["low"] - frame["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _trend_slope(series: pd.Series) -> float:
    if len(series) < 2:
        return 0.0
    x = np.arange(len(series), dtype=float)
    y = series.astype(float).to_numpy()
    coeffs = np.polyfit(x, y, deg=1)
    return float(coeffs[0])


def extract_features(features: dict[str, float | int | bool]) -> dict[str, float]:
    """Normalize a raw feature dictionary to the exact model schema."""
    normalized: dict[str, float] = {}
    for key in FEATURE_COLUMNS:
        value = features.get(key, 0.0)
        normalized[key] = float(value)
    return normalized


def build_feature_frame(
    m15_frame: pd.DataFrame,
    macro_trend: pd.Series,
    micro_state: pd.Series,
    agreement: pd.Series,
    consecutive_count: pd.Series,
) -> pd.DataFrame:
    """Build per-bar feature frame for ML confidence training/inference."""
    data = m15_frame.copy().reset_index(drop=True)
    data["atr"] = _compute_atr(data, period=14)

    atr_avg20 = data["atr"].rolling(20).mean().replace(0.0, np.nan)
    data["atr_ratio"] = data["atr"] / atr_avg20

    swing_high = data["high"].rolling(10).max()
    swing_low = data["low"].rolling(10).min()
    data["swing_amplitude_atr"] = (swing_high - swing_low) / data["atr"].replace(0.0, np.nan)

    candle_range = (data["high"] - data["low"]).replace(0.0, np.nan)
    body_ratio = (data["close"] - data["open"]).abs() / candle_range
    data["candle_body_ratio_10"] = body_ratio.rolling(10).mean()

    last_swing_high = swing_high.shift(1)
    last_swing_low = swing_low.shift(1)
    dist_high = (data["close"] - last_swing_high).abs()
    dist_low = (data["close"] - last_swing_low).abs()
    data["distance_from_last_swing_atr"] = (
        np.minimum(dist_high, dist_low) / data["atr"].replace(0.0, np.nan)
    )

    if "tick_volume" in data.columns:
        vol = data["tick_volume"].astype(float)
    else:
        vol = pd.Series(0.0, index=data.index)
    data["volume_trend_slope_10"] = vol.rolling(10).apply(_trend_slope, raw=False)

    micro_map = {"CONTINUATION": 1.0, "PULLBACK": 0.0, "UNCLEAR": -1.0}
    data["micro_state"] = micro_state.astype(str)
    data["d1_h4_agreement"] = agreement.astype(float)
    data["micro_state_encoded"] = micro_state.map(micro_map).fillna(-1.0).astype(float)
    data["consecutive_structure_count"] = consecutive_count.astype(float)
    data["macro_trend"] = macro_trend

    data[FEATURE_COLUMNS] = data[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan)
    return data


def build_labels(frame: pd.DataFrame, config: TrendMlConfig | None = None) -> pd.Series:
    """Label 1 if trend continues for at least horizon bars, else 0."""
    if config is None:
        config = TrendMlConfig()

    direction = frame["macro_trend"].map({"BULLISH": 1.0, "BEARISH": -1.0}).fillna(0.0)
    future_close = frame["close"].shift(-config.horizon_bars)
    move = direction * (future_close - frame["close"])
    threshold = config.min_move_atr * frame["atr"].replace(0.0, np.nan)
    labels = (move >= threshold).astype(int)
    labels[direction == 0.0] = 0
    return labels


def train_walk_forward(
    feature_frame: pd.DataFrame,
    config: TrendMlConfig | None = None,
) -> tuple[RandomForestClassifier, pd.Series]:
    """Train RandomForest with walk-forward validation and return OOS confidence."""
    if config is None:
        config = TrendMlConfig()

    data = feature_frame.copy()
    data["target"] = build_labels(data, config)
    data = data.dropna(subset=FEATURE_COLUMNS + ["target"])

    if len(data) < 200:
        raise ValueError("Not enough rows for trend model training (minimum 200).")

    confidence = pd.Series(np.nan, index=data.index, dtype=float)
    model = RandomForestClassifier(
        n_estimators=60,
        max_depth=10,
        min_samples_leaf=2,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=1,
    )

    start = 0
    while True:
        train_end = start + config.train_size
        test_end = train_end + config.test_size
        if test_end > len(data):
            break

        train_slice = data.iloc[start:train_end]
        test_slice = data.iloc[train_end:test_end]

        y_train = train_slice["target"].astype(int)
        if y_train.nunique() < 2:
            confidence.loc[test_slice.index] = 0.5
            start += config.step_size
            continue

        model.fit(train_slice[FEATURE_COLUMNS], y_train)
        probs = predict_positive_proba(model, test_slice[FEATURE_COLUMNS])
        confidence.loc[test_slice.index] = probs
        start += config.step_size

    # Fit final model on all data so runtime inference can use a single artifact.
    y_full = data["target"].astype(int)
    model.fit(data[FEATURE_COLUMNS], y_full)
    return model, confidence


def predict_positive_proba(model: RandomForestClassifier, x: pd.DataFrame) -> np.ndarray:
    """Return probability for class=1 even when classifier was trained on one class."""
    probs = model.predict_proba(x)
    classes = getattr(model, "classes_", np.array([], dtype=int))
    if len(classes) == 0:
        return np.full(len(x), 0.5, dtype=float)

    classes_list = [int(item) for item in classes.tolist()]
    if 1 in classes_list:
        idx = classes_list.index(1)
        return probs[:, idx]

    # Model only saw class 0 during training.
    return np.zeros(len(x), dtype=float)


def save_model(model: RandomForestClassifier, path: Path = DEFAULT_MODEL_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = {
        "model": model,
        "feature_columns": FEATURE_COLUMNS,
    }
    joblib.dump(payload, path)


def load_model(path: Path = DEFAULT_MODEL_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Trend model not found: {path}")
    payload = joblib.load(path)
    if not isinstance(payload, dict) or "model" not in payload:
        raise ValueError("Invalid trend model payload.")
    return payload


def predict_confidence(features: dict) -> float:
    """Predict trend confidence in [0.0, 1.0] using saved model artifact."""
    payload = load_model()
    model: RandomForestClassifier = payload["model"]
    feature_columns: list[str] = payload["feature_columns"]

    normalized = extract_features(features)
    x = pd.DataFrame([[normalized[item] for item in feature_columns]], columns=feature_columns)
    proba = predict_positive_proba(model, x)[0]
    return float(proba)
