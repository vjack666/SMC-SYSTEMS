"""Download H1 from MT5 for symbols where disk has <10K bars."""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

if not mt5.initialize():
    print("MT5 NO ESTA ABIERTO -", mt5.last_error())
    exit(1)

symbols = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","NZDUSD","USDCHF","XAUUSD"]
date_from = datetime(2020, 1, 1)
date_to = datetime(2026, 12, 31)

import os
downloaded = []
skipped = []

for sym in symbols:
    path = f"data/raw/{sym}_H1.parquet"
    existing_rows = 0
    if os.path.exists(path):
        existing_rows = len(pd.read_parquet(path))

    rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_H1, date_from, date_to)
    if rates is None or len(rates) == 0:
        print(f"  {sym} H1: MT5 sin datos, skip")
        skipped.append(sym)
        continue

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "volume"})
    df = df[["time", "open", "high", "low", "close", "volume"]]

    if len(df) > existing_rows:
        df.to_parquet(path, index=False)
        print(f"  {sym} H1: {existing_rows:,} -> {len(df):,} rows (updated)")
        downloaded.append(sym)
    else:
        print(f"  {sym} H1: {existing_rows:,} rows (disk already has >= MT5), skip")
        skipped.append(sym)

mt5.shutdown()

print(f"\nDone. Updated: {len(downloaded)}, Skipped: {len(skipped)}")
if downloaded:
    print("Updated:", ", ".join(downloaded))
