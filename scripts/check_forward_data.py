import pandas as pd
from pathlib import Path

DATA_DIR = Path("data/mt5")
symbols = ["EURUSD", "GBPUSD", "XAUUSD"]
print("Checking data availability for forward period...")
for s in symbols:
    for tf in ["H1"]:
        p = DATA_DIR / f"{s}_{tf}.parquet"
        if p.exists():
            d = pd.read_parquet(p)
            print(f"{s}_{tf}: {len(d)} rows, from {d['time'].min()} to {d['time'].max()}")
        else:
            print(f"{s}_{tf}: NOT FOUND")
