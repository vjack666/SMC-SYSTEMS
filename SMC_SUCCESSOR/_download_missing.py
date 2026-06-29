from pathlib import Path
from smc_successor.data.mt5.connector import MT5Connector

missing = ["USDJPY", "USDCAD", "USDCHF"]
output_dir = Path("data/raw")
connector = MT5Connector()

for symbol in missing:
    path = output_dir / f"{symbol}_M15.parquet"
    if path.exists():
        print(f"{symbol} M15 already exists, skipping")
        continue
    print(f"Downloading {symbol} M15...")
    result = connector.download_and_save(symbol, "M15", count=50000, output_dir=output_dir)
    print(f"  {result}")
