from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from backtest.combined_backtest import (
    CombinedBacktestConfig,
    run_combined_backtest,
)
from strategy.scalping_setup import ScalpingConfig


def _run(
    label: str,
    use_wyckoff: bool,
    results_dir: Path,
) -> dict[str, Any]:
    scalping = ScalpingConfig(
        use_wyckoff=use_wyckoff,
        use_stochastic_exhaustion=True,
        use_pac=True,
        use_structural_sl=True,
    )
    cfg = CombinedBacktestConfig(
        scalping_config=scalping,
        use_ml_quality_filter=False,
    )
    t0 = time.time()
    print(f"[{label}] Starting backtest...")
    metrics, trades_df = run_combined_backtest(cfg)
    elapsed = time.time() - t0
    print(f"[{label}] Done in {elapsed:.1f}s | trades={metrics.get('total_trades', 0)} | PF={metrics.get('profit_factor', 0.0):.4f}")

    report = {
        "config": {"use_wyckoff": use_wyckoff, "label": label},
        "metrics": metrics,
        "total_trades": int(metrics.get("total_trades", 0)),
        "win_rate": float(metrics.get("win_rate", 0.0)),
        "profit_factor": float(metrics.get("profit_factor", 0.0)),
        "max_drawdown_r": float(metrics.get("max_drawdown_r", 0.0)),
        "max_drawdown_pct": float(metrics.get("max_drawdown_pct", 0.0)),
        "max_daily_drawdown_pct": float(metrics.get("max_daily_drawdown_pct", 0.0)),
        "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0)),
        "expectancy_r": float(metrics.get("expectancy_r", 0.0)),
    }

    fname = f"bt_{label}.json"
    (results_dir / fname).write_text(json.dumps(report, indent=2), encoding="utf-8")

    if trades_df is not None and len(trades_df) > 0:
        trades_path = results_dir / f"trades_{label}.csv"
        trades_df.to_csv(trades_path, index=False)
        print(f"[{label}] {len(trades_df)} trades saved to {trades_path}")

    return report


def main() -> None:
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  WYCKOFF BACKTEST COMPARISON")
    print("=" * 60)
    print()

    report_a = _run("A_wyckoff_on", use_wyckoff=True, results_dir=results_dir)
    print()
    report_b = _run("B_wyckoff_off", use_wyckoff=False, results_dir=results_dir)

    print()
    print("=" * 60)
    print("  COMPARISON SUMMARY")
    print("=" * 60)
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
    sep = "-" * len(header)
    print(header)
    print(sep)
    for key, label, fmt in keys:
        a_val = report_a.get(key, 0.0)
        b_val = report_b.get(key, 0.0)
        # Fix types
        if fmt == "int":
            a_s = f"{int(a_val):>14d}"
            b_s = f"{int(b_val):>14d}"
            delta_s = f"{int(a_val - b_val):>+14d}"
        else:
            a_s = f"{a_val:>14.4f}"
            b_s = f"{b_val:>14.4f}"
            delta_s = f"{a_val - b_val:>+14.4f}"
        print(f"{label:<20} | {a_s} | {b_s} | {delta_s}")

    improvement = report_a["profit_factor"] - report_b["profit_factor"]
    print()
    print(f"PF improvement with Wyckoff: {improvement:+.4f}")
    print(f"Decision: {'ENABLE Wyckoff' if improvement >= 0 else 'DISABLE Wyckoff'}")
    print()

    combined = {
        "A_wyckoff_on": report_a,
        "B_wyckoff_off": report_b,
        "comparison": {
            "pf_delta": improvement,
            "recommendation": "ENABLE" if improvement >= 0 else "DISABLE",
        },
    }
    (results_dir / "bt_wyckoff_comparison.json").write_text(json.dumps(combined, indent=2), encoding="utf-8")
    print(f"Full comparison saved to {results_dir / 'bt_wyckoff_comparison.json'}")

    # Print key findings for documentation
    print()
    print("-- KEY FINDINGS --")
    print(f"Wyckoff ON:  PF={report_a['profit_factor']:.4f}, WR={report_a['win_rate']:.4f}, Sharpe={report_a['sharpe_ratio']:.4f}, Trades={report_a['total_trades']}")
    print(f"Wyckoff OFF: PF={report_b['profit_factor']:.4f}, WR={report_b['win_rate']:.4f}, Sharpe={report_b['sharpe_ratio']:.4f}, Trades={report_b['total_trades']}")
    if report_a["total_trades"] == 0 and report_b["total_trades"] > 0:
        print("WARNING: Wyckoff filter may be too restrictive - 0 trades generated")
    if report_a["total_trades"] == 0 and report_b["total_trades"] == 0:
        print("WARNING: No trades generated in either configuration - check data/config")


if __name__ == "__main__":
    main()
