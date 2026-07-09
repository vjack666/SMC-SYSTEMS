"""Download multi-year OHLCV data via MT5 with full progress tracking.

Features:
  - Per-file progress bar with ETA and MB downloaded
  - Global progress bar across all symbol/timeframe combinations
  - Chunked downloads by year (bypasses MT5 ~50k bar limit)
  - Skips existing files (use --force to re-download)
  - Shows total estimated size before starting

Requirements:
  - MetaTrader 5 terminal open and logged in
  - pip install -e .

Example:
  python scripts/download_data.py --symbols EURUSD GBPUSD USDCHF USDJPY \
      --years 4 --timeframes M15 H4 D1 --output data/raw
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tqdm import tqdm

from data.mt5.connector import ConnectionConfig, MT5Connector
from _data_legacy import MT5_TERMINAL_PATH

# Bars per year per timeframe
_BARS_PER_YEAR = {
    "M1": 365 * 24 * 60,
    "M5": 365 * 24 * 12,
    "M15": 365 * 24 * 4,
    "M30": 365 * 24 * 2,
    "H1": 365 * 24,
    "H4": 365 * 6,
    "D1": 365,
}

# Approximate bytes per bar (OHLCV + time + volume + spread)
_BYTES_PER_BAR = 64

# Max bars per single MT5 request (copy_rates_from_pos limit)
_MT5_MAX_BARS = 50_000


def _resolve_date_from(date_from: str | None, years: float) -> datetime:
    if date_from:
        return datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - timedelta(days=int(years * 365.25))


def _fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    return f"{n / 1024 ** 3:.2f} GB"


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"


def _estimate_total_bytes(symbols: list[str], timeframes: list[str], years_span: float) -> int:
    total = 0
    for tf in timeframes:
        bars = int(_BARS_PER_YEAR.get(tf.upper(), 365 * 24 * 4) * years_span * 1.1) + 100
        total += bars * _BYTES_PER_BAR * len(symbols)
    return total


def _build_yearly_chunks(date_from: datetime, date_to: datetime, tf: str) -> list[tuple[datetime, datetime]]:
    """Split a date range into yearly chunks so each chunk stays under MT5 bar limit."""
    bars_per_year = _BARS_PER_YEAR.get(tf.upper(), 365 * 24 * 4)
    # If a full year fits under the limit, use 1-year chunks; otherwise split further
    if bars_per_year >= _MT5_MAX_BARS:
        # For M1/M5, use monthly chunks
        chunks = []
        current = date_from
        while current < date_to:
            next_month = min(current + timedelta(days=31), date_to)
            # Align to month boundary
            next_month = datetime(next_month.year, next_month.month, 1, tzinfo=timezone.utc)
            if next_month > date_to:
                next_month = date_to
            if next_month > current:
                chunks.append((current, next_month))
            current = next_month
        return chunks
    else:
        # Use yearly chunks
        chunks = []
        current = date_from
        while current < date_to:
            next_year = datetime(current.year + 1, 1, 1, tzinfo=timezone.utc)
            if next_year > date_to:
                next_year = date_to
            if next_year > current:
                chunks.append((current, next_year))
            current = next_year
        return chunks


def _download_chunked(
    mt5: MT5Connector,
    symbol: str,
    tf: str,
    date_from: datetime,
    date_to: datetime,
    file_bar: tqdm,
) -> pd.DataFrame:
    """Download data in date-range chunks and concatenate."""
    chunks = _build_yearly_chunks(date_from, date_to, tf)
    all_parts: list[pd.DataFrame] = []

    for chunk_from, chunk_to in chunks:
        try:
            df = mt5.download_rates_range(symbol, tf, chunk_from, chunk_to)
            if df is not None and len(df) > 0:
                all_parts.append(df)
                file_bar.update(len(df))
        except Exception:
            # If range download fails, try copy_rates_from_pos as fallback
            try:
                per_year = _BARS_PER_YEAR.get(tf.upper(), 365 * 24 * 4)
                count = int((chunk_to - chunk_from).days / 365.25 * per_year) + 100
                df = mt5.download_rates(symbol, tf, count=count)
                if df is not None and len(df) > 0:
                    df = df[(df["time"] >= chunk_from) & (df["time"] <= chunk_to)]
                    if len(df) > 0:
                        all_parts.append(df)
                        file_bar.update(len(df))
            except Exception:
                pass

    if not all_parts:
        return pd.DataFrame()

    combined = pd.concat(all_parts, ignore_index=True)
    # Deduplicate by time
    combined = combined.drop_duplicates(subset=["time"], keep="last")
    combined = combined.sort_values("time").reset_index(drop=True)
    return combined


def main() -> None:
    parser = argparse.ArgumentParser(description="Download multi-year OHLCV via MT5 with progress tracking")
    parser.add_argument("--symbols", nargs="+", required=True, help="e.g. EURUSD GBPUSD USDCHF USDJPY XAUUSD")
    parser.add_argument(
        "--timeframes", nargs="+", default=["M15", "H4", "D1"],
        help="Timeframes to download (default: M15 H4 D1)",
    )
    parser.add_argument("--years", type=float, default=4.0, help="Lookback window in years (default: 4)")
    parser.add_argument("--from", dest="date_from", type=str, default=None,
                        help="Explicit start date ISO (e.g. 2022-01-01). Overrides --years.")
    parser.add_argument("--to", dest="date_to", type=str, default=None,
                        help="Explicit end date ISO (default: now)")
    parser.add_argument("--output", type=str, default="data/raw")
    parser.add_argument("--force", action="store_true", help="Re-download even if file exists")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    date_from = _resolve_date_from(args.date_from, args.years)
    date_to = (
        datetime.fromisoformat(args.date_to).replace(tzinfo=timezone.utc)
        if args.date_to else datetime.now(timezone.utc)
    )

    years_span = max((date_to - date_from).days / 365.25, 0.1)

    # Build job list
    jobs = [(s, tf) for s in args.symbols for tf in args.timeframes]

    # Check which files already exist
    existing = []
    pending = []
    for symbol, tf in jobs:
        path = output_dir / f"{symbol}_{tf}.parquet"
        if path.exists() and not args.force:
            existing.append((symbol, tf, path))
        else:
            pending.append((symbol, tf))

    # Estimate sizes
    total_est_bytes = _estimate_total_bytes(args.symbols, args.timeframes, years_span)
    pending_est_bytes = _estimate_total_bytes(
        [s for s, _ in pending], args.timeframes, years_span
    )

    # Count total chunks for accurate progress
    total_chunks = 0
    for symbol, tf in pending:
        chunks = _build_yearly_chunks(date_from, date_to, tf)
        total_chunks += len(chunks)

    # Print summary
    print("=" * 60)
    print("  SMC-SYSTEMS - Data Downloader (A6)")
    print("=" * 60)
    print(f"  Window:    {date_from.strftime('%Y-%m-%d')} -> {date_to.strftime('%Y-%m-%d')}")
    print(f"  Span:      ~{years_span:.1f} years")
    print(f"  Symbols:   {', '.join(args.symbols)}")
    print(f"  Timeframes: {', '.join(args.timeframes)}")
    print(f"  Output:    {output_dir.resolve()}")
    print(f"  Est. size: ~{_fmt_bytes(total_est_bytes)} total")
    print(f"  Jobs:      {len(jobs)} total, {len(existing)} existing, {len(pending)} to download")
    if total_chunks > len(pending):
        print(f"  Chunks:    {total_chunks} (split by year to bypass MT5 limits)")
    print("=" * 60)

    if not pending:
        print("All files already exist. Use --force to re-download.")
        return

    if existing:
        print("\nSkipping existing files:")
        for symbol, tf, path in existing:
            size = path.stat().st_size
            print(f"  {symbol}_{tf}.parquet ({_fmt_bytes(size)})")

    print(f"\nStarting download of {len(pending)} files (~{_fmt_bytes(pending_est_bytes)})...\n")

    start_time = time.time()
    total_bytes_downloaded = 0
    total_bars_downloaded = 0
    completed = 0
    failed = 0

    try:
        with MT5Connector(config=ConnectionConfig(path=MT5_TERMINAL_PATH)) as mt5:
            info = mt5.terminal_info()
            print(f"Connected: {info.get('name', 'unknown')} ({info.get('company', '')})\n")

            # Global progress bar
            with tqdm(total=len(pending), desc="Overall", unit="file", ascii=True,
                      bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]") as global_bar:

                for symbol, tf in pending:
                    path = output_dir / f"{symbol}_{tf}.parquet"
                    per_year = _BARS_PER_YEAR.get(tf.upper(), 365 * 24 * 4)
                    count_est = int(per_year * years_span * 1.1) + 100

                    # Per-file progress bar (tracks total bars across all chunks)
                    with tqdm(total=count_est, desc=f"{symbol} {tf}", unit="bars",
                              unit_scale=True, ascii=True,
                              bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]") as file_bar:

                        try:
                            df = _download_chunked(mt5, symbol, tf, date_from, date_to, file_bar)

                            if df is None or len(df) == 0:
                                tqdm.write(f"  [SKIP] {symbol} {tf}: no data in window")
                                failed += 1
                                file_bar.close()
                                global_bar.update(1)
                                continue

                            # Save to parquet
                            df.to_parquet(path, index=False)
                            file_size = path.stat().st_size
                            actual_bars = len(df)

                            # Update file bar to actual count
                            file_bar.n = actual_bars
                            file_bar.total = actual_bars
                            file_bar.refresh()
                            file_bar.close()

                            total_bytes_downloaded += file_size
                            total_bars_downloaded += actual_bars
                            completed += 1

                            tqdm.write(
                                f"  [OK] {symbol}_{tf}.parquet | "
                                f"{actual_bars:,} bars | {_fmt_bytes(file_size)} | "
                                f"{df['time'].iloc[0].strftime('%Y-%m-%d')} -> {df['time'].iloc[-1].strftime('%Y-%m-%d')}"
                            )

                        except Exception as e:
                            file_bar.close()
                            tqdm.write(f"  [FAIL] {symbol} {tf}: {e}")
                            failed += 1

                    global_bar.update(1)

    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        print("Make sure MetaTrader 5 is running and logged in.", file=sys.stderr)
        sys.exit(1)

    elapsed = time.time() - start_time

    # Final summary
    print("\n" + "=" * 60)
    print("  DOWNLOAD COMPLETE")
    print("=" * 60)
    print(f"  Files:       {completed} OK, {failed} failed, {len(existing)} skipped")
    print(f"  Total bars:  {total_bars_downloaded:,}")
    print(f"  Total size:  {_fmt_bytes(total_bytes_downloaded)}")
    print(f"  Time:        {_fmt_duration(elapsed)}")
    print(f"  Speed:       {_fmt_bytes(int(total_bytes_downloaded / max(elapsed, 1)))}/s")
    print("=" * 60)

    if completed > 0:
        print(f"\nNext step: retrain models")
        print(f"  python scripts/run_ml_pipeline.py")
        print(f"\nOr run backtest:")
        print(f"  python -c \"from backtest.engine import run_combined_backtest; m, t = run_combined_backtest(); print(m)\"")


if __name__ == "__main__":
    main()
