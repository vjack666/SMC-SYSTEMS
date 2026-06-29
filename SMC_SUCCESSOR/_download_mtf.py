from pathlib import Path
import pandas as pd
import MetaTrader5 as mt5

missing = ["USDJPY", "NZDUSD", "USDCAD", "USDCHF"]
output_dir = Path("data/raw")
output_dir.mkdir(parents=True, exist_ok=True)

TIMEFRAMES = {"D1": 16408, "H4": 16388}

for symbol in missing:
    for tf_name, tf_val in TIMEFRAMES.items():
        path = output_dir / f"{symbol}_{tf_name}.parquet"
        if path.exists():
            print(f"{symbol} {tf_name} exists ({path.stat().st_size} bytes), skipping")
            continue

        print(f"Downloading {symbol} {tf_name}...")
        if not mt5.initialize():
            print(f"  MT5 init failed: {mt5.last_error()}")
            mt5.shutdown()
            raise SystemExit(1)

        rates = mt5.copy_rates_from_pos(symbol, tf_val, 0, 5000)
        if rates is None or len(rates) == 0:
            print(f"  FAILED: no data ({mt5.last_error()})")
            mt5.shutdown()
            continue

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df[["time", "open", "high", "low", "close", "tick_volume", "spread"]]
        df.to_parquet(path, index=False)
        print(f"  Saved {len(df)} bars: {df['time'].iloc[0]} -> {df['time'].iloc[-1]}")
        mt5.shutdown()

print("Done")
