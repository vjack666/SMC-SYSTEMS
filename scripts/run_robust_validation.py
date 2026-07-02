"""
FASE 13 — Robust Validation and Risk Metrics
Purged KFold, embargo, bootstrap validation, CVaR, Drawdown duration, rolling metrics.

Usage:
    python scripts/run_robust_validation.py
    python scripts/run_robust_validation.py --trades results/combined_trades.csv
    python scripts/run_robust_validation.py --symbol XAUUSD
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml.robust_validation import (
    compute_all_risk_metrics,
    generate_validation_report,
)

RESULTS_DIR = Path("results")
ROBUST_DIR = RESULTS_DIR / "robust_validation"
TRADES_PATH = RESULTS_DIR / "combined_trades.csv"


def _load_trades(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"[ERROR] Trade file not found: {path}")
        sys.exit(1)
    df = pd.read_csv(path)
    if "pnl_r" not in df.columns:
        print(f"[ERROR] Missing 'pnl_r' column in {path}")
        print(f"  Columns found: {list(df.columns)}")
        sys.exit(1)
    print(f"  Loaded {len(df)} trades from {path}")
    return df


def run_per_symbol_report(trades: pd.DataFrame) -> dict[str, Any]:
    """Run validation per symbol and aggregated."""
    ROBUST_DIR.mkdir(parents=True, exist_ok=True)

    all_results: dict[str, Any] = {
        "timestamp_utc": datetime.now(tz=timezone.utc).isoformat(),
        "total_trades_all": len(trades),
    }

    symbols = sorted(trades["symbol"].unique()) if "symbol" in trades.columns else ["ALL"]
    print(f"\nSymbols found: {symbols}")

    # Per-symbol validation
    per_symbol_results: dict[str, Any] = {}
    for sym in symbols:
        print(f"\n{'='*60}")
        print(f"Processing {sym}...")
        print("="*60)
        if sym == "ALL":
            sym_trades = trades
        else:
            sym_trades = trades[trades["symbol"] == sym].copy()
        if len(sym_trades) < 3:
            print(f"  Skipping {sym}: only {len(sym_trades)} trades")
            continue
        result = generate_validation_report(
            sym_trades,
            output_dir=ROBUST_DIR,
            symbol=sym,
        )
        per_symbol_results[sym] = {
            "total_trades": result.get("total_trades", 0),
            "metrics": result.get("metrics", {}),
            "pbo": result.get("pbo", {}),
            "deflated_sharpe": result.get("deflated_sharpe", {}),
        }

    all_results["per_symbol"] = per_symbol_results

    # Aggregated metrics
    all_results["aggregated"] = compute_all_risk_metrics(trades)

    # Save master JSON
    master_path = ROBUST_DIR / "validation_results_master.json"
    master_path.write_text(json.dumps(all_results, indent=2, default=str), encoding="utf-8")
    print(f"\nMaster results saved to {master_path}")

    return all_results


def run_quick_summary(trades: pd.DataFrame) -> dict[str, Any]:
    """Quick summary of all risk metrics without full reports."""
    metrics = compute_all_risk_metrics(trades)
    print(f"\n{'='*60}")
    print("QUICK RISK METRICS SUMMARY")
    print("="*60)
    key_fields = [
        "total_trades", "win_rate", "profit_factor", "expectancy_r",
        "sharpe_ratio", "sortino_ratio", "omega_ratio", "gain_to_pain_ratio",
        "max_drawdown_r", "max_drawdown_pct", "var_95", "cvar_95",
        "ulcer_index", "recovery_factor", "risk_of_ruin", "k_ratio",
        "dd_avg_duration_bars", "dd_max_duration_bars", "dd_median_duration_bars",
        "rolling_sharpe_5pct", "rolling_sharpe_95pct",
        "rolling_pf_5pct", "rolling_pf_95pct",
    ]
    for key in key_fields:
        val = metrics.get(key)
        if val is not None:
            print(f"  {key:35s} = {val}")
        else:
            print(f"  {key:35s} = N/A")

    print(f"\n  Bootstrap ready via: python scripts/run_robust_validation.py --full")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="FASE 13 — Robust Validation and Risk Metrics")
    parser.add_argument("--trades", type=str, default=str(TRADES_PATH),
                        help=f"Path to trades CSV (default: {TRADES_PATH})")
    parser.add_argument("--symbol", type=str, default=None,
                        help="Filter by symbol (e.g., EURUSD)")
    parser.add_argument("--full", action="store_true",
                        help="Run per-symbol full reports including bootstrap + Purged CV")
    args = parser.parse_args()

    print("="*60)
    print("FASE 13 — Robust Validation & Risk Metrics")
    print("="*60)

    trades = _load_trades(Path(args.trades))

    if args.symbol:
        if "symbol" not in trades.columns:
            print(f"[ERROR] No 'symbol' column in trades. Cannot filter.")
            sys.exit(1)
        trades = trades[trades["symbol"] == args.symbol].copy()
        print(f"  Filtered to symbol={args.symbol}: {len(trades)} trades")

    if args.full or len(trades) >= 50:
        run_per_symbol_report(trades)
    else:
        run_quick_summary(trades)

    print(f"\n{'='*60}")
    print("Done. Reports in results/robust_validation/")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
