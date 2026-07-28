"""Headless launcher: paper (DEMO) grid runner with goal-based auto-shutdown.

Starts the existing PaperTradingRunner in PAPER mode (no real orders) with the
3-layer Bollinger grid enabled. The runner exits by itself when a grid closes
on PROFIT_LIMIT (+$60 fixed) or LOSS_LIMIT (-2% of account balance).

Launched/killed by the observador "Auto" tab via process_control.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROFIT_LIMIT_USD = 60.0
LOSS_PCT = 0.02
DEFAULT_BALANCE = 5000.0


def loss_limit_for(balance: float) -> float:
    """Loss limit = 2% of the account balance (Ruben's rule, NOT fixed $60)."""
    return LOSS_PCT * balance


def current_balance() -> float:
    """Live MT5 balance when available, else the 5000.0 default."""
    try:
        import MetaTrader5 as mt5

        if mt5.initialize():
            info = mt5.account_info()
            if info is not None and float(info.balance) > 0:
                return float(info.balance)
    except Exception:
        pass
    return DEFAULT_BALANCE


def build_runner():
    from paper_trading.models import TradeMode
    from paper_trading.runner import PaperTradingRunner
    from risk.governor import GovernorConfig
    from strategy.live_grid import GridConfig

    balance = current_balance()
    return PaperTradingRunner(
        symbols=["EURUSD"],
        timeframe="M15",
        mode=TradeMode.PAPER,
        grid_config=GridConfig(enabled=True, l1_lot=0.30, l2_lot=0.20, grid_step_pips=10),
        governor_config=GovernorConfig(
            profit_limit_usd=PROFIT_LIMIT_USD,
            loss_limit_usd=loss_limit_for(balance),
        ),
    )


def main() -> None:
    log_path = ROOT / "data" / "run_demo_grid.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_path),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.info("run_demo_grid starting (PAPER/DEMO mode)")
    runner = build_runner()
    runner.run()
    logging.info("run_demo_grid finished")


if __name__ == "__main__":
    main()
