from pathlib import Path
from smc_successor.ml.validator import validate_dataset
from smc_successor.ml.trainer import load_dataset

# Validate combined dataset
combined_path = Path("data/ml/multi_symbol/v4_dataset.parquet")
print(f"Validating combined dataset: {combined_path}")
result = validate_dataset(combined_path)
print(result)

print()

# Validate individual symbol datasets
for symbol in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF"]:
    path = Path(f"data/ml/{symbol}/v4_{symbol}.parquet")
    if path.exists():
        r = validate_dataset(path)
        print(f"{symbol}: {r}")
    else:
        print(f"{symbol}: NOT FOUND")

print()
print("Combined dataset shape:")
df = load_dataset(str(combined_path))
print(f"  {df.shape}")
print(f"  Columns: {sorted(df.columns.tolist())}")
print(f"  Symbols: {df['symbol'].unique().tolist()}")
print(f"  Date range: {df['time'].min()} -> {df['time'].max()}")
print(f"  Agent columns present: {[c for c in df.columns if c.startswith('agent_')]}")
print(f"  Label distribution:\n{df['label'].value_counts().to_string()}")
