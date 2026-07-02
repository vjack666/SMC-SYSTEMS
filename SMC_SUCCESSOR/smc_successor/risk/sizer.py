"""Position Sizer — risk-based lot sizing (ported from Position Sizer.ex5)."""

from __future__ import annotations

from dataclasses import dataclass
from math import floor

import MetaTrader5 as mt5


@dataclass
class SizingResult:
    lot: float
    risk_percent: float
    risk_money: float
    sl_ticks: int
    tick_value: float
    commission: float
    raw_lot: float


def compute_lot(
    symbol: str,
    entry: float,
    stop_loss: float,
    risk_percent: float = 1.0,
    risk_money: float | None = None,
    commission_per_lot: float = 0.0,
) -> SizingResult:
    """Compute lot size using Position Sizer formula.

    Lot = RiskMoney / (SL_ticks * TickValue + 2 * commission_per_lot)
    """
    info = mt5.symbol_info(symbol)
    account = mt5.account_info()
    if info is None or account is None:
        raise RuntimeError(f"Cannot get symbol/account info for {symbol}")

    tick_size: float = info.trade_tick_size
    tick_value: float = info.trade_tick_value_loss
    balance: float = account.balance
    volume_step: float = info.volume_step
    volume_min: float = info.volume_min
    volume_max: float = info.volume_max

    sl_distance = abs(entry - stop_loss)
    if sl_distance < tick_size:
        raise ValueError(f"SL distance ({sl_distance}) < tick size ({tick_size})")

    sl_ticks = int(round(sl_distance / tick_size))

    if risk_money is not None:
        risk = risk_money
        used_risk_pct = risk / balance * 100 if balance > 0 else 0.0
    else:
        risk = balance * risk_percent / 100.0
        used_risk_pct = risk_percent

    cost_per_lot = sl_ticks * tick_value + 2.0 * commission_per_lot
    if cost_per_lot <= 0:
        raise ValueError(f"Cost per lot is <= 0 ({cost_per_lot})")

    raw_lot = risk / cost_per_lot

    steps = raw_lot / volume_step
    floored = floor(steps)
    lot = floored * volume_step if floored * volume_step >= volume_min else volume_min
    lot = min(lot, volume_max)

    return SizingResult(
        lot=lot,
        risk_percent=used_risk_pct,
        risk_money=risk,
        sl_ticks=sl_ticks,
        tick_value=tick_value,
        commission=commission_per_lot,
        raw_lot=raw_lot,
    )


def send_market_order(
    symbol: str,
    action: str,
    volume: float,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    comment: str = "SMC_SYSTEMS",
    magic: int = 20260701,
    deviation: int = 10,
) -> dict:
    """Send a market order to MT5 and return the result dict."""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"Cannot get tick for {symbol}")

    is_buy = action.upper() in ("BUY", "LONG")

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
        "price": tick.ask if is_buy else tick.bid,
        "sl": stop_loss,
        "tp": take_profit,
        "deviation": deviation,
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
    }

    result = mt5.order_send(request)
    if result is None:
        return {"retcode": -1, "comment": f"order_send returned None: {mt5.last_error()}", "ticket": 0}

    return {
        "retcode": result.retcode,
        "comment": result.comment,
        "ticket": result.order,
        "volume": result.volume,
        "price": result.price,
    }


def close_position(ticket: int, symbol: str, volume: float, position_type: int, magic: int = 20260701) -> dict:
    """Close an open position."""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"retcode": -1, "comment": f"Cannot get tick for {symbol}"}

    is_buy = position_type == 0
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
        "position": ticket,
        "price": tick.bid if is_buy else tick.ask,
        "deviation": 10,
        "magic": magic,
        "comment": "CLOSE",
        "type_time": mt5.ORDER_TIME_GTC,
    }

    result = mt5.order_send(request)
    if result is None:
        return {"retcode": -1, "comment": f"close failed: {mt5.last_error()}", "ticket": 0}
    return {"retcode": result.retcode, "comment": result.comment, "ticket": result.order}
