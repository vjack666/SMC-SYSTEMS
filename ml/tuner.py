from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import optuna
import pandas as pd
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline

from ml.train import _build_feature_pipeline
from ml.trainer import FEATURES_ML_V3, evaluate_trade_metrics, load_dataset


@dataclass
class TuningConfig:
    n_trials: int = 50
    timeout: int | None = None
    n_splits: int = 5
    random_state: int = 42
    study_name: str = "smc_xgb_tuning"
    storage: str | None = None
    direction: str = "maximize"
    metrics: list[str] = None
    weights: list[float] = None

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = ["roc_auc", "profit_factor", "expectancy"]
        if self.weights is None:
            self.weights = [0.4, 0.3, 0.3]
        if len(self.metrics) != len(self.weights):
            raise ValueError("metrics and weights must have the same length")
        if abs(sum(self.weights) - 1.0) > 1e-6:
            raise ValueError("weights must sum to 1.0")


def _xgb_params(trial: optuna.Trial) -> dict:
    return {
        "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=20),
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0, step=0.05),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0, step=0.05),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
        "gamma": trial.suggest_float("gamma", 0.0, 5.0, step=0.1),
        "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 10.0, step=0.5),
        "reg_lambda": trial.suggest_float("reg_lambda", 0.0, 10.0, step=0.5),
        "random_state": 42,
        "objective": "binary:logistic",
        "eval_metric": "logloss",
    }


def objective(
    trial: optuna.Trial,
    X: pd.DataFrame,
    y: pd.Series,
    preprocess: Any,
    cfg: TuningConfig,
    pnl_r: pd.Series | None = None,
) -> float:
    from xgboost import XGBClassifier

    params = _xgb_params(trial)
    estimator = XGBClassifier(**params, nthread=-1)

    tscv = TimeSeriesSplit(n_splits=cfg.n_splits)
    all_metrics: list[dict[str, float]] = []

    for train_idx, val_idx in tscv.split(X):
        X_train_fold = X.iloc[train_idx]
        y_train_fold = y.iloc[train_idx]
        X_val_fold = X.iloc[val_idx]
        y_val_fold = y.iloc[val_idx]

        if pnl_r is not None:
            pnl_train_fold = pnl_r.iloc[train_idx]
            pnl_val_fold = pnl_r.iloc[val_idx]
        else:
            pnl_train_fold = None
            pnl_val_fold = None

        if y_train_fold.nunique() < 2:
            continue

        pipe = Pipeline([
            ("preprocess", preprocess),
            ("clf", estimator),
        ])
        pipe.fit(X_train_fold, y_train_fold)

        proba = pipe.predict_proba(X_val_fold)[:, 1]

        # Use evaluate_trade_metrics to compute all metrics including profit_factor and expectancy
        metrics = evaluate_trade_metrics(
            y_true=y_val_fold,
            y_pred_proba=proba,
            pnl_r=pnl_val_fold,
            threshold=0.5,
        )

        # Extract the metrics we care about
        fold_metrics = {}
        for m in cfg.metrics:
            if m in metrics:
                val = metrics[m]
                if isinstance(val, float) and (np.isinf(val) or np.isnan(val)):
                    val = 0.0
                fold_metrics[m] = float(val)
            elif m == "logloss":
                # Handle logloss separately (negate for maximization)
                val = -log_loss(y_val_fold, proba, labels=[0, 1])
                if np.isinf(val) or np.isnan(val):
                    val = 0.0
                fold_metrics[m] = float(val)
            else:
                # Default to roc_auc if metric not found
                if len(np.unique(y_val_fold)) > 1:
                    val = roc_auc_score(y_val_fold, proba)
                else:
                    val = 0.5
                fold_metrics[m] = float(val)

        all_metrics.append(fold_metrics)

    if not all_metrics:
        return 0.5

    # Compute mean for each metric across folds
    mean_metrics: dict[str, float] = {}
    for m in cfg.metrics:
        mean_metrics[m] = float(np.mean([fm[m] for fm in all_metrics]))

    # Compute weighted composite score
    composite_score = sum(mean_metrics[m] * w for m, w in zip(cfg.metrics, cfg.weights))

    # Store individual metrics in trial user_attrs for logging callback
    trial.set_user_attr("metrics", mean_metrics)
    trial.set_user_attr("composite_score", float(composite_score))

    return float(composite_score)


def _metrics_logging_callback(study: optuna.Study, trial: optuna.Trial) -> None:
    metrics = trial.user_attrs.get("metrics")
    composite = trial.user_attrs.get("composite_score")
    if metrics:
        metrics_str = ", ".join(f"{k}={v:.4f}" for k, v in metrics.items())
        print(f"Trial {trial.number}: composite={composite:.4f} | {metrics_str}")


def tune_hyperparameters(
    X: pd.DataFrame,
    y: pd.Series,
    cfg: TuningConfig | None = None,
    progress_cb: Callable | None = None,
    pnl_r: pd.Series | None = None,
) -> tuple[dict, float]:
    if cfg is None:
        cfg = TuningConfig()

    preprocess = _build_feature_pipeline(X)

    def _objective(trial: optuna.Trial) -> float:
        return objective(trial, X, y, preprocess, cfg, pnl_r)

    study = optuna.create_study(
        direction=cfg.direction,
        study_name=cfg.study_name,
        storage=cfg.storage,
        load_if_exists=True,
        sampler=optuna.samplers.TPESampler(seed=cfg.random_state),
    )

    callbacks: list[Callable] = [_metrics_logging_callback]
    if progress_cb is not None:
        callbacks.append(progress_cb)

    study.optimize(_objective, n_trials=cfg.n_trials, timeout=cfg.timeout, callbacks=callbacks)

    return study.best_params, study.best_value


def train_with_best_params(
    X: pd.DataFrame,
    y: pd.Series,
    best_params: dict,
    calibrate: bool = True,
) -> tuple[Any, dict]:
    from xgboost import XGBClassifier

    clf_params = {k: v for k, v in best_params.items() if k != "eval_metric"}
    estimator = XGBClassifier(**clf_params, nthread=-1)

    preprocess = _build_feature_pipeline(X)

    pipe = Pipeline([
        ("preprocess", preprocess),
        ("clf", estimator),
    ])

    pipe.fit(X, y)

    model_for_inference: Any = pipe
    calibration_used = False
    calibration_method = "none"

    if calibrate and y.nunique() > 1:
        from sklearn.calibration import CalibratedClassifierCV

        min_class_count = int(y.value_counts().min())
        calibration_cv = min(3, min_class_count)
        if calibration_cv >= 2:
            method = "isotonic" if calibration_cv >= 3 else "sigmoid"
            calibrated = CalibratedClassifierCV(pipe, method=method, cv=calibration_cv)
            calibrated.fit(X, y)
            model_for_inference = calibrated
            calibration_used = True
            calibration_method = method

    metrics: dict[str, Any] = {
        "model": "xgboost_tuned",
        "calibration_used": calibration_used,
        "calibration_method": calibration_method,
        "n_train": int(len(X)),
        "best_params": best_params,
    }

    return model_for_inference, metrics


def tune_from_dataset(
    dataset_path: Path | str,
    feature_list: tuple[str, ...] | None = None,
    target_column: str = "win",
    tuning_config: TuningConfig | None = None,
) -> dict:
    if tuning_config is None:
        tuning_config = TuningConfig()

    X, y, features, schema_version = load_dataset(
        dataset_path,
        feature_list=feature_list or FEATURES_ML_V3,
        target_column=target_column,
    )

    # Load PnL data for trading metrics
    pnl_r = None
    try:
        df = pd.read_parquet(dataset_path)
        if "pnl_r" in df.columns:
            pnl_r = df["pnl_r"]
    except Exception:
        pass

    best_params, best_value = tune_hyperparameters(X, y, tuning_config, pnl_r=pnl_r)

    model, train_metrics = train_with_best_params(X, y, best_params, calibrate=True)

    output_dir = Path("ml/tuning_results")
    output_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, Any] = {
        "dataset_path": str(dataset_path),
        "schema_version": schema_version,
        "n_features": int(X.shape[1]),
        "n_samples": int(len(X)),
        "n_trials": tuning_config.n_trials,
        "best_value": best_value,
        "best_params": best_params,
        "model": train_metrics["model"],
        "calibration_used": train_metrics["calibration_used"],
    }

    results_path = output_dir / f"{tuning_config.study_name}_results.json"
    results_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    return results
