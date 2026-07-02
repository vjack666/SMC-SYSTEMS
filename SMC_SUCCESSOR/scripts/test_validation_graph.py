"""Test script for the F7 Backtest Validation LangGraph.

Usage:
    python scripts/test_validation_graph.py
    python scripts/test_validation_graph.py --symbol GBPUSD --timeframe H1
"""

from __future__ import annotations

import argparse
import sys
from pprint import pprint


def main() -> int:
    parser = argparse.ArgumentParser(description="Run F7 LangGraph validation pipeline")
    parser.add_argument("--symbol", default="EURUSD", help="Trading symbol")
    parser.add_argument("--timeframe", default="M15", help="Timeframe (e.g. M15, H1, H4)")
    parser.add_argument("--data-dir", default="data/raw", help="Data directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print full report")
    args = parser.parse_args()

    sys.path.insert(0, ".")

    from smc_successor.orchestration.backtest_validation_graph import run_validation

    print(f"\n{'='*70}")
    print(f"  F7 LangGraph Validation Pipeline")
    print(f"  {args.symbol} {args.timeframe} | data_dir={args.data_dir}")
    print(f"{'='*70}\n")

    result = run_validation(
        symbol=args.symbol,
        timeframe=args.timeframe,
        data_dir=args.data_dir,
    )

    status = result.get("status", "unknown")
    signals = result.get("signals", [])
    ea_results = result.get("ea_results", [])
    comparison = result.get("comparison")
    errors = result.get("errors", [])
    total_bars = result.get("total_bars", 0)

    print(f"  Status          : {status}")
    print(f"  Total bars      : {total_bars}")
    print(f"  Signals         : {len(signals)}")
    print(f"  EA results      : {len(ea_results)}")
    print(f"  Matched trades  : {comparison.get('matched_trades', 0) if comparison else 0}")
    print(f"  Errors          : {len(errors)}")
    if errors:
        for e in errors:
            print(f"    - {e}")

    if comparison:
        print()
        print(f"  {'Metric':<30} {'Python':>10} {'EA':>10} {'Delta':>10}")
        print(f"  {'-'*30} {'-'*10} {'-'*10} {'-'*10}")
        print(f"  {'Win rate':<30} {comparison['python_win_rate']:>10.2%} {comparison['ea_win_rate']:>10.2%} {comparison['delta_win_rate']:>+10.2%}")
        print(f"  {'Profit factor':<30} {comparison['python_profit_factor']:>10.4f} {comparison['ea_profit_factor']:>10.4f} {comparison['delta_profit_factor']:>+10.4f}")
        print(f"  {'Total net ($)':<30} {comparison['python_total_net']:>10.2f} {comparison['ea_total_net']:>10.2f} {comparison['delta_total_net']:>+10.2f}")
        print(f"  {'Total pips':<30} {comparison['python_total_pips']:>10.1f} {comparison['ea_total_pips']:>10.1f} {comparison['delta_total_pips']:>+10.1f}")
        print(f"  {'Entry MAE':<30} {comparison['entry_price_mae']:>10.5f}")
        print(f"  {'Entry max diff':<30} {comparison['entry_price_max_diff']:>10.5f}")
        print(f"  {'Avg slippage (pips)':<30} {comparison['avg_slippage_pips']:>10.2f}")
        print(f"  {'Slippage cost ($)':<30} {comparison['slippage_cost_total']:>10.2f}")
        print(f"  {'Max drawdown ($)':<30} {comparison['python_max_drawdown']:>10.2f} {comparison['ea_max_drawdown']:>10.2f}")
        print(f"  {'Sharpe':<30} {comparison['python_sharpe']:>10.4f} {comparison['ea_sharpe']:>10.4f}")

    if args.verbose or status == "failed":
        print()
        print("--- FULL REPORT ---")
        report_text = result.get("report", "(no report)")
        try:
            print(report_text)
        except UnicodeEncodeError:
            print(report_text.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
    else:
        print()
        report = result.get("report", "")
        if report:
            print("--- REPORT PREVIEW ---")
            for line in report.split("\n")[:8]:
                print(line)
            print("  ...")
            print(f"  ({len(report)} chars total)")

    print(f"\n{'='*70}")
    if status == "report_generated" and not errors:
        print("  [OK] Validation pipeline completed successfully.")
        return 0
    else:
        print(f"  [FAIL] Pipeline finished with status={status} and {len(errors)} error(s).")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
