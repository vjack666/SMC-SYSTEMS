"""First live trade test: Python -> MT5 (direct, no EA).

Usage:
  python scripts/first_live_test.py

Sends one BUY market order on EURUSD, lote 0.01, SL=50p, TP=100p.
Prints order result + open positions.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

import MetaTrader5 as mt5


def main() -> int:
    print("=" * 72)
    print("  SMC SYSTEMS - First Live Trade Test (Python -> MT5)")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 72)

    # --- 1. Connect ---
    print("\n[1] Connecting to MT5 ...")
    if not mt5.initialize():
        print(f"  FAILED: {mt5.last_error()}")
        return 1

    account = mt5.account_info()
    terminal = mt5.terminal_info()
    print(f"  Account  : {account.login} (balance=${account.balance:.2f})")
    print(f"  Terminal : {terminal.name}")

    # --- 2. Check trade permissions ---
    print("\n[2] Checking trade context ...")
    if not terminal.trade_allowed:
        print("  WARNING: trade_not_allowed — enable Algo Trading in MT5")

    # --- 3. Prepare signal ---
    symbol = "EURUSD"
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print(f"\n[3] ERROR: cannot get tick for {symbol}")
        mt5.shutdown()
        return 1

    point = mt5.symbol_info(symbol).point
    volume = 0.01
    sl = round(tick.bid - 500 * point, 5)     # 50 pips below bid
    tp = round(tick.bid + 1000 * point, 5)     # 100 pips above bid

    print(f"\n[3] Signal:")
    print(f"  Symbol : {symbol}")
    print(f"  Action : BUY (market)")
    print(f"  Volume : {volume}")
    print(f"  Ask    : {tick.ask:.5f}")
    print(f"  SL     : {sl:.5f}  ({(tick.ask - sl) / point:.0f}p)")
    print(f"  TP     : {tp:.5f}  ({(tp - tick.ask) / point:.0f}p)")

    # --- 4. Send order ---
    print(f"\n[4] Sending order ...")
    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       symbol,
        "volume":       volume,
        "type":         mt5.ORDER_TYPE_BUY,
        "price":        tick.ask,
        "sl":           sl,
        "tp":           tp,
        "deviation":    10,
        "magic":        20260701,
        "comment":      f"SMC_TEST_{uuid4().hex[:6].upper()}",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    result = mt5.order_send(request)
    if result is None:
        print(f"  ERROR: order_send returned None (last_error={mt5.last_error()})")
        mt5.shutdown()
        return 1

    print(f"  Retcode  : {result.retcode}  ({result.comment})")
    print(f"  Ticket   : {result.order}")
    print(f"  Volume   : {result.volume}")
    print(f"  Price    : {result.price}")
    print(f"  Comment  : {result.comment}")

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"\n  >>> ORDER REJECTED (code {result.retcode}) <<<")
        print(f"  Check MT5 Journal tab for details")

    # --- 5. Show open positions ---
    time.sleep(1)
    print(f"\n[5] MT5 Open Positions:")
    positions = mt5.positions_get()
    if positions:
        for pos in positions:
            side = "BUY" if pos.type == 0 else "SELL"
            print(f"  {pos.symbol} {side} vol={pos.volume:.2f} "
                  f"open={pos.price_open:.5f} sl={pos.sl:.5f} tp={pos.tp:.5f} "
                  f"profit=${pos.profit:.2f}")
    else:
        print("  No open positions")

    mt5.shutdown()
    verdict = "PASSED" if result.retcode == mt5.TRADE_RETCODE_DONE else "FAILED"
    print(f"\n{'=' * 72}")
    print(f"  TEST {verdict}")
    print(f"{'=' * 72}")
    return 0 if result.retcode == mt5.TRADE_RETCODE_DONE else 1


if __name__ == "__main__":
    raise SystemExit(main())
