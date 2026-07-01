from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd

from backtest.combined_backtest import CombinedBacktestConfig, run_combined_backtest
from strategy.scalping_setup import ScalpingConfig

# Limit date window to last ~3 months for speed
START = "2026-03-01"
END = "2026-06-01"
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

def run(label: str, use_wyckoff: bool) -> dict[str, Any]:
    scalping = ScalpingConfig(
        use_wyckoff=use_wyckoff,
        use_stochastic_exhaustion=True,
        use_pac=True,
        use_structural_sl=True,
    )
    cfg = CombinedBacktestConfig(
        symbols=("EURUSD", "GBPUSD", "XAUUSD"),
        scalping_config=scalping,
        use_ml_quality_filter=False,
        start_time=START,
        end_time=END,
    )
    t0 = time.time()
    print(f"[{label}] Running backtest {START} -> {END} ...", flush=True)
    metrics, trades_df = run_combined_backtest(cfg)
    elapsed = time.time() - t0
    ntrades = int(metrics.get("total_trades", 0))
    pf = float(metrics.get("profit_factor", 0.0))
    print(f"[{label}] {elapsed:.0f}s | trades={ntrades} | PF={pf:.4f}", flush=True)
    report = {
        "label": label, "use_wyckoff": use_wyckoff,
        "total_trades": ntrades,
        "win_rate": float(metrics.get("win_rate", 0.0)),
        "profit_factor": pf,
        "max_drawdown_r": float(metrics.get("max_drawdown_r", 0.0)),
        "max_drawdown_pct": float(metrics.get("max_drawdown_pct", 0.0)),
        "max_daily_drawdown_pct": float(metrics.get("max_daily_drawdown_pct", 0.0)),
        "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0)),
        "expectancy_r": float(metrics.get("expectancy_r", 0.0)),
    }
    (RESULTS_DIR / f"bt_{label}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if trades_df is not None and len(trades_df) > 0:
        trades_df.to_csv(RESULTS_DIR / f"trades_{label}.csv", index=False)
    return report

def print_comparison(a: dict, b: dict) -> None:
    keys = [
        ("total_trades", "Total Trades", "int"),
        ("win_rate", "Win Rate", ".4f"),
        ("profit_factor", "Profit Factor", ".4f"),
        ("max_drawdown_pct", "Max DD%", ".4f"),
        ("max_daily_drawdown_pct", "Max Daily DD%", ".4f"),
        ("sharpe_ratio", "Sharpe Ratio", ".4f"),
        ("expectancy_r", "Expectancy (R)", ".4f"),
    ]
    header = f"{'Metric':<20} | {'Wyckoff ON':>14} | {'Wyckoff OFF':>14} | {'Delta':>14}"
    print(header)
    print("-" * len(header))
    for key, label, fmt in keys:
        av = a.get(key, 0.0)
        bv = b.get(key, 0.0)
        if fmt == "int":
            print(f"{label:<20} | {int(av):>14d} | {int(bv):>14d} | {int(av-bv):>+14d}")
        else:
            print(f"{label:<20} | {av:>14.4f} | {bv:>14.4f} | {av-bv:>+14.4f}")

if __name__ == "__main__":
    print("=" * 70)
    print("WYCKOFF BACKTEST COMPARISON (Mar-May 2026)")
    print("=" * 70)
    r1 = run("A_wyckoff_on", use_wyckoff=True)
    print()
    r2 = run("B_wyckoff_off", use_wyckoff=False)
    print()
    print("=" * 70)
    print("COMPARISON")
    print("=" * 70)
    print_comparison(r1, r2)
    delta = r1["profit_factor"] - r2["profit_factor"]
    print()
    print(f"PF delta: {delta:+.4f}")
    print(f"Recommendation: {'ENABLE Wyckoff' if delta >= 0 else 'DISABLE Wyckoff'}")
    combined = {"A_wyckoff_on": r1, "B_wyckoff_off": r2, "pf_delta": delta}
    (RESULTS_DIR / "bt_wyckoff_comparison.json").write_text(json.dumps(combined, indent=2), encoding="utf-8")
