"""Tests for the Auto tab semi-automation (launcher math + goal shutdown).

No live MT5: runner constructed in PAPER mode with tmp state dir; the
goal flag test drives _close_grid directly with a real GridBook.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from paper_trading.models import TradeMode  # noqa: E402
from paper_trading.runner import PaperTradingRunner  # noqa: E402
from strategy.live_grid import GridBook, GridConfig  # noqa: E402


def _book() -> GridBook:
    from datetime import datetime, timezone

    b = GridBook("EURUSD", "BUY", 1.10000, GridConfig(enabled=True))
    b.open_time = datetime.now(timezone.utc)
    return b


def _load_launcher():
    spec = importlib.util.spec_from_file_location(
        "run_demo_grid", ROOT / "scripts" / "run_demo_grid.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_loss_limit_for_is_two_percent_of_balance():
    mod = _load_launcher()
    assert mod.loss_limit_for(5000.0) == 100.0
    assert mod.loss_limit_for(8000.0) == 160.0


def _runner(tmp_path: Path) -> PaperTradingRunner:
    return PaperTradingRunner(
        symbols=["EURUSD"],
        mode=TradeMode.PAPER,
        state_dir=tmp_path,
        grid_config=GridConfig(enabled=True),
    )


def test_goal_reached_on_profit_limit(tmp_path):
    r = _runner(tmp_path)
    assert r._goal_reached is False
    r.grid_books["EURUSD"] = _book()
    r._close_grid("EURUSD", 1.10200, "PROFIT_LIMIT", pnl_override=60.0)
    assert r._goal_reached is True


def test_goal_reached_on_loss_limit(tmp_path):
    r = _runner(tmp_path)
    r.grid_books["EURUSD"] = _book()
    r._close_grid("EURUSD", 1.09000, "LOSS_LIMIT", pnl_override=-100.0)
    assert r._goal_reached is True


def test_no_goal_on_sl_fallback_or_max_hold(tmp_path):
    r = _runner(tmp_path)
    r.grid_books["EURUSD"] = _book()
    r._close_grid("EURUSD", 1.09500, "SL fallback")
    assert r._goal_reached is False
    r.grid_books["EURUSD"] = _book()
    r._close_grid("EURUSD", 1.10050, "max hold expired")
    assert r._goal_reached is False
