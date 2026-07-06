"""End-to-end ML pipeline: dataset build, train, verify, notify.

Writes progress to results/ml_pipeline_status.json and prints ML_PIPELINE_COMPLETE
when finished so terminals/watchers can detect completion.
"""
from __future__ import annotations

import json
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STATUS_PATH = ROOT / "results" / "ml_pipeline_status.json"
COMPLETE_MARKER = "ML_PIPELINE_COMPLETE"
DATASET_PATH = ROOT / "data" / "ml" / "multi_symbol" / "v4_dataset.parquet"
MODEL_PATH = ROOT / "ml" / "models" / "quality_filter.pkl"


def write_status(phase: str, message: str, **extra: object) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "phase": phase,
        "message": message,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **extra,
    }
    STATUS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[{phase}] {message}", flush=True)


def build_dataset() -> int:
    from ml.dataset_builder import DatasetBuildConfig, build_ml_dataset

    symbols = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF")
    config = DatasetBuildConfig(
        symbols=symbols,
        timeframes=("M15",),
        data_dir=ROOT / "data" / "raw",
        output_dir=ROOT / "data" / "ml",
        max_bars=5000,
        min_confidence=0.0,
        scalping_config={"trend_confidence_threshold": 0.0, "min_atr_ratio": 0.0},
        schema_version="v4",
        auto_download=True,
        combined_output=True,
    )
    result = build_ml_dataset(config)
    return int(sum(result.values()))


def train_model() -> dict:
    from datetime import datetime as dt

    import pandas as pd

    from ml.trainer import (
        FEATURES_ML_V3,
        ModelMetadata,
        TARGET_COLUMN,
        chronological_train_test_split,
        load_dataset,
        save_model,
        train_model as fit_model,
    )

    X, y, features, schema = load_dataset(DATASET_PATH, FEATURES_ML_V3, TARGET_COLUMN)
    if "entry_time" in pd.read_parquet(DATASET_PATH).columns:
        times = pd.read_parquet(DATASET_PATH)["entry_time"]
        X = X.copy()
        X["entry_time"] = times.values

    X_train, X_test, _, y_train, y_test, _ = chronological_train_test_split(
        X, y, test_size=0.2, time_col="entry_time" if "entry_time" in X.columns else "timestamp"
    )
    feature_cols = [c for c in features if c in X_train.columns]
    X_train = X_train[feature_cols]
    X_test = X_test[feature_cols]

    model, metrics = fit_model(X_train, y_train, X_test, y_test, calibrate=True)
    metrics["holdout"] = metrics.get("validation", {})

    metadata = ModelMetadata(
        feature_names=feature_cols,
        schema_version=schema,
        training_date=dt.now(timezone.utc).isoformat(),
        metrics=metrics,
        model_name="quality_filter",
        n_samples=len(X_train),
    )
    save_model(model, metadata, MODEL_PATH, X_train=X_train)
    return metrics


def verify_integration() -> dict:
    from ml.inference import QualityFilter

    qf = QualityFilter.load(MODEL_PATH)
    checks = {
        "model_loaded": qf.is_active,
        "paper_runner_import": False,
        "scalping_config_ml_flag": False,
    }

    from paper_trading.runner import PaperTradingRunner
    from signals.pipeline import ScalpingConfig

    checks["paper_runner_import"] = PaperTradingRunner is not None
    cfg = ScalpingConfig()
    checks["scalping_config_ml_flag"] = cfg.use_ml_quality_filter and bool(cfg.ml_model_path)
    checks["all_passed"] = all(checks.values())
    return checks


def notify_windows() -> None:
    notify_script = ROOT / "scripts" / "ml_notify_complete.py"
    if notify_script.exists():
        subprocess.run([sys.executable, str(notify_script)], check=False)


def main() -> int:
    write_status("starting", "ML pipeline started")
    try:
        write_status("building_dataset", "Building v4 dataset from real market data...")
        sample_count = build_dataset()
        write_status("building_dataset", f"Dataset ready ({sample_count} samples)", samples=sample_count)

        write_status("training", "Training quality filter with chronological holdout...")
        metrics = train_model()
        holdout = metrics.get("holdout", metrics.get("validation", {}))
        roc_auc = float(holdout.get("roc_auc", 0.0))
        write_status(
            "training",
            f"Model trained — holdout ROC-AUC={roc_auc:.3f}",
            metrics=metrics,
            model_path=str(MODEL_PATH),
        )

        write_status("verifying", "Verifying ML integration in paper trading...")
        checks = verify_integration()
        write_status("verifying", "Integration checks complete", checks=checks)

        write_status(
            "complete",
            COMPLETE_MARKER,
            complete=True,
            marker=COMPLETE_MARKER,
            checks=checks,
            metrics=metrics,
        )
        print(COMPLETE_MARKER, flush=True)
        notify_windows()
        return 0
    except Exception as exc:
        write_status(
            "failed",
            str(exc),
            error=traceback.format_exc(),
        )
        print(f"ML_PIPELINE_FAILED: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())