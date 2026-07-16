"""tests/test_r6_fill_next_open.py — R6.2 (G2): fill next_open.

El precio de ENTRADA debe ser el OPEN de la vela SIGUIENTE a la senal
(fill realista de produccion), no el close de la vela de senal (teoria).

Contrato:
- fill_mode='next_open' (default produccion) -> entry == open[entry_at + 1]
- fill_mode='signal_close' (theory)        -> entry == close[entry_at]
"""

from __future__ import annotations

import pandas as pd
import pytest

from ict_backtest.engine import ICTSignal, simulate_trade, fill_entry_price


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        "time": ["2024-01-01 10:00", "2024-01-01 10:15", "2024-01-01 10:30"],
        "open": [1.1000, 1.1010, 1.1020],
        "high": [1.1020, 1.1030, 1.1040],
        "low": [1.0990, 1.1000, 1.1010],
        "close": [1.1010, 1.1020, 1.1030],
    })


def test_fill_entry_next_open_uses_next_bar_open():
    frame = _frame()
    entry_at = 0
    price = fill_entry_price(frame, entry_at, "next_open")
    assert price == float(frame.iloc[entry_at + 1]["open"]) == 1.1010


def test_fill_entry_signal_close_uses_signal_bar_close():
    frame = _frame()
    entry_at = 0
    price = fill_entry_price(frame, entry_at, "signal_close")
    assert price == float(frame.iloc[entry_at]["close"]) == 1.1010


def test_fill_entry_invalid_mode_raises():
    frame = _frame()
    with pytest.raises(ValueError):
        fill_entry_price(frame, 0, "bogus")


def test_simulate_trade_respects_passed_entry():
    """simulate_trade no re-fija el entry: usa el que le pasan (next_open o close)."""
    frame = _frame()
    for mode in ("next_open", "signal_close"):
        entry_at = 0
        entry = fill_entry_price(frame, entry_at, mode)
        sig = ICTSignal(symbol="X", time="2024-01-01 10:00", direction=1,
                        entry=entry, stop_loss=entry - 0.001,
                        take_profit=entry + 0.003, entry_at=entry_at)
        trade, meta = simulate_trade(frame, sig, max_hold_bars=1)
        assert trade is not None
        assert float(trade.entry) == entry
        assert meta["exit_reason"] in ("SL", "TP", "hold_limit")
