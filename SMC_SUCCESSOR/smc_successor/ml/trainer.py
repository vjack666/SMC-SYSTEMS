from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    auc,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.pipeline import Pipeline

from smc_successor.ml.train import _build_feature_pipeline, _pick_estimator

FEATURES_ML_V3: tuple[str, ...] = (
    # ICT detector features
    "bos_detected", "bos_strength",
    "choch_detected", "choch_strength",
    "fvg_detected", "fvg_size", "fvg_fill_status", "fvg_direction",
    "ob_detected", "ob_distance",
    "liquidity_sweep",
    "displacement_magnitude", "displacement_bullish", "displacement_bearish",
    # Zone features
    "premium_discount_zone", "premium_distance", "ote_long_min", "ote_short_min",
    # Structure features
    "d1_bias", "h4_bias", "trend_alignment", "trend_confidence",
    "directional_efficiency", "range_compression",
    # Technical indicators
    "ema_fast", "ema_slow", "ema_distance", "ema_slope",
    "atr", "atr_ratio", "candle_range_vs_atr",
    "volatility_regime",
    "rsi", "rsi_slope",
    "volume_ratio", "momentum_strength",
    "spread", "market_regime",
    # Session / context
    "session", "weekday", "direction",
    # Trade context
    "sl_distance", "tp_distance", "rr_ratio", "expected_hold_bars",
    # Agent outputs (22 columns — excludes agent_decision_ml_probability)
    "agent_ict_bias", "agent_ict_confidence", "agent_ict_events",
    "agent_wyckoff_bias", "agent_wyckoff_confidence", "agent_wyckoff_phase",
    "agent_wyckoff_events",
    "agent_wyckoff_spring", "agent_wyckoff_upthrust",
    "agent_wyckoff_sos", "agent_wyckoff_sow", "agent_wyckoff_effort_divergence",
    "agent_structure_bias", "agent_structure_confidence", "agent_structure_events",
    "agent_decision_bias", "agent_decision_confidence", "agent_decision_reasons",
    "agent_decision_conflicts", "agent_decision_conflict_penalty",
    "agent_decision_weighted_bias_sum", "agent_decision_total_weight",
)

COLUMNS_TO_DROP: tuple[str, ...] = (
    "schema_version", "symbol", "timestamp", "year_month",
    "win", "pnl_r", "max_favorable_excursion", "max_adverse_excursion",
    "holding_time", "exit_reason",
    "ml_probability", "ml_threshold",
    "agent_decision_ml_probability",
)

TARGET_COLUMN = "win"


@dataclass
class ModelMetadata:
    feature_names: list[str]
    schema_version: str
    training_date: str
    metrics: dict[str, Any]
    model_name: str
    n_samples: int
    feature_importance: list[dict[str, float]] = field(default_factory=list)


def load_dataset(
    path: Path | str,
    feature_list: tuple[str, ...] = FEATURES_ML_V3,
    target_column: str = TARGET_COLUMN,
) -> tuple[pd.DataFrame, pd.Series, list[str], str]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    df = pd.read_parquet(path)
    schema_version = str(df.get("schema_version", "unknown").iloc[0]) if "schema_version" in df.columns else "unknown"

    available_features = [c for c in feature_list if c in df.columns]
    missing = [c for c in feature_list if c not in df.columns]
    if missing:
        import warnings
        warnings.warn(f"Missing {len(missing)} expected features: {missing}")

    if target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' not found in dataset")

    X = df[available_features].copy()
    y = df[target_column].astype(int)

    return X, y, available_features, schema_version


def chronological_train_test_split(
    X: pd.DataFrame,
    y: pd.Series,
    test_size: float = 0.2,
    val_size: float = 0.0,
    shuffle: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, pd.Series, pd.Series, pd.Series | None]:
    n = len(X)
    test_n = int(n * test_size)
    val_n = int(n * val_size)

    train_n = n - test_n - val_n

    X_train = X.iloc[:train_n].reset_index(drop=True)
    y_train = y.iloc[:train_n].reset_index(drop=True)

    X_test = X.iloc[train_n:train_n + test_n].reset_index(drop=True)
    y_test = y.iloc[train_n:train_n + test_n].reset_index(drop=True)

    X_val: pd.DataFrame | None = None
    y_val: pd.Series | None = None
    if val_size > 0:
        X_val = X.iloc[train_n + test_n:].reset_index(drop=True)
        y_val = y.iloc[train_n + test_n:].reset_index(drop=True)

    return X_train, X_test, X_val, y_train, y_test, y_val


def train_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame | None = None,
    y_val: pd.Series | None = None,
    calibrate: bool = True,
    random_state: int = 42,
) -> tuple[Any, dict[str, Any]]:
    model_name, estimator = _pick_estimator()
    preprocess = _build_feature_pipeline(X_train)

    if y_train.nunique() < 2:
        from sklearn.dummy import DummyClassifier
        estimator = DummyClassifier(strategy="prior")
        model_name = "dummy"
        calibrate = False

    pipe = Pipeline([
        ("preprocess", preprocess),
        ("clf", estimator),
    ])
    pipe.fit(X_train, y_train)

    model_for_inference: Any = pipe
    calibration_used = False
    calibration_method = "none"
    val_metrics: dict[str, float] | None = None

    if calibrate and y_train.nunique() > 1:
        min_class_count = int(y_train.value_counts().min())
        calibration_cv = min(3, min_class_count)
        if calibration_cv >= 2:
            from sklearn.calibration import CalibratedClassifierCV
            method = "isotonic" if calibration_cv >= 3 else "sigmoid"
            calibrated = CalibratedClassifierCV(pipe, method=method, cv=calibration_cv)
            calibrated.fit(X_train, y_train)
            model_for_inference = calibrated
            calibration_used = True
            calibration_method = method

    if X_val is not None and y_val is not None:
        val_metrics = _compute_classification_metrics(model_for_inference, X_val, y_val)

    metrics: dict[str, Any] = {
        "model": model_name,
        "calibration_used": calibration_used,
        "calibration_method": calibration_method,
        "n_train": int(len(X_train)),
    }
    if val_metrics:
        metrics["validation"] = val_metrics
    if X_val is None:
        train_metrics = _compute_classification_metrics(pipe, X_train, y_train)
        metrics["training"] = train_metrics

    return model_for_inference, metrics


def _compute_classification_metrics(model: Any, X: pd.DataFrame, y: pd.Series) -> dict[str, float]:
    proba = np.asarray(model.predict_proba(X))
    proba_class1 = proba[:, 1] if proba.ndim == 2 and proba.shape[1] >= 2 else np.full(len(y), 0.5)
    pred = (proba_class1 >= 0.5).astype(int)

    metrics: dict[str, float] = {}
    metrics["accuracy"] = float(accuracy_score(y, pred))

    if len(np.unique(y)) > 1:
        metrics["precision"] = float(precision_score(y, pred, zero_division=0))
        metrics["recall"] = float(recall_score(y, pred, zero_division=0))
        if proba_class1.std() > 1e-9:
            metrics["roc_auc"] = float(roc_auc_score(y, proba_class1))
        else:
            metrics["roc_auc"] = 0.5
    else:
        metrics["precision"] = float(precision_score(y, pred, zero_division=0)) if y.sum() > 0 else 0.0
        metrics["recall"] = float(recall_score(y, pred, zero_division=0)) if y.sum() > 0 else 0.0
        metrics["roc_auc"] = 0.5

    metrics["n_samples"] = int(len(y))
    return metrics


def evaluate_trade_metrics(
    y_true: pd.Series,
    y_pred_proba: pd.Series | np.ndarray,
    pnl_r: pd.Series | None = None,
    threshold: float = 0.5,
) -> dict[str, Any]:
    proba_arr = np.asarray(y_pred_proba)
    pred = (proba_arr >= threshold).astype(int)

    base_metrics = _compute_classification_metrics_for_values(y_true, proba_arr, pred)

    if pnl_r is not None:
        pnl_arr = np.asarray(pnl_r)
        accepted_mask = pred == 1
        rejected_mask = pred == 0

        accepted_pnl = pnl_arr[accepted_mask] if accepted_mask.sum() > 0 else np.array([0.0])
        rejected_pnl = pnl_arr[rejected_mask] if rejected_mask.sum() > 0 else np.array([0.0])

        all_pnl = pnl_arr

        base_metrics["all_trades_win_rate"] = float((all_pnl > 0).mean())
        base_metrics["accepted_win_rate"] = float((accepted_pnl > 0).mean()) if len(accepted_pnl) > 0 else 0.0
        base_metrics["rejected_win_rate"] = float((rejected_pnl > 0).mean()) if len(rejected_pnl) > 0 else 0.0
        base_metrics["win_rate_impact"] = base_metrics["accepted_win_rate"] - base_metrics["all_trades_win_rate"]

        accepted_profit = accepted_pnl[accepted_pnl > 0].sum() if (accepted_pnl > 0).any() else 1e-9
        accepted_loss = abs(accepted_pnl[accepted_pnl < 0].sum()) if (accepted_pnl < 0).any() else 1e-9
        rejected_profit = rejected_pnl[rejected_pnl > 0].sum() if (rejected_pnl > 0).any() else 1e-9
        rejected_loss = abs(rejected_pnl[rejected_pnl < 0].sum()) if (rejected_pnl < 0).any() else 1e-9

        all_profit = all_pnl[all_pnl > 0].sum() if (all_pnl > 0).any() else 1e-9
        all_loss = abs(all_pnl[all_pnl < 0].sum()) if (all_pnl < 0).any() else 1e-9

        base_metrics["all_trades_profit_factor"] = float(all_profit / all_loss) if all_loss > 1e-9 else float("inf")
        base_metrics["accepted_profit_factor"] = float(accepted_profit / accepted_loss) if accepted_loss > 1e-9 else float("inf")
        base_metrics["rejected_profit_factor"] = float(rejected_profit / rejected_loss) if rejected_loss > 1e-9 else float("inf")
        base_metrics["profit_factor_impact"] = base_metrics["accepted_profit_factor"] - base_metrics["all_trades_profit_factor"]

        base_metrics["all_trades_expectancy"] = float(all_pnl.mean())
        base_metrics["accepted_expectancy"] = float(accepted_pnl.mean()) if len(accepted_pnl) > 0 else 0.0
        base_metrics["rejected_expectancy"] = float(rejected_pnl.mean()) if len(rejected_pnl) > 0 else 0.0
        base_metrics["expectancy_impact"] = base_metrics["accepted_expectancy"] - base_metrics["all_trades_expectancy"]

        base_metrics["n_accepted"] = int(accepted_mask.sum())
        base_metrics["n_rejected"] = int(rejected_mask.sum())
        base_metrics["n_all"] = int(len(all_pnl))

    base_metrics["threshold"] = threshold
    return base_metrics


def _compute_classification_metrics_for_values(
    y_true: pd.Series | np.ndarray,
    proba: np.ndarray,
    pred: np.ndarray,
) -> dict[str, float]:
    metrics: dict[str, float] = {}
    metrics["accuracy"] = float(accuracy_score(y_true, pred))
    if len(np.unique(y_true)) > 1:
        metrics["precision"] = float(precision_score(y_true, pred, zero_division=0))
        metrics["recall"] = float(recall_score(y_true, pred, zero_division=0))
        if proba.std() > 1e-9:
            metrics["roc_auc"] = float(roc_auc_score(y_true, proba))
        else:
            metrics["roc_auc"] = 0.5
    else:
        metrics["precision"] = 0.0
        metrics["recall"] = 0.0
        metrics["roc_auc"] = 0.5
    return metrics


FEATURE_IMPORTANCE_FALLBACK: list[dict[str, float]] = []


def compute_feature_importance(
    model: Any,
    feature_names: list[str],
    X: pd.DataFrame | None = None,
    y: pd.Series | None = None,
) -> list[dict[str, float]]:
    try:
        inner = model
        if hasattr(inner, "base_estimator"):
            inner = inner.base_estimator
        if hasattr(inner, "named_steps") and "clf" in inner.named_steps:
            inner = inner.named_steps["clf"]
        importances = inner.feature_importances_

        n_imp = len(importances)

        if n_imp == len(feature_names):
            result = [{"feature": fn, "importance": float(imp)} for fn, imp in zip(feature_names, importances)]
            return sorted(result, key=lambda x: -x["importance"])

        if n_imp > len(feature_names):
            from sklearn.compose import ColumnTransformer

            try:
                preprocess = model.named_steps["preprocess"]
                if isinstance(preprocess, ColumnTransformer):
                    transformer_names: list[str] = []
                    for name, transformer, columns in preprocess.transformers_:
                        if hasattr(transformer, "get_feature_names_out"):
                            try:
                                out = transformer.get_feature_names_out()
                                for o in out:
                                    prefixed = f"{name}__{o}"
                                    transformer_names.append(prefixed)
                            except Exception:
                                pass

                    if len(transformer_names) == n_imp:
                        imp_map: dict[str, float] = {}
                        for transformed_name, imp_val in zip(transformer_names, importances):
                            base = transformed_name.split("__")[1] if "__" in transformed_name else transformed_name
                            base = base.split("_")[0] if base in ("bos", "choch", "fvg", "ob", "ema", "atr", "rsi") else base
                            for fn in feature_names:
                                if base in fn or fn in base:
                                    imp_map[fn] = imp_map.get(fn, 0.0) + imp_val
                                    break
                            else:
                                imp_map[transformed_name] = imp_val
                        result = [{"feature": k, "importance": v} for k, v in imp_map.items()]
                        norm = sum(r["importance"] for r in result) or 1.0
                        for r in result:
                            r["importance"] = r["importance"] / norm
                        return sorted(result, key=lambda x: -x["importance"])
            except (AttributeError, KeyError):
                pass

            result = [{"feature": fn, "importance": 0.0} for fn in feature_names]
            return result
    except (AttributeError, ValueError):
        pass

    if X is not None and y is not None and len(X) > 5 and len(y) > 5:
        try:
            from sklearn.inspection import permutation_importance

            perm = permutation_importance(
                model, X, y,
                n_repeats=3,
                random_state=42,
                n_jobs=1,
            )
            result = [
                {"feature": fn, "importance": float(perm.importances_mean[i])}
                for i, fn in enumerate(feature_names)
            ]
            return sorted(result, key=lambda x: -x["importance"])
        except Exception:
            pass

    return [{"feature": fn, "importance": 0.0} for fn in feature_names]


def find_optimal_threshold(
    y_true: pd.Series | np.ndarray,
    y_prob: pd.Series | np.ndarray,
    pnl_r: pd.Series | np.ndarray | None = None,
    metric: str = "profit_factor",
) -> dict[str, Any]:
    thresholds = np.linspace(0.1, 0.9, 81)
    best_val = -1e9
    best_threshold = 0.5
    results: list[dict[str, Any]] = []

    for t in thresholds:
        pred = (np.asarray(y_prob) >= t).astype(int)
        if pred.sum() == 0:
            continue

        if pnl_r is not None and metric in ("profit_factor", "expectancy", "win_rate"):
            pnl = np.asarray(pnl_r)
            mask = pred == 1
            selected_pnl = pnl[mask]
            if len(selected_pnl) == 0:
                continue
            if metric == "profit_factor":
                profit = selected_pnl[selected_pnl > 0].sum() if (selected_pnl > 0).any() else 1e-9
                loss = abs(selected_pnl[selected_pnl < 0].sum()) if (selected_pnl < 0).any() else 1e-9
                val = profit / loss if loss > 1e-9 else 99.0
            elif metric == "expectancy":
                val = float(selected_pnl.mean())
            elif metric == "win_rate":
                val = float((selected_pnl > 0).mean())
            else:
                val = float(roc_auc_score(y_true[mask], y_prob[mask])) if len(np.unique(y_true[mask])) > 1 else 0.5
        else:
            val = float(roc_auc_score(y_true, pred)) if len(np.unique(y_true)) > 1 else 0.5

        results.append({"threshold": float(t), metric: float(val), "n_accepted": int(pred.sum())})

        if val > best_val:
            best_val = val
            best_threshold = float(t)

    return {
        "recommended_threshold": best_threshold,
        "best_value": float(best_val),
        "metric": metric,
        "threshold_scan": results,
    }


def save_model(
    model: Any,
    metadata: ModelMetadata,
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": model,
        "metadata": {
            "feature_names": metadata.feature_names,
            "schema_version": metadata.schema_version,
            "training_date": metadata.training_date,
            "model_name": metadata.model_name,
            "n_samples": metadata.n_samples,
            "metrics": metadata.metrics,
            "feature_importance": metadata.feature_importance,
        },
    }
    joblib.dump(payload, path)
    metrics_path = path.with_suffix(".json")
    metrics_path.write_text(json.dumps(payload["metadata"], indent=2, default=str), encoding="utf-8")
    return path


def load_model(path: Path) -> tuple[Any, dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Model not found: {path}")

    payload = joblib.load(path)
    if isinstance(payload, dict) and "model" in payload and "metadata" in payload:
        return payload["model"], payload["metadata"]

    if hasattr(payload, "predict") or hasattr(payload, "predict_proba"):
        return payload, {}

    raise ValueError(f"Unknown model format at {path}")


def predict_proba(model: Any, feature_row: pd.DataFrame, fallback: float = 0.5) -> float:
    if model is None:
        return float(max(0.0, min(1.0, fallback)))
    if not hasattr(model, "predict_proba"):
        return float(max(0.0, min(1.0, fallback)))
    try:
        proba = np.asarray(model.predict_proba(feature_row))
        if proba.ndim == 2 and proba.shape[0] > 0 and proba.shape[1] >= 2:
            value = float(proba[0, 1])
            if np.isfinite(value):
                return float(max(0.0, min(1.0, value)))
    except Exception:
        pass
    return float(max(0.0, min(1.0, fallback)))
