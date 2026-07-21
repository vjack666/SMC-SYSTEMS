"""Update D1 and H4 from MT5 where MT5 has more data."""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import os

if not mt5.initialize():
    print("MT5 NO ESTA ABIERTO -", mt5.last_error())
    exit(1)

symbols = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","NZDUSD","USDCHF","XAUUSD"]
date_from = datetime(2020, 1, 1)
date_to = datetime(2026, 12, 31)

for tf_code, tf_name, tf_label in [
    (mt5.TIMEFRAME_D1, "D1", "D1"),
    (mt5.TIMEFRAME_H4, "H4", "H4"),
]:
    print(f"\n=== {tf_name} ===")
    for sym in symbols:
        path = f"data/raw/{sym}_{tf_name}.parquet"
        existing_rows = 0
        if os.path.exists(path):
            existing_rows = len(pd.read_parquet(path))

        rates = mt5.copy_rates_range(sym, tf_code, date_from, date_to)
        if rates is None or len(rates) == 0:
            print(f"  {sym} {tf_name}: sin datos")
            continue

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={"tick_volume": "volume"})
        df = df[["time", "open", "high", "low", "close", "volume"]]

        if len(df) > existing_rows:
            df.to_parquet(path, index=False)
            print(f"  {sym} {tf_name}: {existing_rows:,} -> {len(df):,} (updated)")
        else:
            print(f"  {sym} {tf_name}: {existing_rows:,} (ok)")

mt5.shutdown()
print("\nDone.")
