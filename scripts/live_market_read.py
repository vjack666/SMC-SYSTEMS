"""First Live Market Reading — SMC SYSTEMS.

Connects to MT5, fetches latest data for all major pairs,
runs feature enrichment and signal pipeline, prints comprehensive summary.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import MetaTrader5 as mt5
from _data_legacy import load_frame
from adapters import FeatureEnrichmentAdapter


def _print_feature_group(name: str, data: dict, indent: str = "    ") -> None:
    impl = data.get("implementation", "active")
    print(f"{indent}{name:<35} {impl}")
    for k, v in data.items():
        if k == "implementation":
            continue
        if isinstance(v, dict):
            flat = "; ".join(f"{sk}={sv}" for sk, sv in v.items())
            print(f"{indent}  {k:<35} {flat}")
        elif not isinstance(v, list):
            print(f"{indent}  {k:<35} = {v}")


def main() -> int:
    print("=" * 72)
    print("  SMC SYSTEMS — First Live Market Reading")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 72)

    # --- 1. Connect to MT5 ---
    print("\n[1] Connecting to MT5...")
    if not mt5.initialize():
        print(f"  FAILED: {mt5.last_error()}")
        return 1

    terminal = mt5.terminal_info()
    account = mt5.account_info()
    print(f"  Terminal : {terminal.name}")
    print(f"  Server   : {terminal.company}")
    print(f"  Account  : {account.login if account else 'demo'}")

    # --- 2. Fetch live rates ---
    print("\n[2] Live Rates (MT5 ticks):")
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD", "USDCHF"]
    rates: dict[str, dict] = {}
    for sym in symbols:
        tick = mt5.symbol_info_tick(sym)
        if tick:
            spread_pips = round((tick.ask - tick.bid) * 10_000, 1)
            print(f"  {sym:<8} bid={tick.bid:.5f}  ask={tick.ask:.5f}  spread={spread_pips:.1f}p")
            rates[sym] = {"bid": tick.bid, "ask": tick.ask, "spread": spread_pips}
        else:
            print(f"  {sym:<8} --- no data ---")

    # --- 3. Run Feature Enrichment ---
    print("\n[3] Feature Enrichment (EURUSD M15):")
    try:
        adapter = FeatureEnrichmentAdapter()
        result = adapter.run([], {"symbol": "EURUSD", "timeframe": "M15", "data_dir": "data/raw"})
        features = result.get("features", {})
        if features:
            print(f"  Total bars analyzed: {result.get('total_bars', 0)}")
            print()
            for group_name in ("liquidity_sweeps", "inducements", "displacement",
                               "premium_discount_arrays", "regime_labels", "interaction_features"):
                group = features.get(group_name)
                if group:
                    _print_feature_group(group_name, group)

            # --- Market Context ---
            liq = features.get("liquidity_sweeps", {})
            ind = features.get("inducements", {})
            reg = features.get("regime_labels", {})
            pda = features.get("premium_discount_arrays", {})
            intf = features.get("interaction_features", {})
            print()
            print("  --- MARKET CONTEXT ---")
            print(f"  Regime     : {reg.get('current_regime', 'N/A')} "
                  f"(dominant: {reg.get('dominant_recent_regime_8_bars', 'N/A')})")
            print(f"  Zone       : {pda.get('current_zone_type', 'N/A')} "
                  f"({pda.get('current_premium_distance', 0):.2f}%)")
            print(f"  Sweep      : {liq.get('sweep_detected', False)} "
                  f"(last: {liq.get('last_sweep_type', 'N/A')})")
            print(f"  Inducement : {ind.get('inducement_detected', False)} "
                  f"(last: {ind.get('last_inducement_type', 'N/A')})")
            print(f"  Displacemnt: bullish={features.get('displacement', {}).get('displacement_bullish', False)} "
                  f"bearish={features.get('displacement', {}).get('displacement_bearish', False)}")
            print(f"  SweepxInd  : co-occur={intf.get('sweep_x_inducement_co_occurrence_count', 0)} "
                  f"({intf.get('sweep_x_inducement_co_occurrence_pct', 0):.2%})")
        else:
            print(f"  WARNING: no features in result. Keys: {list(result.keys())}")
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()

    # --- 4. Run Validation Graph for signals ---
    print("\n[4] Signal Generation (EMA crossover on 50k bars):")
    try:
        from orchestration.backtest_validation_graph import run_validation

        vresult = run_validation(symbol="EURUSD", timeframe="M15", data_dir="data/raw")
        signals = vresult.get("signals", [])
        comparison = vresult.get("comparison", {})

        print(f"  Total signals : {len(signals)}")
        print(f"  Status        : {vresult.get('status', 'N/A')}")
        if signals:
            print()
            print("  Last 5 signals:")
            for s in signals[-5:]:
                print(f"    {s['signal_id']} | {s['action']:5} @ {s['price']:.5f} | "
                      f"SL={s['stop_loss']:.5f} TP={s['take_profit']:.5f}")
        if comparison:
            print()
            print("  Validation Metrics:")
            print(f"    Matched trades  : {comparison.get('matched_trades', 0)}")
            print(f"    Python net P&L  : ${comparison.get('python_total_net', 0):.2f}")
            print(f"    EA net P&L      : ${comparison.get('ea_total_net', 0):.2f}")
            print(f"    Delta net       : ${comparison.get('delta_total_net', 0):+.2f}")
            print(f"    Python win rate : {comparison.get('python_win_rate', 0):.1%}")
            print(f"    EA win rate     : {comparison.get('ea_win_rate', 0):.1%}")
            print(f"    Entry MAE       : {comparison.get('entry_price_mae', 0):.5f}")
            print(f"    Avg slippage    : {comparison.get('avg_slippage_pips', 0):.2f} pips")
    except Exception as e:
        print(f"  ERROR: {e}")

    # --- 5. Summary ---
    print()
    print("=" * 72)
    print("  MARKET READING SUMMARY")
    print("=" * 72)
    print(f"  MT5 Status    : {'CONNECTED' if rates else 'DISCONNECTED'}")
    print(f"  Pairs tracked : {len(rates)}/7")
    print(f"  Account       : {account.login if account else 'N/A'}")
    print(f"  Balance       : ${account.balance:.2f}" if account else "  Balance       : N/A")
    print(f"  Equity        : ${account.equity:.2f}" if account else "  Equity        : N/A")
    print(f"  Features      : {'ACTIVE' if features else 'NONE'} (6 groups)")
    print(f"  Signals       : {len(signals)} generated")
    print(f"  Validation    : {'PASS' if comparison else 'N/A'}")
    print(f"  Pipeline      : EURUSD M15 — Full SMC feature set")
    print()

    # Verdict
    if rates and features and comparison:
        print("  >>> SISTEMA LISTO PARA OPERAR EN MODO LECTURA DE MERCADO <<<")
        print(f"  >>> Regimen actual: {features.get('regime_labels', {}).get('current_regime', 'UNKNOWN')} <<<")
    else:
        print("  >>> SISTEMA EN MODO DEGRADADO — revisar componentes faltantes <<<")

    mt5.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
