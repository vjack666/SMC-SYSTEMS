from pathlib import Path
import pandas as pd

data_dir = Path("data/raw")
symbols = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"]
missing = ["USDJPY", "USDCAD", "USDCHF"]

for s in symbols:
    p = data_dir / f"{s}_M15.parquet"
    if p.exists():
        df = pd.read_parquet(p)
        print(f"{s} M15: {len(df):>8} rows | time: {df['time'].iloc[0]} to {df['time'].iloc[-1]}")
    else:
        print(f"{s} M15: MISSING")

for s in missing:
    p = data_dir / f"{s}_M15.parquet"
    if p.exists():
        df = pd.read_parquet(p)
        print(f"{s} M15: {len(df):>8} rows | time: {df['time'].iloc[0]} to {df['time'].iloc[-1]}")
    else:
        print(f"{s} M15: MISSING")
