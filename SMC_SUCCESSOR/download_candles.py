from __future__ import annotations

import argparse
import sys
from pathlib import Path

from smc_successor.data.mt5.connector import MT5Connector


def main() -> None:
    parser = argparse.ArgumentParser(description="Download historical candles from MetaTrader 5")
    parser.add_argument("symbol", type=str, help="Symbol to download (e.g. EURUSD)")
    parser.add_argument("timeframe", type=str, nargs="?", default="M15", help="Timeframe (M1, M5, M15, M30, H1, H4, D1)")
    parser.add_argument("--count", type=int, default=100_000, help="Number of bars to download")
    parser.add_argument("--output", type=str, default="data/raw", help="Output directory for parquet files")
    parser.add_argument("--all-timeframes", action="store_true", help="Download all timeframes for the symbol")

    args = parser.parse_args()

    output_dir = Path(args.output)

    try:
        with MT5Connector() as mt5:
            print(f"Connected to MT5 terminal")
            print(f"  Terminal: {mt5.terminal_info().get('name', 'unknown')}")
            print(f"  Account:  {mt5.account_info().get('login', 'unknown')}")
            print()

            if args.all_timeframes:
                timeframes = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
                print(f"Downloading {args.symbol} for all timeframes...")
                results = mt5.download_all_timeframes(args.symbol, timeframes, args.count, output_dir)
                for r in results:
                    print(f"  {r.timeframe:4s}: {r.bars:>6d} bars  {r.date_from} -> {r.date_to}  -> {r.file_path}")
            else:
                print(f"Downloading {args.symbol} {args.timeframe}...")
                result = mt5.download_and_save(args.symbol, args.timeframe, args.count, output_dir)
                print(f"  {result.bars} bars  {result.date_from} -> {result.date_to}")
                print(f"  Columns: {', '.join(result.columns)}")
                print(f"  Saved:   {result.file_path}")

    except ConnectionError as e:
        print(f"ERROR: Cannot connect to MT5: {e}", file=sys.stderr)
        print("Make sure MetaTrader 5 terminal is running.", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
