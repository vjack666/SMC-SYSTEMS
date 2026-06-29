from pathlib import Path
from smc_successor.ml.walk_forward import run_walk_forward, print_walk_forward_report

dataset_path = Path("data/ml/multi_symbol/v4_dataset.parquet")

print(f"Training on: {dataset_path}")
print(f"  Dataset size: {dataset_path.stat().st_size / 1024:.1f} KB")

result = run_walk_forward(
    dataset_path=dataset_path,
    n_windows=5,
    calibrate=True,
)

print_walk_forward_report(result)
print(f"\nAggregate metrics: {result.aggregate_metrics}")
print(f"Stability: {result.stability}")
if result.feature_importance_rank:
    print("\nTop 10 features:")
    for fi in result.feature_importance_rank[:10]:
        print(f"  {fi['feature']}: {fi['importance']:.4f}")
