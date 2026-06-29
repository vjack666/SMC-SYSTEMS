from pathlib import Path
from smc_successor.ml.dataset_builder import DatasetBuildConfig, build_ml_dataset

SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF")

config = DatasetBuildConfig(
    symbols=SYMBOLS,
    timeframe="M15",
    data_dir=Path("data/raw"),
    output_dir=Path("data/ml"),
    max_bars=5000,
    min_confidence=0.0,
    scalping_config={
        "trend_confidence_threshold": 0.0,
        "min_atr_ratio": 0.0,
    },
    schema_version="v4",
    auto_download=True,
    combined_output=True,
)

result = build_ml_dataset(config)

print(f"\n=== BUILD RESULTS ===")
total = sum(result.values())
print(f"Symbols processed: {len(result)}")
print(f"Total samples: {total}")
for sym, count in sorted(result.items()):
    print(f"  {sym}: {count}")
