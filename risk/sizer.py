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
    filling = _filling_mode(symbol)
    if filling is not None:
        request["type_filling"] = filling

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


def _filling_mode(symbol: str) -> int | None:
    info = mt5.symbol_info(symbol)
    if info is None:
        return None
    # Prefer IOC then FOK then RETURN depending on symbol flags.
    filling = info.filling_mode
    if filling & 1:  # FOK
        return mt5.ORDER_FILLING_FOK
    if filling & 2:  # IOC
        return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN


def send_limit_order(
    symbol: str,
    side: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
    volume: float | None = None,
    risk_percent: float = 1.0,
    comment: str = "SMC_LIMIT",
    magic: int = 20260716,
) -> dict:
    """Place a pending LIMIT order with SL/TP (demo-friendly).

    LONG  -> BUY_LIMIT  (entry should be below market)
    SHORT -> SELL_LIMIT (entry should be above market)
    If price is on the wrong side of market, falls back to STOP order type
    so the pending order is still accepted by the broker.
    """
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"symbol_select failed for {symbol}: {mt5.last_error()}")

    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if info is None or tick is None:
        raise RuntimeError(f"No symbol/tick for {symbol}")

    digits = int(info.digits)
    entry = round(float(entry), digits)
    stop_loss = round(float(stop_loss), digits)
    take_profit = round(float(take_profit), digits)

    is_long = side.upper() in ("BUY", "LONG")
    bid, ask = float(tick.bid), float(tick.ask)

    if is_long:
        # BUY LIMIT below market; BUY STOP above market
        if entry < ask:
            order_type = mt5.ORDER_TYPE_BUY_LIMIT
        else:
            order_type = mt5.ORDER_TYPE_BUY_STOP
    else:
        # SELL LIMIT above market; SELL STOP below market
        if entry > bid:
            order_type = mt5.ORDER_TYPE_SELL_LIMIT
        else:
            order_type = mt5.ORDER_TYPE_SELL_STOP

    if volume is None:
        sizing = compute_lot(symbol, entry, stop_loss, risk_percent=risk_percent)
        volume = sizing.lot
    volume = float(volume)
    if volume <= 0:
        raise ValueError("Computed volume is 0 — risk too small or SL too wide")

    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": entry,
        "sl": stop_loss,
        "tp": take_profit,
        "deviation": 20,
        "magic": magic,
        "comment": comment[:31],
        "type_time": mt5.ORDER_TIME_GTC,
    }
    filling = _filling_mode(symbol)
    if filling is not None:
        request["type_filling"] = filling

    result = mt5.order_send(request)
    if result is None:
        return {
            "ok": False,
            "retcode": -1,
            "comment": f"order_send None: {mt5.last_error()}",
            "ticket": 0,
            "volume": volume,
            "order_type": int(order_type),
            "price": entry,
        }

    ok = result.retcode == mt5.TRADE_RETCODE_DONE
    return {
        "ok": ok,
        "retcode": result.retcode,
        "comment": result.comment,
        "ticket": result.order,
        "volume": volume,
        "order_type": int(order_type),
        "price": entry,
        "sl": stop_loss,
        "tp": take_profit,
        "side": "LONG" if is_long else "SHORT",
        "request": request,
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
