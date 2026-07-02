import MetaTrader5 as mt5
import pandas as pd
from pathlib import Path

if not mt5.initialize():
    print(f"init failed: {mt5.last_error()}")
    raise SystemExit(1)

selected = mt5.symbol_select("USDCHF", True)
print(f"symbol_select USDCHF: {selected}")

rates = mt5.copy_rates_from_pos("USDCHF", 16408, 0, 100)
print(f"USDCHF D1 100 bars: {len(rates) if rates is not None else 0}")
if rates is not None and len(rates) > 0:
    df = pd.DataFrame(rates)
    t0 = pd.to_datetime(df["time"].iloc[0], unit="s")
    t1 = pd.to_datetime(df["time"].iloc[-1], unit="s")
    print(f"Range: {t0} -> {t1}")

    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df[["time", "open", "high", "low", "close", "tick_volume", "spread"]]

    out = Path("data/raw")
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / "USDCHF_D1.parquet", index=False)
    print(f"Saved {len(df)} bars")
else:
    print(f"Error: {mt5.last_error()}")

mt5.shutdown()
