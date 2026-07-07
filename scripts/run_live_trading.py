"""Run the trading system in LIVE mode."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from paper_trading.models import TradeMode
from paper_trading.runner import PaperTradingRunner
from signals.pipeline import ScalpingConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Live trading runner")
    parser.add_argument("--symbols", nargs="+", default=["XAUUSD", "EURUSD", "GBPUSD"])
    parser.add_argument("--timeframe", default="M15")
    parser.add_argument("--mode", choices=["PAPER", "LIVE"], default="PAPER")
    parser.add_argument("--risk", type=float, default=1.0)
    parser.add_argument("--confidence", type=float, default=0.65)
    parser.add_argument("--magic", type=int, default=20260701)
    parser.add_argument("--deviation", type=int, default=10)
    parser.add_argument("--kill-switch", type=str, default="data/KILL_SWITCH")
    parser.add_argument("--no-ml", action="store_true", help="Disable ML quality filter")
    parser.add_argument("--ml-model", type=str, default="ml/models/quality_filter.pkl")
    parser.add_argument(
        "--drift-check",
        action="store_true",
        help="Enable live PSI drift monitoring vs training baseline (forces LOCKDOWN on drift)",
    )
    parser.add_argument("--drift-threshold", type=float, default=0.2)
    parser.add_argument("--drift-every", type=int, default=60, help="Check drift every N poll cycles")
    args = parser.parse_args()

    scalping = ScalpingConfig(
        use_ml_quality_filter=not args.no_ml,
        ml_model_path=args.ml_model,
    )

    runner = PaperTradingRunner(
        symbols=args.symbols,
        timeframe=args.timeframe,
        mode=TradeMode(args.mode),
        risk_percent=args.risk,
        min_confidence=args.confidence,
        magic=args.magic,
        deviation=args.deviation,
        kill_switch_path=Path(args.kill_switch),
        scalping_config=scalping,
        drift_check_enabled=args.drift_check,
        drift_threshold=args.drift_threshold,
        drift_check_every=args.drift_every,
    )
    try:
        runner.run()
    except KeyboardInterrupt:
        print("\nShutdown requested")
    finally:
        print("Runner stopped")


if __name__ == "__main__":
    main()
