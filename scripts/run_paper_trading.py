"""Real-time paper trading loop with live status dashboard.

Features:
  - Live status bar showing current symbol, poll cycle, uptime
  - Position summary (open PnL, total trades)
  - Governor state display
  - Signal detection counter

Usage:
  python scripts/run_paper_trading.py
  python scripts/run_paper_trading.py --symbols EURUSD,GBPUSD --timeframe M15
  python scripts/run_paper_trading.py --min-confidence 0.70 --risk 0.5
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from data.mt5.connector import ConnectionConfig
from paper_trading.runner import POLL_INTERVAL, PaperTradingRunner
from signals.pipeline import ScalpingConfig


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"


def _clear_line():
    sys.stdout.write("\r\033[K")


def _print_dashboard(
    cycle: int,
    uptime: float,
    current_symbol: str,
    open_positions: int,
    total_trades: int,
    signals_found: int,
    governor_mode: str,
    last_action: str,
):
    """Print a compact live dashboard line."""
    now = datetime.now().strftime("%H:%M:%S")
    bar_width = 30
    # Cycle progress within current symbol scan (approximate)
    pct = min(100, (cycle % 100))  # rough indicator

    line = (
        f"\r[{now}] Cycle #{cycle:>5} | "
        f"Uptime: {_fmt_duration(uptime):>8} | "
        f"Symbol: {current_symbol:<8} | "
        f"Positions: {open_positions} | "
        f"Trades: {total_trades:>3} | "
        f"Signals: {signals_found:>3} | "
        f"Gov: {governor_mode:<10} | "
        f"{last_action}"
    )
    # Truncate to terminal width
    max_width = 140
    if len(line) > max_width:
        line = line[:max_width - 3] + "..."
    sys.stdout.write(line)
    sys.stdout.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-time paper trading loop with live dashboard")
    parser.add_argument("--symbols", type=str, default="EURUSD,GBPUSD,USDJPY,USDCHF",
                        help="Comma-separated symbols to trade")
    parser.add_argument("--timeframe", type=str, default="M15",
                        help="Timeframe for signal generation (M15, H1, etc.)")
    parser.add_argument("--data-dir", type=str, default="data/raw",
                        help="Directory for parquet data")
    parser.add_argument("--state-dir", type=str, default="data/paper_trading",
                        help="Directory for position/trade state")
    parser.add_argument("--min-confidence", type=float, default=0.65,
                        help="Minimum signal confidence to open a position")
    parser.add_argument("--max-hold", type=int, default=16,
                        help="Maximum bars to hold a position before expiry")
    parser.add_argument("--risk", type=float, default=1.0,
                        help="Risk percent per trade (%% of account)")
    parser.add_argument("--commission", type=float, default=0.0,
                        help="Commission per lot")
    parser.add_argument("--bars", type=int, default=500,
                        help="Bars to download for each pipeline run")
    parser.add_argument("--trend-threshold", type=float, default=0.45,
                        help="Trend confidence threshold")
    parser.add_argument("--min-confluence", type=int, default=2,
                        help="Minimum confluence score")
    parser.add_argument("--min-atr", type=float, default=1.0,
                        help="Minimum ATR ratio")
    parser.add_argument("--ob-fvg-proximity", type=float, default=1.5,
                        help="OB/FVG proximity in ATR units")
    parser.add_argument("--no-ml", action="store_true",
                        help="Disable ML quality filter")
    parser.add_argument("--ml-model", type=str, default="ml/models/quality_filter.pkl",
                        help="Path to ML quality filter model")
    parser.add_argument("--no-agents", action="store_true",
                        help="Disable AI agents (ICT/Wyckoff/Structure)")
    parser.add_argument("--relaxed-bos", action="store_true",
                        help="Use relaxed BOS detection")
    parser.add_argument("--mt5-path", type=str, default=None,
                        help="Path to Funded Next / MT5 terminal executable")

    args = parser.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    if not symbols:
        print("ERROR: at least one symbol required", file=sys.stderr)
        sys.exit(1)

    config = ScalpingConfig(
        trend_confidence_threshold=args.trend_threshold,
        min_confluence_score=args.min_confluence,
        min_atr_ratio=args.min_atr,
        ob_fvg_proximity_atr=args.ob_fvg_proximity,
        relaxed_bos=args.relaxed_bos,
        use_ml_quality_filter=not args.no_ml and not args.no_agents,
        ml_model_path=args.ml_model,
    )

    connector_config = ConnectionConfig(path=args.mt5_path) if args.mt5_path else None

    # Print header
    print("=" * 60)
    print("  SMC-SYSTEMS - Paper Trading (Live Dashboard)")
    print("=" * 60)
    print(f"  Symbols:    {', '.join(symbols)}")
    print(f"  Timeframe:  {args.timeframe}")
    print(f"  Confidence: {args.min_confidence}")
    print(f"  Risk:       {args.risk}% per trade")
    print(f"  ML Filter:  {'OFF' if args.no_ml else 'ON'}")
    print(f"  Agents:     {'OFF' if args.no_agents else 'ON'}")
    print(f"  Poll:       every {POLL_INTERVAL}s")
    print("=" * 60)
    print()

    runner = PaperTradingRunner(
        symbols=symbols,
        timeframe=args.timeframe,
        connector_config=connector_config,
        data_dir=Path(args.data_dir),
        state_dir=Path(args.state_dir),
        min_confidence=args.min_confidence,
        max_hold_bars=args.max_hold,
        scalping_config=config,
        risk_percent=args.risk,
        commission_per_lot=args.commission,
        bars_for_pipeline=args.bars,
    )

    # Patch the runner to expose live stats
    runner._cycle_count = 0
    runner._signals_found = 0
    runner._last_action = "Initializing..."
    runner._current_symbol = "-"
    start_time = time.time()

    # Wrap the original _process_symbol to track stats
    original_process = runner._process_symbol

    def wrapped_process(symbol: str):
        runner._current_symbol = symbol
        runner._last_action = f"Scanning {symbol}..."
        result = original_process(symbol)
        runner._last_action = f"Done {symbol}"
        return result

    runner._process_symbol = wrapped_process

    try:
        runner.running = True
        mode_label = runner.mode.value
        runner._log(f"PaperTradingRunner started - symbols={symbols} timeframe={args.timeframe} mode={mode_label}")
        runner._log(f"Polling MT5 every {POLL_INTERVAL}s, checking for new {args.timeframe} candles")
        runner._log(f"State dir: {runner.state_dir.resolve()}")

        if not runner._ensure_mt5_running():
            runner.running = False
            return

        from data.mt5.connector import MT5Connector
        with MT5Connector(runner.connector_config) as connector:
            runner.connector = connector
            info = connector.terminal_info()
            runner._log(f"Connected: {info.get('name', 'unknown')}")

            from paper_trading.persistence import load_positions, load_governor_state
            runner.positions = load_positions(runner.state_path)
            if runner.positions:
                runner._log(f"Restored {len(runner.positions)} open positions")

            persisted_governor = load_governor_state(runner.governor_path)
            if persisted_governor:
                runner.governor = persisted_governor
                runner._log(f"Restored governor state: {runner.governor.mode}")

            for symbol in symbols:
                runner._log(f"Initializing {symbol}...")
                try:
                    runner._refresh_data(symbol)
                    runner._log(f"  {symbol} data ready")
                except Exception as e:
                    runner._log(f"  {symbol} init error: {e}")

            runner._log("Dashboard active - press Ctrl+C to stop")
            print()

            try:
                while runner.running:
                    if runner._check_kill_switch():
                        break
                    runner._check_drift()
                    for symbol in symbols:
                        try:
                            wrapped_process(symbol)
                        except Exception as e:
                            runner._log(f"{symbol} error: {e}")
                    runner._save_state()
                    runner._cycle_count += 1

                    # Update dashboard
                    uptime = time.time() - start_time
                    _print_dashboard(
                        cycle=runner._cycle_count,
                        uptime=uptime,
                        current_symbol=runner._current_symbol,
                        open_positions=len(runner.positions),
                        total_trades=len(runner.trade_log),
                        signals_found=runner._signals_found,
                        governor_mode=runner.governor.mode,
                        last_action=runner._last_action,
                    )

                    time.sleep(POLL_INTERVAL)
            except KeyboardInterrupt:
                runner._log("Shutting down...")
            finally:
                runner._save_state()
                runner._log(f"Positions saved. Total trades: {len(runner.trade_log)}")

    except ConnectionError as e:
        print(f"ERROR: Cannot connect to MT5: {e}", file=sys.stderr)
        print("Make sure MetaTrader 5 terminal is running.", file=sys.stderr)
        sys.exit(1)

    print("\n\nShutdown complete.")


if __name__ == "__main__":
    main()
