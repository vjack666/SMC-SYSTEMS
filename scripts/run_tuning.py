"""CLI entry point for Optuna hyperparameter tuning on ML datasets.

Usage:
  python scripts/run_tuning.py --dataset data/dataset.parquet
  python scripts/run_tuning.py --dataset data/dataset.parquet --symbol GBPUSD --trials 100 --train
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.trainer import FEATURES_ML_V3, load_dataset, save_model, ModelMetadata
from ml.tuner import TuningConfig, tune_from_dataset, train_with_best_params


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Optuna hyperparameter tuning on an ML dataset",
    )
    parser.add_argument("--dataset", required=True, help="Path to parquet dataset")
    parser.add_argument("--symbol", default="EURUSD", help="Symbol name for output naming")
    parser.add_argument("--trials", type=int, default=50, help="Number of Optuna trials")
    parser.add_argument("--splits", type=int, default=5, help="TimeSeriesSplit folds")
    parser.add_argument("--output", default="ml/tuning_results", help="Output directory")
    parser.add_argument("--train", action="store_true", help="Train and save the model after tuning")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    dataset_path = Path(args.dataset)

    if not dataset_path.exists():
        print(f"ERROR: dataset not found: {dataset_path}")
        return 1

    cfg = TuningConfig(
        n_trials=args.trials,
        n_splits=args.splits,
    )

    try:
        X, y, features, schema_version = load_dataset(dataset_path, feature_list=FEATURES_ML_V3)

        print(f"Dataset: {dataset_path.name}")
        print(f"Samples: {len(X)}  Features: {len(features)}  Schema: {schema_version}")
        print()

        print(f"Starting tuning ({cfg.n_trials} trials, {cfg.n_splits}-fold CV)...")
        results = tune_from_dataset(
            dataset_path=dataset_path,
            feature_list=FEATURES_ML_V3,
            tuning_config=cfg,
        )

        print()
        print("=" * 60)
        print("  TUNING REPORT")
        print("=" * 60)
        print(f"  Best score (validation): {results['best_value']:.4f}")
        print(f"  Best params:            {results['best_params']}")
        print(f"  Trials run:             {results['n_trials']}")
        print(f"  Features used:          {results['n_features']}")
        print(f"  Samples used:           {results['n_samples']}")
        print(f"  Calibration:            {results.get('calibration_used', False)}")
        print("=" * 60)

        if args.train:
            print()
            print("Training final model with best params...")

            model, metrics = train_with_best_params(
                X, y, results["best_params"], calibrate=True,
            )

            output_dir = Path(args.output)
            model_path = output_dir / f"{args.symbol}_xgb_model.joblib"

            save_model(
                model=model,
                metadata=ModelMetadata(
                    feature_names=features,
                    schema_version=schema_version,
                    training_date=datetime.now(timezone.utc).isoformat(),
                    model_name="xgboost_tuned",
                    n_samples=len(X),
                    metrics=metrics,
                ),
                path=model_path,
            )

            print(f"  Model saved: {model_path}")
            print(f"  Metrics:     {metrics}")

    except FileNotFoundError as e:
        print(f"ERROR: file not found -- {e}")
        return 1
    except ImportError as e:
        print(f"ERROR: missing dependency -- {e}")
        return 1
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
