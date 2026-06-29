from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smc_successor.ml.trainer import (
    FEATURES_ML_V3,
    TARGET_COLUMN,
    ModelMetadata,
    chronological_train_test_split,
    compute_feature_importance,
    evaluate_trade_metrics,
    load_dataset,
    save_model,
    train_model,
)


@dataclass
class WalkForwardWindow:
    name: str
    train_start: int | str
    train_end: int | str
    test_start: int | str
    test_end: int | str
    n_train: int = 0
    n_test: int = 0
    use_date_filter: bool = False


@dataclass
class WalkForwardResult:
    windows: list[dict[str, Any]] = field(default_factory=list)
    aggregate_metrics: dict[str, float] = field(default_factory=dict)
    stability: dict[str, float] = field(default_factory=dict)
    feature_importance_rank: list[dict[str, float]] = field(default_factory=list)


def _build_date_windows(
    timestamps: pd.Series,
    n_windows: int = 3,
    min_train_frac: float = 0.4,
) -> list[WalkForwardWindow]:
    ts = pd.to_datetime(timestamps, errors="coerce")
    years = ts.dt.year.dropna().unique()
    years.sort()

    if len(years) < 2:
        return _build_index_windows(len(timestamps), n_windows)

    windows: list[WalkForwardWindow] = []
    total = len(ts)

    for i in range(min(n_windows, len(years) - 1)):
        train_years = years[: i + 1]
        test_year = years[i + 1]

        train_mask = ts.dt.year.isin(train_years)
        test_mask = ts.dt.year == test_year

        if train_mask.sum() < 10 or test_mask.sum() < 5:
            continue

        windows.append(WalkForwardWindow(
            name=f"train-{train_years[0]}-{train_years[-1]}_test-{test_year}",
            train_start=int(train_years[0]),
            train_end=int(train_years[-1]),
            test_start=int(test_year),
            test_end=int(test_year),
            n_train=int(train_mask.sum()),
            n_test=int(test_mask.sum()),
            use_date_filter=True,
        ))

    if not windows:
        return _build_index_windows(len(timestamps), n_windows)

    return windows


def _build_index_windows(
    n_samples: int,
    n_windows: int = 3,
    min_train_frac: float = 0.4,
) -> list[WalkForwardWindow]:
    windows: list[WalkForwardWindow] = []
    min_train = max(10, int(n_samples * min_train_frac))

    for i in range(n_windows):
        train_end = int(min_train + (n_samples - min_train) * i / n_windows)
        if i == n_windows - 1:
            test_end = n_samples
        else:
            test_end = int(min_train + (n_samples - min_train) * (i + 1) / n_windows)

        train_start = 0
        test_start = train_end

        if test_end - test_start < 5:
            continue

        windows.append(WalkForwardWindow(
            name=f"window-{i + 1}",
            train_start=train_start,
            train_end=train_end - 1,
            test_start=test_start,
            test_end=test_end - 1,
            n_train=train_end,
            n_test=test_end - test_start,
        ))

    return windows


def _extract_timestamps(
    path: Path,
) -> pd.Series | None:
    try:
        df = pd.read_parquet(path)
        if "timestamp" in df.columns:
            ts = pd.to_datetime(df["timestamp"], errors="coerce")
            if ts.notna().sum() > 10:
                return ts
    except Exception:
        pass
    return None


def run_walk_forward(
    dataset_path: Path,
    feature_list: tuple[str, ...] = FEATURES_ML_V3,
    target_column: str = TARGET_COLUMN,
    n_windows: int = 3,
    calibrate: bool = True,
) -> WalkForwardResult:
    X, y, feature_names, schema_version = load_dataset(dataset_path, feature_list, target_column)
    timestamps = _extract_timestamps(dataset_path)

    windows_list = (
        _build_date_windows(timestamps, n_windows)
        if timestamps is not None
        else _build_index_windows(len(X), n_windows)
    )

    if not windows_list:
        windows_list = _build_index_windows(len(X), n_windows)

    result = WalkForwardResult()
    all_models: list[Any] = []

    df_full = pd.read_parquet(dataset_path)

    for win in windows_list:
        if isinstance(win.train_start, int) and isinstance(win.train_end, int):
            X_train = X.iloc[win.train_start:win.train_end + 1]
            y_train = y.iloc[win.train_start:win.train_end + 1]
            X_test = X.iloc[win.test_start:win.test_end + 1]
            y_test = y.iloc[win.test_start:win.test_end + 1]
        else:
            ts = pd.to_datetime(df_full["timestamp"], errors="coerce")
            train_mask = (ts.dt.year >= win.train_start) & (ts.dt.year <= win.train_end)
            test_mask = (ts.dt.year >= win.test_start) & (ts.dt.year <= win.test_end)
            X_train = X[train_mask]
            y_train = y[train_mask]
            X_test = X[test_mask]
            y_test = y[test_mask]

        if len(X_train) < 10 or len(X_test) < 5:
            continue

        model, train_metrics = train_model(
            X_train, y_train,
            X_val=X_test, y_val=y_test,
            calibrate=calibrate,
        )
        all_models.append(model)

        proba = np.asarray(model.predict_proba(X_test))
        proba_class1 = proba[:, 1] if proba.ndim == 2 and proba.shape[1] >= 2 else np.full(len(y_test), 0.5)

        pnl_series: pd.Series | None = None
        if "pnl_r" in df_full.columns:
            if isinstance(win.train_start, int):
                pnl_series = df_full["pnl_r"].iloc[win.test_start:win.test_end + 1].reset_index(drop=True)
            else:
                pnl_series = df_full["pnl_r"][test_mask].reset_index(drop=True)

        y_test_reset = y_test.reset_index(drop=True)
        trade_metrics = evaluate_trade_metrics(
            y_true=y_test_reset,
            y_pred_proba=proba_class1,
            pnl_r=pnl_series,
            threshold=0.5,
        )

        trade_metrics["window"] = win.name
        trade_metrics["n_train"] = win.n_train if win.n_train > 0 else int(len(X_train))
        trade_metrics["n_test"] = win.n_test if win.n_test > 0 else int(len(X_test))
        trade_metrics["model"] = train_metrics.get("model", "unknown")
        trade_metrics["calibration"] = train_metrics.get("calibration_method", "none")
        result.windows.append(trade_metrics)

    if not result.windows:
        return result

    # Aggregate metrics
    agg: dict[str, list[float]] = {}
    for w in result.windows:
        for k, v in w.items():
            if isinstance(v, (int, float)) and k not in ("window", "threshold", "n_train", "n_test", "model", "calibration"):
                agg.setdefault(k, []).append(float(v))

    result.aggregate_metrics = {
        "mean_" + k: float(np.mean(v)) for k, v in agg.items()
    }
    result.aggregate_metrics["n_windows"] = len(result.windows)

    # Stability = lower std is better
    result.stability = {
        "std_" + k: float(np.std(v)) for k, v in agg.items()
    }

    # Feature importance from last model
    if all_models:
        result.feature_importance_rank = compute_feature_importance(all_models[-1], feature_names)

    return result


def print_walk_forward_report(result: WalkForwardResult) -> None:
    print("=" * 70)
    print("WALK-FORWARD VALIDATION REPORT")
    print("=" * 70)

    for win in result.windows:
        print(f"\n--- {win['window']} ---")
        print(f"  Samples: train={win['n_train']}, test={win['n_test']}")
        print(f"  Model: {win.get('model', 'N/A')}, Calibration: {win.get('calibration', 'none')}")
        print(f"  Accuracy:    {win.get('accuracy', 0):.4f}")
        print(f"  Precision:   {win.get('precision', 0):.4f}")
        print(f"  Recall:      {win.get('recall', 0):.4f}")
        print(f"  ROC-AUC:     {win.get('roc_auc', 0):.4f}")
        print(f"  Win rate (accepted): {win.get('accepted_win_rate', 0):.3f}")
        print(f"  Win rate (all):      {win.get('all_trades_win_rate', 0):.3f}")
        print(f"  Profit factor impact: {win.get('profit_factor_impact', 0):.3f}")
        print(f"  Expectancy impact:    {win.get('expectancy_impact', 0):.4f}")

    if result.aggregate_metrics:
        print(f"\n{'=' * 70}")
        print("AGGREGATE (mean across windows)")
        print(f"{'=' * 70}")
        for k, v in sorted(result.aggregate_metrics.items()):
            if not k.startswith("std_"):
                print(f"  {k}: {v:.4f}")

    if result.stability:
        print(f"\n{'=' * 70}")
        print("STABILITY (std across windows — lower is better)")
        print(f"{'=' * 70}")
        for k, v in sorted(result.stability.items()):
            print(f"  {k}: {v:.4f}")

    if result.feature_importance_rank:
        print(f"\n{'=' * 70}")
        print("FEATURE IMPORTANCE")
        print(f"{'=' * 70}")
        for fi in result.feature_importance_rank[:20]:
            print(f"  {fi['feature']:45s} {fi['importance']:.4f}")

    print(f"\n{'=' * 70}")
    print("END REPORT")
    print("=" * 70)
