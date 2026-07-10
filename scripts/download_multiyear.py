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

# Make the project root importable when run as `python scripts/download_multiyear.py`
# (otherwise `data/__init__.py` cannot find the top-level `_data_legacy` module).
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tqdm import tqdm

from data.mt5.connector import ConnectionConfig, MT5Connector
from _data_legacy import MT5_TERMINAL_PATH

# Approximate bars per year per timeframe — used to size the chunked download
# so the progress bar knows the total before MT5 starts streaming.
_BARS_PER_YEAR = {
    "M1": 365 * 24 * 60,
    "M5": 365 * 24 * 12,
    "M15": 365 * 24 * 4,
    "M30": 365 * 24 * 2,
    "H1": 365 * 24,
    "H4": 365 * 6,
    "D1": 365,
}


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

    years_span = max((date_to - date_from).days / 365.25, 0.1)
    # Build the full list of (symbol, tf) jobs up front so tqdm can show total.
    jobs = [(s, tf) for s in args.symbols for tf in args.timeframes]
    total_jobs = len(jobs)
    done = 0

    print(f"Window: {date_from.date()} -> {date_to.date()} "
          f"(~{round(years_span, 2)} years) | {total_jobs} downloads")

    try:
        with MT5Connector(config=ConnectionConfig(path=MT5_TERMINAL_PATH)) as mt5:
            ti = mt5.terminal_info()
            if ti is None:
                account = mt5.account_info()
                if account is None:
                    raise ConnectionError(
                        "MT5 abierto pero SIN sesion/login (terminal_info y account_info son None). "
                        "Abre MetaTrader 5, entra a tu cuenta y confirmá 'Conectado' arriba a la derecha."
                    )
                print(f"Connected: {ti.get('name', 'unknown') if ti else 'n/a'}")
            else:
                print(f"Connected: {ti.get('name', 'unknown')}")
            with tqdm(total=total_jobs, desc="Global", unit="dl", ascii=True) as pbar:
                for symbol, tf in jobs:
                    path = output_dir / f"{symbol}_{tf}.parquet"
                    if path.exists():
                        tqdm.write(f"  {symbol} {tf}: exists, skipping ({path.name})")
                        done += 1
                        pbar.update(1)
                        continue
                    # Estimate how many bars cover the window (with 10% margin).
                    per_year = _BARS_PER_YEAR.get(tf.upper(), 365 * 24 * 4)
                    count_est = int(per_year * years_span * 1.1) + 100
                    tqdm.write(f"  Downloading {symbol} {tf} "
                               f"(~{count_est} bars expected) ...")
                    df = mt5.download_rates(symbol, tf, count=count_est)
                    # Keep only the requested calendar window.
                    df = df[(df["time"] >= date_from) & (df["time"] <= date_to)]
                    if df is None or len(df) == 0:
                        tqdm.write(" NO DATA")
                        done += 1
                        pbar.update(1)
                        continue
                    df.to_parquet(path, index=False)
                    tqdm.write(f" {len(df)} bars  {df['time'].iloc[0]} -> {df['time'].iloc[-1]}")
                    done += 1
                    pbar.update(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print("Make sure MetaTrader 5 is running and logged in.", file=sys.stderr)
        sys.exit(1)

    print(f"Done ({done}/{total_jobs}). Then retrain: python scripts/run_ml_pipeline.py")


if __name__ == "__main__":
    main()
