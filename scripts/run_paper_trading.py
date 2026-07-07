"""Real-time paper trading loop for SMC Successor.

Polls MT5 every 5 seconds for new M15 candles. When a candle closes,
runs the full signal pipeline and manages virtual positions.

Usage:
    python scripts/run_paper_trading.py
    python scripts/run_paper_trading.py --symbols EURUSD,GBPUSD --timeframe M15
    python scripts/run_paper_trading.py --min-confidence 0.70 --risk 0.5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from data.mt5.connector import ConnectionConfig
from paper_trading.runner import POLL_INTERVAL, PaperTradingRunner
from signals.pipeline import ScalpingConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-time paper trading loop")
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

    try:
        runner.run()
    except KeyboardInterrupt:
        print("\nShutdown complete.")
    except ConnectionError as e:
        print(f"ERROR: Cannot connect to MT5: {e}", file=sys.stderr)
        print("Make sure MetaTrader 5 terminal is running.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
