from pathlib import Path
import pandas as pd

path = Path("data/ml/multi_symbol/v4_dataset.parquet")
df = pd.read_parquet(path)
print(f"Shape: {df.shape}")
print(f"Columns ({len(df.columns)}): {sorted(df.columns.tolist())}")
print(f"Symbols: {df['symbol'].unique().tolist()}")
ts_col = "timestamp" if "timestamp" in df.columns else ("time" if "time" in df.columns else None)
if ts_col:
    print(f"Date range: {df[ts_col].min()} -> {df[ts_col].max()}")
print(f"Schema version: {df['schema_version'].iloc[0]}")
agent_cols = [c for c in df.columns if c.startswith('agent_')]
print(f"Agent columns ({len(agent_cols)}): {agent_cols}")
if 'label' in df.columns:
    print(f"Label distribution:\n{df['label'].value_counts().to_string()}")
elif 'win' in df.columns:
    print(f"Win rate: {df['win'].mean():.3f}  (zeros={df['win'].value_counts().get(0,0)}, ones={df['win'].value_counts().get(1,0)})")
print(f"NaN check: {df.isna().sum().sum()} total NaN values")
print(f"year_month range: {df['year_month'].min()} -> {df['year_month'].max()}")
