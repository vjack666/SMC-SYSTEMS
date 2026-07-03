"""Full pipeline demo: SMC Market Context + Risk Sizing + MT5 Execution.

Usage:
  python scripts/full_pipeline_demo.py

Pipeline:
  1. Feature Enrichment (market regime, premium/discount, sweeps)
  2. Signal generation (EMA crossover)
  3. Risk sizing (Position Sizer formula)
  4. MT5 execution (market order)
  5. Position confirmation + close
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import MetaTrader5 as mt5
from smc_successor.adapters import FeatureEnrichmentAdapter
from smc_successor.risk.sizer import SizingResult, close_position, compute_lot, send_market_order


def get_signal_from_features(features: dict) -> dict | None:
    """Derive a trade signal from feature enrichment output."""
    pda = features.get("premium_discount_arrays", {})
    reg = features.get("regime_labels", {})
    liq = features.get("liquidity_sweeps", {})

    zone = pda.get("current_zone_type", "N/A")
    regime = reg.get("current_regime", "N/A")

    if zone == "DISCOUNT" and regime in ("HIGH_VOL", "NEUTRAL"):
        return {"direction": "BUY", "reason": f"DISCOUNT zone + {regime} regime"}
    elif zone == "PREMIUM" and regime in ("HIGH_VOL", "NEUTRAL"):
        return {"direction": "SELL", "reason": f"PREMIUM zone + {regime} regime"}
    return None


def main() -> int:
    print("=" * 72)
    print("  SMC SYSTEMS - Full Pipeline Demo")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 72)

    # ------------------------------------------------------------------
    # 1. FEATURE ENRICHMENT
    # ------------------------------------------------------------------
    print("\n[1] Feature Enrichment (EURUSD M15)")
    adapter = FeatureEnrichmentAdapter()
    result = adapter.run([], {"symbol": "EURUSD", "timeframe": "M15", "data_dir": "data/raw"})
    features = result.get("features", {})
    if not features:
        print("  ERROR: no features returned")
        return 1

    pda = features.get("premium_discount_arrays", {})
    reg = features.get("regime_labels", {})
    liq = features.get("liquidity_sweeps", {})
    disp = features.get("displacement", {})

    print(f"  Zone       : {pda.get('current_zone_type', 'N/A')} "
          f"(prem_dist={pda.get('current_premium_distance', 0):.2%})")
    print(f"  Regime     : {reg.get('current_regime', 'N/A')} "
          f"(dominant={reg.get('dominant_recent_regime_8_bars', 'N/A')})")
    print(f"  Sweep      : {liq.get('sweep_detected', False)} "
          f"(last={liq.get('last_sweep_type', 'N/A')})")
    print(f"  Displace   : bullish={disp.get('displacement_bullish', False)} "
          f"bearish={disp.get('displacement_bearish', False)}")

    # ------------------------------------------------------------------
    # 2. SIGNAL
    # ------------------------------------------------------------------
    print("\n[2] Signal Generation")
    signal = get_signal_from_features(features)
    print(f"  Direction  : {signal['direction'] if signal else 'NONE'}")
    print(f"  Reason     : {signal['reason'] if signal else 'no signal - market context neutral'}")

    if not signal:
        # Force a BUY signal for demo purposes
        force_dir = "BUY"
        force_reason = "DEMO MODE - forced signal for pipeline test"
        print(f"  [FORCED]   : {force_dir} ({force_reason})")
        signal = {"direction": force_dir, "reason": force_reason}

    # ------------------------------------------------------------------
    # 3. MT5 CONNECT + LIVE PRICE
    # ------------------------------------------------------------------
    print("\n[3] MT5 Connection + Live Price")
    if not mt5.initialize():
        print(f"  FAILED: {mt5.last_error()}")
        return 1

    account = mt5.account_info()
    symbol = "EURUSD"
    tick = mt5.symbol_info_tick(symbol)
    point = mt5.symbol_info(symbol).point
    print(f"  Account    : {account.login} (balance=${account.balance:.2f})")
    print(f"  {symbol}     : bid={tick.bid:.5f} ask={tick.ask:.5f}")

    # ------------------------------------------------------------------
    # 4. RISK SIZING (Position Sizer formula)
    # ------------------------------------------------------------------
    print("\n[4] Risk Sizing (Position Sizer formula)")
    risk_pct = 0.5  # 0.5% risk per trade
    entry = tick.ask if signal["direction"] == "BUY" else tick.bid
    sl_pips = 50
    take_profit_pips = 100

    if signal["direction"] == "BUY":
        sl = round(tick.ask - sl_pips * 10 * point, 5)
        tp = round(tick.ask + take_profit_pips * 10 * point, 5)
    else:
        sl = round(tick.bid + sl_pips * 10 * point, 5)
        tp = round(tick.bid - take_profit_pips * 10 * point, 5)

    sz: SizingResult = compute_lot(
        symbol=symbol,
        entry=entry,
        stop_loss=sl,
        risk_percent=risk_pct,
    )

    print(f"  Risk       : {risk_pct}% = ${sz.risk_money:.2f}")
    print(f"  SL distance: {sl_pips}p ({sz.sl_ticks} ticks)")
    print(f"  Tick value : ${sz.tick_value:.2f}/tick/lot")
    print(f"  Raw lot    : {sz.raw_lot:.4f}")
    print(f"  Final lot  : {sz.lot:.2f}")
    print(f"  SL         : {sl:.5f}")
    print(f"  TP         : {tp:.5f}")

    # ------------------------------------------------------------------
    # 5. EXECUTION
    # ------------------------------------------------------------------
    print(f"\n[5] MT5 Execution ({signal['direction']} {symbol} {sz.lot:.2f} lot)")
    result = send_market_order(
        symbol=symbol,
        action=signal["direction"],
        volume=sz.lot,
        stop_loss=sl,
        take_profit=tp,
        comment=f"SMC_PIPELINE_{datetime.now(timezone.utc).strftime('%H%M%S')}",
    )

    retcode = result.get("retcode", -1)
    print(f"  Retcode    : {retcode} ({result.get('comment', 'N/A')})")
    print(f"  Ticket     : {result.get('ticket', 0)}")
    print(f"  Fill price : {result.get('price', 0):.5f}")
    print(f"  Fill volume: {result.get('volume', 0):.2f}")

    if retcode != 10009:
        print(f"  >>> ORDER FAILED - aborting pipeline test <<<")
        mt5.shutdown()
        return 1

    # ------------------------------------------------------------------
    # 6. CONFIRM POSITION
    # ------------------------------------------------------------------
    time.sleep(1)
    print(f"\n[6] Position Confirmation")
    positions = mt5.positions_get()
    our_positions = [p for p in (positions or []) if p.comment and "SMC_PIPELINE" in p.comment]
    if our_positions:
        for p in our_positions:
            side = "BUY" if p.type == 0 else "SELL"
            print(f"  TICKET {p.ticket}: {p.symbol} {side} {p.volume:.2f} "
                  f"@{p.price_open:.5f} profit=${p.profit:.2f}")
    else:
        print("  WARNING: position not found in MT5 (may have been rejected after order)")

    # ------------------------------------------------------------------
    # 7. CLOSE POSITION
    # ------------------------------------------------------------------
    print(f"\n[7] Closing Position(s)")
    if our_positions:
        for p in our_positions:
            close_result = close_position(p.ticket, p.symbol, p.volume, p.type)
            print(f"  Ticket {p.ticket}: retcode={close_result['retcode']} "
                  f"({close_result['comment']})")
    else:
        print("  Nothing to close")

    # ------------------------------------------------------------------
    # FINAL VERIFICATION
    # ------------------------------------------------------------------
    time.sleep(0.5)
    remaining = mt5.positions_get()
    our_remaining = [p for p in (remaining or []) if p.comment and "SMC_PIPELINE" in p.comment]
    print(f"\n  Remaining positions: {len(our_remaining)}")

    mt5.shutdown()

    verdict = "PASSED" if retcode == 10009 and len(our_remaining) == 0 else "FAILED"
    print(f"\n{'=' * 72}")
    print(f"  FULL PIPELINE DEMO {verdict}")
    print(f"{'=' * 72}")
    return 0 if verdict == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
