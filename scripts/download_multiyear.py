"""Download 3-4 years of historical candles for SMC-SYSTEMS (Task A6).

Uses the MT5 connector's `download_rates_range` so you get a fixed calendar
window (not "last N bars"), which is what out-of-sample validation needs.

Requirements:
  - MetaTrader 5 terminal open and logged in (your Funded Next / demo account).
  - `pip install -e .` (so `data.mt5.connector` is importable).

Example:
  python scripts/download_multiyear.py --symbols EURUSD GBPUSD USDCHF USDJPY \
      --years 4 --timeframes M15 H4 D1 --output data/raw
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from data.mt5.connector import MT5Connector


def _resolve_date_from(date_from: str | None, years: int) -> datetime:
    if date_from:
        return datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - timedelta(days=int(years * 365.25))


def main() -> None:
    parser = argparse.ArgumentParser(description="Download multi-year OHLCV via MT5")
    parser.add_argument("--symbols", nargs="+", required=True, help="e.g. EURUSD GBPUSD")
    parser.add_argument(
        "--timeframes", nargs="+", default=["M15", "H4", "D1"],
        help="Timeframes to download (default M15 H4 D1)",
    )
    parser.add_argument("--years", type=float, default=4.0, help="Lookback window in years")
    parser.add_argument("--from", dest="date_from", type=str, default=None,
                        help="Explicit start date ISO (e.g. 2022-01-01). Overrides --years.")
    parser.add_argument("--to", dest="date_to", type=str, default=None,
                        help="Explicit end date ISO (default: now)")
    parser.add_argument("--output", type=str, default="data/raw")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    date_from = _resolve_date_from(args.date_from, args.years)
    date_to = (
        datetime.fromisoformat(args.date_to).replace(tzinfo=timezone.utc)
        if args.date_to else datetime.now(timezone.utc)
    )

    print(f"Window: {date_from.date()} -> {date_to.date()} "
          f"(~{round((date_to - date_from).days / 365.25, 2)} years)")

    try:
        with MT5Connector() as mt5:
            print(f"Connected: {mt5.terminal_info().get('name', 'unknown')}")
            for symbol in args.symbols:
                for tf in args.timeframes:
                    path = output_dir / f"{symbol}_{tf}.parquet"
                    if path.exists():
                        print(f"  {symbol} {tf}: exists, skipping ({path.name})")
                        continue
                    print(f"  Downloading {symbol} {tf} ...", end=" ", flush=True)
                    df = mt5.download_rates_range(symbol, tf, date_from, date_to)
                    if df is None or len(df) == 0:
                        print("NO DATA")
                        continue
                    df.to_parquet(path, index=False)
                    print(f"{len(df)} bars  {df['time'].iloc[0]} -> {df['time'].iloc[-1]}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print("Make sure MetaTrader 5 is running and logged in.", file=sys.stderr)
        sys.exit(1)

    print("Done. Then retrain: python scripts/run_ml_pipeline.py")


if __name__ == "__main__":
    main()
