"""
Validate structural stop loss fix by comparing metrics and checking for invalid stops.
"""

from pathlib import Path
import pandas as pd
import numpy as np
import json


def validate_stops(df: pd.DataFrame) -> tuple[int, int, list[dict]]:
    """Check for invalid stop positions."""
    df = df.copy()
    df["direction"] = df["direction"].astype(int)
    df["entry_price"] = pd.to_numeric(df["entry_price"], errors="coerce")
    df["sl_price"] = pd.to_numeric(df["sl_price"], errors="coerce")
    
    long_invalid = len(df[(df["direction"] == 1) & (df["sl_price"] >= df["entry_price"])])
    short_invalid = len(df[(df["direction"] == -1) & (df["sl_price"] <= df["entry_price"])])
    
    invalid_rows = df[
        ((df["direction"] == 1) & (df["sl_price"] >= df["entry_price"])) |
        ((df["direction"] == -1) & (df["sl_price"] <= df["entry_price"]))
    ]
    
    return long_invalid, short_invalid, invalid_rows.to_dict("records")


def validate_exit_logic(df: pd.DataFrame) -> int:
    """Check for exit logic violations."""
    df = df.copy()
    df["pnl_r"] = pd.to_numeric(df["pnl_r"], errors="coerce")
    df["exit_reason"] = df["exit_reason"].astype(str)
    
    violations = len(df[
        ((df["exit_reason"] == "sl_hit") & (df["pnl_r"] > 0)) |
        ((df["exit_reason"] == "tp_hit") & (df["pnl_r"] < 0))
    ])
    
    return violations


def load_metrics(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def generate_validation_report():
    results_dir = Path("results")
    
    # Load datasets
    broken = pd.read_csv(results_dir / "experiment_F_structural_sl.csv")
    fixed = pd.read_csv(results_dir / "experiment_F_structural_sl_fixed.csv")
    
    # Validate fixed version
    long_inv, short_inv, invalid_rows = validate_stops(fixed)
    exit_violations = validate_exit_logic(fixed)
    
    # Check ATR nulls
    atr_nulls = fixed["stop_distance_atr"].isna().sum()
    
    # Check holding bars distribution
    holding_bars_unique = sorted(fixed["holding_bars"].unique())
    
    # Total trades
    total_trades = len(fixed)
    
    lines = [
        "# Structural Stop Loss Fix Validation",
        "",
        "## Fix Status",
        "",
        f"- **Invalid LONG stops**: {long_inv} (target: 0)",
        f"- **Invalid SHORT stops**: {short_inv} (target: 0)",
        f"- **Invalid exit logic violations**: {exit_violations} (target: 0)",
        f"- **stop_distance_atr NaN count**: {atr_nulls} (target: 0)",
        f"- **Total trades**: {total_trades}",
        f"- **Holding bars unique values**: {holding_bars_unique}",
        "",
        "## Validation Criteria",
        "",
    ]
    
    passed = (long_inv == 0 and short_inv == 0 and exit_violations == 0)
    status = "✅ PASSED" if passed else "❌ FAILED"
    lines.append(f"**Overall Status**: {status}")
    lines.append("")
    
    if long_inv == 0:
        lines.append("- ✅ LONG stops are all below entry_price")
    else:
        lines.append(f"- ❌ {long_inv} LONG stops are above or equal to entry_price")
    
    if short_inv == 0:
        lines.append("- ✅ SHORT stops are all above entry_price")
    else:
        lines.append(f"- ❌ {short_inv} SHORT stops are below or equal to entry_price")
    
    if exit_violations == 0:
        lines.append("- ✅ Exit logic is consistent (no sl_hit with pnl_r > 0, no tp_hit with pnl_r < 0)")
    else:
        lines.append(f"- ❌ {exit_violations} exit logic violations found")
    
    if atr_nulls == 0:
        lines.append("- ✅ stop_distance_atr has valid values")
    else:
        lines.append(f"- ❌ {atr_nulls} NaN values in stop_distance_atr")
    
    if len(holding_bars_unique) > 1:
        lines.append(f"- ✅ Holding bars varies: {holding_bars_unique[:10]}...")
    else:
        lines.append(f"- ❌ Holding bars is constant: {holding_bars_unique}")
    
    lines.append("")
    lines.append("## Comparison: Broken vs Fixed")
    lines.append("")
    lines.append("| Metric | Broken | Fixed | Improvement |")
    lines.append("|--------|--------|-------|-------------|")
    
    broken_long_inv, broken_short_inv, _ = validate_stops(broken)
    broken_exit_vio = validate_exit_logic(broken)
    broken_atr_null = broken["stop_distance_atr"].isna().sum()
    
    lines.append(f"| Invalid LONG stops | {broken_long_inv} | {long_inv} | {broken_long_inv - long_inv} ✅ |")
    lines.append(f"| Invalid SHORT stops | {broken_short_inv} | {short_inv} | {broken_short_inv - short_inv} ✅ |")
    lines.append(f"| Exit logic violations | {broken_exit_vio} | {exit_violations} | {broken_exit_vio - exit_violations} ✅ |")
    lines.append(f"| stop_distance_atr NaN | {broken_atr_null} | {atr_nulls} | {broken_atr_null - atr_nulls} ✅ |")
    lines.append(f"| Total trades | {len(broken)} | {total_trades} | - |")
    
    lines.append("")
    lines.append("## Trade Statistics (Fixed)")
    lines.append("")
    fixed_metrics = load_metrics(results_dir / "experiment_F_structural_sl_fixed_metrics.json")
    if fixed_metrics:
        for key, val in fixed_metrics.items():
            lines.append(f"- **{key}**: {val}")
    
    report = "\n".join(lines)
    (results_dir / "structural_sl_fix_validation.md").write_text(report, encoding="utf-8")
    print(f"Wrote results/structural_sl_fix_validation.md")
    
    # Print summary
    print("\n=== VALIDATION SUMMARY ===")
    print(f"Invalid LONG stops: {long_inv}")
    print(f"Invalid SHORT stops: {short_inv}")
    print(f"Exit logic violations: {exit_violations}")
    print(f"stop_distance_atr NaN: {atr_nulls}")
    print(f"Total trades: {total_trades}")
    print(f"Holding bars unique: {len(holding_bars_unique)}")
    print(f"Status: {'✅ PASSED' if passed else '❌ FAILED'}")


if __name__ == "__main__":
    generate_validation_report()
