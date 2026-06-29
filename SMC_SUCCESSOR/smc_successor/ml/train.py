from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import brier_score_loss, log_loss, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from smc_successor.features import FeatureEngine

DEFAULT_FEATURES_ML: tuple[str, ...] = (
    "bos_detected", "bos_strength",
    "choch_detected", "choch_strength",
    "fvg_detected", "fvg_size", "fvg_fill_status", "fvg_direction",
    "ob_detected", "ob_distance",
    "liquidity_sweep",
    "displacement_magnitude", "displacement_bullish", "displacement_bearish",
    "premium_discount_zone", "premium_distance", "ote_long_min", "ote_short_min",
    "d1_bias", "h4_bias", "trend_alignment", "trend_confidence",
    "directional_efficiency", "range_compression",
    "ema_fast", "ema_slow", "ema_distance", "ema_slope",
    "atr", "atr_ratio",
    "candle_range_vs_atr",
    "volatility_regime",
    "rsi", "rsi_slope",
    "volume_ratio",
    "momentum_strength",
    "spread",
    "market_regime",
    "session", "weekday", "direction",
    "sl_distance", "tp_distance", "rr_ratio",
    "expected_hold_bars",
    "risk_multiplier",
)


@dataclass(frozen=True)
class WalkForwardConfig:
    n_splits: int = 5
    gap: int = 0
    test_size: int | None = None
    calibrate: bool = True
    calibration_method: str = "isotonic"
    features: tuple[str, ...] = DEFAULT_FEATURES_ML
    model_dir: Path = Path("ml/models")
    metrics_path: Path = Path("ml/model_metrics.json")
    importance_path: Path = Path("ml/feature_importance.csv")
    random_state: int = 42


def _pick_estimator() -> tuple[str, Any]:
    try:
        from xgboost import XGBClassifier

        return (
            "xgboost",
            XGBClassifier(
                n_estimators=220,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.9,
                random_state=42,
                objective="binary:logistic",
                eval_metric="logloss",
            ),
        )
    except Exception:
        pass

    try:
        from lightgbm import LGBMClassifier

        return (
            "lightgbm",
            LGBMClassifier(
                n_estimators=280,
                max_depth=-1,
                learning_rate=0.05,
                random_state=42,
            ),
        )
    except Exception:
        pass

    try:
        from catboost import CatBoostClassifier

        return (
            "catboost",
            CatBoostClassifier(
                iterations=260,
                depth=5,
                learning_rate=0.05,
                verbose=False,
                random_state=42,
            ),
        )
    except Exception:
        pass

    from sklearn.ensemble import HistGradientBoostingClassifier

    return (
        "hist_gradient_boosting",
        HistGradientBoostingClassifier(random_state=42),
    )


def _build_feature_pipeline(X: pd.DataFrame) -> ColumnTransformer:
    numeric = [c for c in X.columns if is_numeric_dtype(X[c])]
    categorical = [c for c in X.columns if c not in numeric]

    return ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline([
                    ("imputer", SimpleImputer(strategy="median")),
                    ("scaler", StandardScaler()),
                ]),
                numeric,
            ),
            (
                "cat",
                Pipeline([
                    ("imputer", SimpleImputer(strategy="most_frequent")),
                    ("onehot", OneHotEncoder(handle_unknown="ignore")),
                ]),
                categorical,
            ),
        ]
    )


def _compute_temporal_importance(estimator: Any, feature_names: list[str]) -> pd.DataFrame:
    try:
        importances = estimator.feature_importances_
        imp_rows = [{"feature": fn, "importance": float(imp)} for fn, imp in zip(feature_names, importances)]
    except (AttributeError, ValueError):
        imp_rows = [{"feature": fn, "importance": 0.0} for fn in feature_names]
    return pd.DataFrame(imp_rows).sort_values("importance", ascending=False)


def _build_dataset_from_context(
    context: pd.DataFrame,
    feature_engine: FeatureEngine,
) -> pd.DataFrame:
    df = feature_engine.build_training_dataset(context)
    df["timestamp"] = pd.to_datetime(context["time"] if "time" in context.columns else context.index)
    return df.sort_values("timestamp").reset_index(drop=True)


def train_walk_forward(
    X: pd.DataFrame,
    y: pd.Series,
    cfg: WalkForwardConfig | None = None,
) -> tuple[Any, dict[str, Any], float]:
    if cfg is None:
        cfg = WalkForwardConfig()

    tscv = TimeSeriesSplit(n_splits=cfg.n_splits, gap=cfg.gap, test_size=cfg.test_size)
    model_name, estimator = _pick_estimator()
    preprocess = _build_feature_pipeline(X)

    fold_metrics: list[dict[str, Any]] = []
    pipelines: list[Pipeline] = []

    for fold_idx, (train_idx, val_idx) in enumerate(tscv.split(X)):
        X_train_fold = X.iloc[train_idx]
        y_train_fold = y.iloc[train_idx]
        X_val_fold = X.iloc[val_idx]
        y_val_fold = y.iloc[val_idx]

        if y_train_fold.nunique() < 2:
            continue

        pipe = Pipeline([
            ("preprocess", preprocess),
            ("clf", estimator),
        ])
        pipe.fit(X_train_fold, y_train_fold)

        proba = pipe.predict_proba(X_val_fold)[:, 1]
        pred = (proba >= 0.5).astype(int)
        fold_metrics.append({
            "fold": int(fold_idx),
            "train_samples": int(len(X_train_fold)),
            "val_samples": int(len(X_val_fold)),
            "logloss": float(log_loss(y_val_fold, proba, labels=[0, 1])),
            "roc_auc": float(roc_auc_score(y_val_fold, proba)) if len(np.unique(y_val_fold)) > 1 else 0.5,
            "precision": float(precision_score(y_val_fold, pred, zero_division=0)),
            "recall": float(recall_score(y_val_fold, pred, zero_division=0)),
            "brier_score": float(brier_score_loss(y_val_fold, proba)),
        })
        pipelines.append(pipe)

    if y.nunique() < 2:
        from sklearn.dummy import DummyClassifier
        final_pipe = Pipeline([
            ("preprocess", preprocess),
            ("clf", DummyClassifier(strategy="prior")),
        ])
        final_pipe.fit(X, y)
    else:
        final_pipe = Pipeline([
            ("preprocess", preprocess),
            ("clf", estimator),
        ])
        final_pipe.fit(X, y)

    model_for_inference: Any = final_pipe
    calibration_used = False
    calibration_method = "none"

    if cfg.calibrate and y.nunique() > 1:
        min_class_count = int(y.value_counts().min())
        calibration_cv = min(3, min_class_count)
        if calibration_cv >= 2:
            method = cfg.calibration_method if calibration_cv >= 3 else "sigmoid"
            calibrated = CalibratedClassifierCV(final_pipe, method=method, cv=calibration_cv)
            calibrated.fit(X, y)
            model_for_inference = calibrated
            calibration_used = True
            calibration_method = method
        else:
            model_for_inference = final_pipe

    avg_roc_auc = float(np.mean([m["roc_auc"] for m in fold_metrics])) if fold_metrics else 0.5
    avg_logloss = float(np.mean([m["logloss"] for m in fold_metrics])) if fold_metrics else 0.0
    avg_brier = float(np.mean([m["brier_score"] for m in fold_metrics])) if fold_metrics else 0.25

    metrics = {
        "model": model_name,
        "n_splits": cfg.n_splits,
        "total_samples": int(len(X)),
        "walk_forward_folds": fold_metrics,
        "avg_roc_auc_wf": avg_roc_auc,
        "avg_logloss_wf": avg_logloss,
        "avg_brier_wf": avg_brier,
        "calibration_used": calibration_used,
        "calibration_method": calibration_method,
    }

    return model_for_inference, metrics, avg_roc_auc


def train_from_csv(
    csv_path: Path | str,
    cfg: WalkForwardConfig | None = None,
) -> dict[str, Any]:
    if cfg is None:
        cfg = WalkForwardConfig()

    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    df = pd.read_csv(path)
    if "win" not in df.columns:
        raise ValueError("Dataset must contain 'win' target column")

    y = pd.to_numeric(df["win"], errors="coerce").fillna(0).astype(int)

    drop_cols = ["win", "pnl_r", "exit_reason", "trade_id", "schema_version",
                  "max_favorable_excursion", "max_adverse_excursion", "future_return"]
    X = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

    if "timestamp" in X.columns:
        sort_key = pd.to_datetime(X["timestamp"], errors="coerce")
        order = sort_key.argsort()
        X = X.iloc[order].reset_index(drop=True)
        y = y.iloc[order].reset_index(drop=True)
        X = X.drop(columns=["timestamp"])

    feat_cols = [c for c in cfg.features if c in X.columns]
    extra_cols = [c for c in X.columns if is_numeric_dtype(X[c]) and c not in feat_cols and c not in drop_cols]
    use_cols = feat_cols + extra_cols
    X = X[[c for c in use_cols if c in X.columns]]

    model, wf_metrics, avg_roc = train_walk_forward(X, y, cfg)

    cfg.model_dir.mkdir(parents=True, exist_ok=True)
    model_path = cfg.model_dir / "quality_filter.pkl"
    joblib.dump(model, model_path)

    imp_df = _compute_temporal_importance(
        model if not hasattr(model, "base_estimator") else model.base_estimator,
        list(X.columns),
    )
    imp_df.to_csv(cfg.importance_path, index=False)

    metrics_payload = {
        **wf_metrics,
        "model_path": str(model_path),
        "importance_path": str(cfg.importance_path),
    }
    cfg.metrics_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.metrics_path.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")
    return metrics_payload


def train_from_context(
    context: pd.DataFrame,
    engine: FeatureEngine | None = None,
    cfg: WalkForwardConfig | None = None,
) -> dict[str, Any]:
    if engine is None:
        engine = FeatureEngine()
    df = _build_dataset_from_context(context, engine)
    y = df["win"] if "win" in df.columns else pd.Series([0] * len(df))
    X = df[[c for c in cfg.features if c in df.columns]] if cfg else df

    if cfg is None:
        cfg = WalkForwardConfig()

    model, wf_metrics, _ = train_walk_forward(X, y, cfg)

    cfg.model_dir.mkdir(parents=True, exist_ok=True)
    model_path = cfg.model_dir / "quality_filter.pkl"
    joblib.dump(model, model_path)
    wf_metrics["model_path"] = str(model_path)

    return wf_metrics
