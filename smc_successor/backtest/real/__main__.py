from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from smc_successor.backtest.engine import (
    CombinedBacktestConfig,
    ProgressCB,
    metrics_pass_thresholds,
    run_combined_backtest,
)
from smc_successor.risk import GovernorConfig
from smc_successor.signals import ScalpingConfig
from smc_successor.data.mt5.connector import MT5Connector


_stages: dict[str, str] = {}


def _on_progress(stage: str, current: int, total: int, message: str) -> None:
    if stage == "download":
        _draw_bar("Downloading", current, total, 30, suffix=message)
    elif stage == "timeframe":
        print(f"\r  Timeframe [{current+1}/{total}]: {message}    ")
    elif stage == "symbol":
        print(f"\n--- Symbol [{current+1}/{total}]: {message} ---")
    elif stage == "signals":
        _draw_bar("Signals", current, total, 30, suffix=message)
    elif stage == "context":
        _draw_bar("Context", current, total, 20, suffix=message)
    elif stage == "backtest":
        _draw_bar("Backtest", current, total, 30, suffix=message)


def _draw_bar(label: str, current: int, total: int, width: int = 30, suffix: str = "") -> None:
    if total <= 0:
        return
    pct = current / total
    filled = int(width * pct)
    bar = "#" * filled + "." * (width - filled)
    print(f"\r  {label}: |{bar}| {current}/{total} ({pct*100:.0f}%) {suffix}", end="")


def _parquet_bar_count(path: Path) -> int:
    try:
        import pyarrow.parquet as pq
        pf = pq.ParquetFile(path)
        return pf.metadata.num_rows
    except Exception:
        try:
            return len(pd.read_parquet(path))
        except Exception:
            return 0


def _max_bars_for_timeframe(tf: str) -> int:
    mapping = {
        "M1": 100_000,
        "M5": 100_000,
        "M15": 100_000,
        "M30": 50_000,
        "H1": 50_000,
        "H4": 20_000,
        "D1": 5_000,
        "W1": 1_000,
        "MN1": 500,
    }
    return mapping.get(tf, 10_000)


def ensure_data(
    connector: MT5Connector,
    symbol: str,
    timeframes: list[str],
    output_dir: Path,
    count: int,
) -> None:
    for i, tf in enumerate(timeframes, 1):
        max_bars = _max_bars_for_timeframe(tf)
        dl_count = min(count, max_bars)
        parquet_path = output_dir / f"{symbol}_{tf}.parquet"
        if parquet_path.exists():
            existing = _parquet_bar_count(parquet_path)
            if existing >= dl_count:
                print(f"  [{i}/{len(timeframes)}] {symbol} {tf}: cached ({existing} bars)")
                continue
            print(f"  [{i}/{len(timeframes)}] {symbol} {tf}: cached {existing} -> re-downloading {dl_count}")
        else:
            print(f"  [{i}/{len(timeframes)}] {symbol} {tf}: downloading {dl_count} bars")
        connector.download_and_save(symbol, tf, dl_count, output_dir, progress_cb=_on_progress)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SMC_SUCCESSOR backtest with real MT5 data")
    parser.add_argument("--symbols", type=str, nargs="+", default=["EURUSD"],
                        help="Symbols to backtest")
    parser.add_argument("--timeframe", type=str, default="M15", help="Trading timeframe")
    parser.add_argument("--count", type=int, default=50_000, help="Bars to download per symbol")
    parser.add_argument("--data-dir", type=str, default="data/raw", help="Parquet data directory")
    parser.add_argument("--output-dir", type=str, default="results", help="Results output directory")
    parser.add_argument("--min-confidence", type=float, default=0.52, help="Minimum signal confidence")
    parser.add_argument("--max-hold", type=int, default=16, help="Maximum hold bars")
    parser.add_argument("--no-ml", action="store_true", help="Disable ML quality filter")
    parser.add_argument("--permissive", action="store_true",
                        help="Permissive mode: disables governor lockdown and lowers signal thresholds for data collection")

    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    symbols = args.symbols
    timeframes_to_dl = list(dict.fromkeys([args.timeframe, "H4", "D1"]))  # dedup preserving order

    print("=" * 60)
    print("SMC_SUCCESSOR — Real Backtest")
    print("=" * 60)
    print()

    try:
        with MT5Connector() as connector:
            print(f"MT5 terminal: {connector.terminal_info().get('name', 'unknown')}")
            info = connector.account_info()
            print(f"Account:       {info.get('login', 'unknown')}  Balance: {info.get('balance', '?')}  Currency: {info.get('currency', '?')}")
            print()

            for symbol in symbols:
                ensure_data(connector, symbol, timeframes_to_dl, data_dir, args.count)

    except ConnectionError as e:
        print(f"ERROR: Cannot connect to MT5: {e}", file=sys.stderr)
        print("Make sure MetaTrader 5 terminal is running.", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print("[1/5] MT5 download complete")
    print("[2/5] Loading parquet data...")

    if args.permissive:
        scalping_cfg = ScalpingConfig(
            min_confluence_score=1,
            trend_confidence_threshold=0.20,
            relaxed_bos=True,
            min_atr_ratio=0.5,
        )
        governor_cfg = GovernorConfig(
            caution_after_losses=999,
            defensive_after_losses=999,
            lockdown_after_losses=999,
            caution_total_dd=50.0,
            defensive_total_dd=75.0,
            lockdown_total_dd=100.0,
        )
    else:
        scalping_cfg = ScalpingConfig()
        governor_cfg = GovernorConfig()

    config = CombinedBacktestConfig(
        data_dir=data_dir,
        symbols=tuple(symbols),
        timeframe=args.timeframe,
        min_confidence=args.min_confidence,
        max_hold_bars=args.max_hold,
        use_ml_quality_filter=not args.no_ml,
        scalping_config=scalping_cfg,
        risk_governor=governor_cfg,
    )

    print("[3/5] Building signals & simulating trades...")

    try:
        metrics, trades_df = run_combined_backtest(config, progress_cb=_on_progress)
    except RuntimeError as e:
        print(f"Backtest failed: {e}", file=sys.stderr)
        sys.exit(1)

    print("[4/5] Writing results...")

    trades_path = output_dir / "trades.csv"
    trades_df.to_csv(trades_path, index=False)
    print(f"Trades:  {trades_path}")

    metrics_path = output_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    print(f"Metrics: {metrics_path}")

    equity = trades_df["pnl_r"].cumsum()
    equity_df = pd.DataFrame({
        "trade": range(1, len(trades_df) + 1),
        "entry_time": trades_df["entry_time"],
        "pnl_r": trades_df["pnl_r"],
        "equity_r": equity,
    })
    equity_path = output_dir / "equity_curve.csv"
    equity_df.to_csv(equity_path, index=False)
    print(f"Equity:  {equity_path}")

    print()
    print("Results:")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    passed = metrics_pass_thresholds(metrics)
    print()
    print(f"Thresholds: {'PASSED' if passed else 'FAILED'}")
    print("[5/5] Done")


if __name__ == "__main__":
    main()
