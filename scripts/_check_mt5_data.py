"""Check MT5 available data for all symbols + TFs."""
import MetaTrader5 as mt5
import pandas as pd

if not mt5.initialize():
    print("MT5 NO ESTA ABIERTO -", mt5.last_error())
    exit(1)

info = mt5.terminal_info()
print("MT5:", info.name)
print("Connected:", info.connected)
print("Build:", info.build)
print()

symbols = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","NZDUSD","USDCHF","XAUUSD"]
tfs = [
    (mt5.TIMEFRAME_M1, "M1"),
    (mt5.TIMEFRAME_M5, "M5"),
    (mt5.TIMEFRAME_M15, "M15"),
    (mt5.TIMEFRAME_H1, "H1"),
    (mt5.TIMEFRAME_H4, "H4"),
    (mt5.TIMEFRAME_D1, "D1"),
]

from datetime import datetime
date_from = datetime(2020, 1, 1)
date_to = datetime(2026, 12, 31)

fmt = "{:<10} {:>5} {:>12} {:>12} {:>12}"
print(fmt.format("Symbol", "TF", "Bars", "Oldest", "Newest"))
print("-" * 55)

available = {}
for sym in symbols:
    for tf_code, tf_name in tfs:
        rates = mt5.copy_rates_range(sym, tf_code, date_from, date_to)
        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            oldest = df["time"].iloc[0].strftime("%Y-%m-%d")
            newest = df["time"].iloc[-1].strftime("%Y-%m-%d")
            count = len(rates)
            print(fmt.format(sym, tf_name, f"{count:,}", oldest, newest))
            available[(sym, tf_name)] = {"rows": count, "oldest": oldest, "newest": newest}
        else:
            print(fmt.format(sym, tf_name, "NO DATA", "-", "-"))

mt5.shutdown()

# Gap analysis
print("\n\n=== GAP ANALYSIS (what disk needs vs MT5 has) ===")
import glob, os

disk_files = glob.glob("data/raw/*.parquet")
disk_inv = {}
for f in disk_files:
    name = os.path.basename(f).replace(".parquet", "")
    parts = name.rsplit("_", 1)
    if len(parts) == 2:
        disk_inv[(parts[0], parts[1])] = os.path.getsize(f) / (1024*1024)

engine_tfs = ["D1", "H4", "H1", "M15", "M5", "M1"]
print()
for sym in symbols:
    missing = []
    for tf in engine_tfs:
        if (sym, tf) not in disk_inv:
            mt5_info = available.get((sym, tf))
            if mt5_info:
                missing.append(f"{tf} ({mt5_info['rows']:,} bars, {mt5_info['oldest']} to {mt5_info['newest']})")
            else:
                missing.append(f"{tf} (NOT AVAILABLE in MT5)")
    if missing:
        print(f"  {sym} MISSING on disk:")
        for m in missing:
            print(f"    - {m}")
    else:
        print(f"  {sym}: COMPLETE on disk")
