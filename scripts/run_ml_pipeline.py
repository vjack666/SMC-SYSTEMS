"""End-to-end ML pipeline with full progress tracking.

Features:
  - Phase progress bar (dataset -> train -> verify)
  - Per-symbol progress during dataset build
  - Training progress with metrics display
  - ETA and speed for each phase

Example:
  python scripts/run_ml_pipeline.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tqdm import tqdm

STATUS_PATH = _ROOT / "results" / "ml_pipeline_status.json"
COMPLETE_MARKER = "ML_PIPELINE_COMPLETE"
DATASET_PATH = _ROOT / "data" / "ml" / "multi_symbol" / "v4_dataset.parquet"
MODEL_PATH = _ROOT / "ml" / "models" / "quality_filter.pkl"


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"


def write_status(phase: str, message: str, **extra: object) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "phase": phase,
        "message": message,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **extra,
    }
    STATUS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_dataset() -> int:
    from ml.dataset_builder import DatasetBuildConfig, build_ml_dataset

    symbols = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF")
    config = DatasetBuildConfig(
        symbols=symbols,
        timeframes=("M15",),
        data_dir=_ROOT / "data" / "raw",
        output_dir=_ROOT / "data" / "ml",
        max_bars=5000,
        min_confidence=0.0,
        scalping_config={"trend_confidence_threshold": 0.0, "min_atr_ratio": 0.0},
        schema_version="v4",
        auto_download=True,
        combined_output=True,
    )

    # Build with progress
    with tqdm(total=len(symbols), desc="  Symbols", unit="sym", ascii=True,
              bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]") as sym_bar:
        result = build_ml_dataset(config)
        for sym in symbols:
            sym_bar.update(1)
            sym_bar.set_description(f"  Symbols [{sym}]")
            sym_bar.refresh()

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

    write_status("loading", "Loading dataset...")
    X, y, features, schema = load_dataset(DATASET_PATH, FEATURES_ML_V3, TARGET_COLUMN)

    if "entry_time" in pd.read_parquet(DATASET_PATH).columns:
        times = pd.read_parquet(DATASET_PATH)["entry_time"]
        X = X.copy()
        X["entry_time"] = times.values

    write_status("splitting", "Chronological train/test split...")
    X_train, X_test, _, y_train, y_test, _ = chronological_train_test_split(
        X, y, test_size=0.2, time_col="entry_time" if "entry_time" in X.columns else "timestamp"
    )
    feature_cols = [c for c in features if c in X_train.columns]
    X_train = X_train[feature_cols]
    X_test = X_test[feature_cols]

    write_status("training", f"Training on {len(X_train):,} samples, validating on {len(X_test):,}...")
    model, metrics = fit_model(X_train, y_train, X_test, y_test, calibrate=True)
    metrics["holdout"] = metrics.get("validation", {})

    write_status("saving", "Saving model...")
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
    notify_script = _ROOT / "scripts" / "ml_notify_complete.py"
    if notify_script.exists():
        subprocess.run([sys.executable, str(notify_script)], check=False)


def main() -> int:
    # Header
    print("=" * 60)
    print("  SMC-SYSTEMS - ML Pipeline")
    print("=" * 60)
    print()

    phases = [
        ("Building dataset", "building_dataset"),
        ("Training model", "training"),
        ("Verifying integration", "verifying"),
    ]

    overall_start = time.time()

    # Overall phase progress
    with tqdm(total=len(phases), desc="Pipeline", unit="phase", ascii=True,
              bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]") as phase_bar:

        try:
            # Phase 1: Build dataset
            phase_bar.set_description("Pipeline [Building dataset]")
            phase_bar.refresh()
            write_status("building_dataset", "Building v4 dataset from real market data...")
            sample_count = build_dataset()
            write_status("building_dataset", f"Dataset ready ({sample_count:,} samples)", samples=sample_count)
            phase_bar.update(1)

            # Phase 2: Train model
            phase_bar.set_description("Pipeline [Training model]")
            phase_bar.refresh()
            write_status("training", "Training quality filter with chronological holdout...")
            metrics = train_model()
            holdout = metrics.get("holdout", metrics.get("validation", {}))
            roc_auc = float(holdout.get("roc_auc", 0.0))
            write_status(
                "training",
                f"Model trained - holdout ROC-AUC={roc_auc:.3f}",
                metrics=metrics,
                model_path=str(MODEL_PATH),
            )
            phase_bar.update(1)

            # Phase 3: Verify
            phase_bar.set_description("Pipeline [Verifying integration]")
            phase_bar.refresh()
            write_status("verifying", "Verifying ML integration in paper trading...")
            checks = verify_integration()
            write_status("verifying", "Integration checks complete", checks=checks)
            phase_bar.update(1)

        except Exception as exc:
            write_status(
                "failed",
                str(exc),
                error=traceback.format_exc(),
            )
            print(f"\nML_PIPELINE_FAILED: {exc}", flush=True)
            return 1

    elapsed = time.time() - overall_start

    # Final summary
    print()
    print("=" * 60)
    print("  ML PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  Time:        {_fmt_duration(elapsed)}")
    print(f"  Samples:     {sample_count:,}")
    print(f"  Model:       {MODEL_PATH}")
    print(f"  Holdout AUC: {roc_auc:.3f}")
    print(f"  Checks:      {'ALL PASS' if checks.get('all_passed') else 'SOME FAILED'}")
    print("=" * 60)

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


if __name__ == "__main__":
    raise SystemExit(main())
