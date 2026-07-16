"""tests/test_r6_costs_on.py — R6.3 (G3): costos ON por defecto en produccion.

La balanza profesional mide CON costos de mercado reales por defecto.
El modo teoria (sin costos) es opt-in via --no-cost.

Contrato:
- resolve_cost(symbol) devuelve la tabla real del simbolo (spread/commission/slippage).
- resolve_cost(symbol, no_cost=True) -> None (modo teoria).
- resolve_cost(symbol, override="1.0,0.5,0.3") usa el override explicito.
- simulate_trade con cost resta comision y aplica spread/slippage (pnl empeora).
"""

from __future__ import annotations

import pandas as pd

from ict_backtest.costs import COST_BY_SYMBOL, resolve_cost
from ict_backtest.engine import ICTSignal, simulate_trade


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        "time": ["2024-01-01 10:00", "2024-01-01 10:15", "2024-01-01 10:30"],
        "open": [1.1000, 1.1010, 1.1020],
        "high": [1.1020, 1.1030, 1.1040],
        "low": [1.0990, 1.1000, 1.1010],
        "close": [1.1010, 1.1020, 1.1030],
    })


def _sig(entry: float, entry_at: int) -> ICTSignal:
    return ICTSignal(symbol="X", time="2024-01-01 10:00", direction=1,
                     entry=entry, stop_loss=entry - 0.001, take_profit=entry + 0.003,
                     entry_at=entry_at)


def test_resolve_cost_returns_real_table():
    cost = resolve_cost("XAUUSD")
    assert cost is not None
    assert set(cost.keys()) == {"spread_pips", "commission_pips", "slippage_pips"}
    assert cost["spread_pips"] > 0


def test_resolve_cost_no_cost_is_none():
    assert resolve_cost("XAUUSD", no_cost=True) is None


def test_resolve_cost_override_parses():
    cost = resolve_cost("XAUUSD", override="1.0,0.5,0.3")
    assert cost == {"spread_pips": 1.0, "commission_pips": 0.5, "slippage_pips": 0.3}


def test_cost_worsens_pnl_vs_no_cost():
    frame = _frame()
    entry_at = 0
    entry = float(frame.iloc[entry_at + 1]["open"])
    sig = _sig(entry, entry_at)
    sig.take_profit = entry + 0.0015
    sig.stop_loss = entry - 0.0015
    trade_free, _ = simulate_trade(frame, sig, max_hold_bars=2, cost=None)
    trade_cost, _ = simulate_trade(frame, sig, max_hold_bars=2, cost=resolve_cost("XAUUSD"))
    assert trade_free is not None and trade_cost is not None
    assert trade_cost.pnl_r < trade_free.pnl_r, (
        f"costos deben empeorar pnl: con cost={trade_cost.pnl_r} vs sin={trade_free.pnl_r}")


def test_cost_does_not_inflate_pnl_with_small_risk():
    """FIX R6.3: costo en R no explota si risk es pequeño.

    Antes: pnl_r = pnl_price/risk - comm/risk -> con risk~0 el termino
    comm/risk infla pnl_r artificialmente. Ahora el costo se resta en
    precio, y risk<0.3pip descarta el trade.
    """
    frame = _frame()
    sig = _sig(float(frame.iloc[1]["open"]), 0)
    sig.stop_loss = sig.entry - 0.00002  # ~0.2 pip EURUSD
    sig.take_profit = sig.entry + 0.0006
    trade, _ = simulate_trade(frame, sig, max_hold_bars=2, cost=resolve_cost("EURUSD"))
    assert trade is None, f"risk diminuto debe descartarse, no dar pnl {trade.pnl_r if trade else None}"
