"""Tests for the flag-gated 3-layer Bollinger grid (strategy/live_grid.py).

Pure-function tests — no MT5 connection required. The GridBook math must
match signals/paper_sim.py (_layers_pnl and the +/-60 USD close rule).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from strategy.live_grid import PIP, GridBook, GridConfig, compute_bollinger  # noqa: E402
from risk.governor import GovernorConfig, GovernorState, next_state  # noqa: E402


def _cfg(**kw) -> GridConfig:
    return GridConfig(enabled=True, **kw)


def test_bollinger_sane_bands():
    rng = np.random.default_rng(7)
    closes = 1.10 + np.cumsum(rng.normal(0, 0.0005, 200))
    mid, upper, lower = compute_bollinger(closes, period=20, std=2.0)
    assert len(mid) == len(closes)
    assert np.isnan(mid[:19]).all()
    valid = ~np.isnan(mid)
    assert (upper[valid] >= mid[valid]).all()
    assert (lower[valid] <= mid[valid]).all()
    # mid is the rolling mean of the last 20 closes
    assert abs(mid[19] - closes[:20].mean()) < 1e-12


def test_grid_layers_match_paper_sim_semantics():
    book = GridBook("EURUSD", "BUY", 1.10000, _cfg())
    step = 10 * PIP
    assert [l.price for l in book.layers] == [1.10000, 1.10000 - step, 1.10000 - 2 * step]
    assert [l.lot for l in book.layers] == [0.30, 0.20, 0.20]
    assert [l.opened for l in book.layers] == [True, False, False]

    sell = GridBook("EURUSD", "SELL", 1.10000, _cfg())
    assert [l.price for l in sell.layers] == [1.10000, 1.10000 + step, 1.10000 + 2 * step]


def test_floating_pnl_sign_convention():
    book = GridBook("EURUSD", "BUY", 1.10000, _cfg())
    # +20 pips on 0.30 lots = 20 * 10 * 0.30 = 60 USD (paper_sim convention)
    assert abs(book.floating_pnl(1.10200) - 60.0) < 1e-6
    sell = GridBook("EURUSD", "SELL", 1.10000, _cfg())
    assert abs(sell.floating_pnl(1.09800) - 60.0) < 1e-6
    assert abs(sell.floating_pnl(1.10200) + 60.0) < 1e-6


def test_profit_limit_triggers_close_decision():
    book = GridBook("EURUSD", "BUY", 1.10000, _cfg())
    assert book.should_close(1.10200, 60.0, 60.0) == "PROFIT_LIMIT"
    assert book.should_close(1.10190, 60.0, 60.0) is None


def test_loss_limit_triggers_close_decision():
    book = GridBook("EURUSD", "BUY", 1.10000, _cfg())
    assert book.should_close(1.09800, 60.0, 60.0) == "LOSS_LIMIT"
    # limits disabled (governor default 0.0) => never closes on floating pnl
    assert book.should_close(1.05000, 0.0, 0.0) is None


def test_pending_layers_fill_in_order_and_pnl_aggregates():
    book = GridBook("EURUSD", "BUY", 1.10000, _cfg())
    # candle touches L2 (1.0990) but not L3
    newly = book.check_pending(low=1.09895, high=1.10050)
    assert len(newly) == 1 and newly[0].price == 1.10000 - 10 * PIP
    # candle touches L3
    newly = book.check_pending(low=1.09790, high=1.09900)
    assert len(newly) == 1
    assert all(l.opened for l in book.layers)
    # aggregated pnl: sum over 3 layers at price 1.0980
    price = 1.09800
    expected = ((price - 1.10000) * 0.30 + (price - 1.09900) * 0.20 + (price - 1.09800) * 0.20) * 100000
    assert abs(book.floating_pnl(price) - expected) < 1e-6


def test_grid_disabled_by_default_and_governor_limits_off():
    assert GridConfig().enabled is False
    gc = GovernorConfig()
    assert gc.profit_limit_usd == 0.0
    assert gc.loss_limit_usd == 0.0
    # governor loss logic unchanged
    st = next_state(GovernorState(consecutive_losses=5), gc)
    assert st.mode == "LOCKDOWN"
    demo = GovernorConfig(profit_limit_usd=60.0, loss_limit_usd=60.0)
    assert demo.profit_limit_usd == 60.0 and demo.loss_limit_usd == 60.0
