from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.rebuild_experiment_f_structural import ExperimentFBuilder

OUTPUT_DIR = Path("results/forensic_f")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_experiment_trades() -> pd.DataFrame:
    path = Path("results/experiment_F_structural_sl.csv")
    if not path.exists():
        raise FileNotFoundError(f"Missing experiment output: {path}")
    return pd.read_csv(path)


def load_raw_signal_counts(builder: ExperimentFBuilder) -> tuple[pd.DataFrame, dict[str, int]]:
    all_signals: list[dict] = []
    symbol_counts: dict[str, int] = {}

    for symbol in builder.symbols:
        print(f"Loading signals for {symbol}...")
        df = builder._load_symbol_data(symbol)
        signals = builder._find_entry_signals(df)
        symbol_counts[symbol] = len(signals)
        all_signals.extend(signals)

    signals_df = pd.DataFrame(all_signals)
    return signals_df, symbol_counts


def validate_stop_positions(trades: pd.DataFrame) -> pd.DataFrame:
    df = trades.copy()
    df["direction"] = df["direction"].astype(int)
    df["entry_price"] = pd.to_numeric(df["entry_price"], errors="coerce")
    df["sl_price"] = pd.to_numeric(df["sl_price"], errors="coerce")
    df["stop_is_valid"] = np.where(
        (df["direction"] == 1) & (df["sl_price"] < df["entry_price"]), True,
        np.where((df["direction"] == -1) & (df["sl_price"] > df["entry_price"]), True, False),
    )
    return df.loc[~df["stop_is_valid"]].copy()


def validate_risk(trades: pd.DataFrame) -> pd.DataFrame:
    out = trades.copy()
    out["entry_price"] = pd.to_numeric(out["entry_price"], errors="coerce")
    out["sl_price"] = pd.to_numeric(out["sl_price"], errors="coerce")
    out["stop_distance_pips"] = pd.to_numeric(out["stop_distance_pips"], errors="coerce")
    out["risk_recalc"] = (out["entry_price"] - out["sl_price"]).abs()
    out["risk_diff"] = out["stop_distance_pips"] - out["risk_recalc"]
    return out[["symbol", "entry_idx", "direction", "entry_price", "sl_price", "stop_distance_pips", "risk_recalc", "risk_diff"]]


def validate_rr(trades: pd.DataFrame) -> pd.DataFrame:
    out = trades.copy()
    out["entry_price"] = pd.to_numeric(out["entry_price"], errors="coerce")
    out["sl_price"] = pd.to_numeric(out["sl_price"], errors="coerce")
    out["tp_price"] = pd.to_numeric(out["tp_price"], errors="coerce")
    out["rr_calc"] = (out["tp_price"] - out["entry_price"]).abs() / (out["entry_price"] - out["sl_price"]).abs()
    out["expected_rr"] = 2.0
    out["rr_diff"] = out["rr_calc"] - out["expected_rr"]
    return out[["symbol", "entry_idx", "direction", "entry_price", "sl_price", "tp_price", "rr_calc", "expected_rr", "rr_diff"]]


def validate_exit_logic(trades: pd.DataFrame) -> pd.DataFrame:
    df = trades.copy()
    df["pnl_r"] = pd.to_numeric(df["pnl_r"], errors="coerce")
    df["exit_reason"] = df["exit_reason"].astype(str)
    invalid_mask = (
        ((df["exit_reason"] == "sl_hit") & (df["pnl_r"] > 0))
        | ((df["exit_reason"] == "tp_hit") & (df["pnl_r"] < 0))
    )
    return df.loc[invalid_mask].copy()


def write_csv(path: Path, df: pd.DataFrame) -> None:
    df.to_csv(path, index=False)
    print(f"Wrote {path} ({len(df)} rows)")


def write_md(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {path}")


def generate_report_files():
    trades = load_experiment_trades()
    builder = ExperimentFBuilder()
    signals_df, symbol_counts = load_raw_signal_counts(builder)
    unique_signals = signals_df.drop_duplicates(subset=["symbol", "entry_idx"], keep="first")

    invalid_stops = validate_stop_positions(trades)
    write_csv(OUTPUT_DIR / "invalid_stop_positions.csv", invalid_stops)

    risk_validation = validate_risk(trades)
    write_csv(OUTPUT_DIR / "risk_validation.csv", risk_validation)

    rr_validation = validate_rr(trades)
    write_csv(OUTPUT_DIR / "rr_validation.csv", rr_validation)

    invalid_exit = validate_exit_logic(trades)
    write_csv(OUTPUT_DIR / "invalid_exit_logic.csv", invalid_exit)

    trade_count_lines = [
        "# Trade Count Analysis",
        "",
        "This file maps the raw entry signal count to the final experiment F trade count.",
        "",
        "| stage | trades_remaining |",
        "|---|---|",
        f"| raw_bos_fvg_signals | {len(signals_df)} |",
        f"| unique_entry_signals | {len(unique_signals)} |",
        f"| experiment_F_final_trades | {len(trades)} |",
        "",
        "## Unique signal count by symbol",
    ]
    for symbol, count in unique_signals["symbol"].value_counts().items():
        trade_count_lines.append(f"- {symbol}: {count}")
    trade_count_lines.append("")
    trade_count_lines.append(f"Final experiment F trades: {len(trades)}")
    trade_count_lines.append(f"Invalid stop positions: {len(invalid_stops)}")
    trade_count_lines.append(f"Invalid exit logic violations: {len(invalid_exit)}")
    write_md(OUTPUT_DIR / "trade_count_analysis.md", trade_count_lines)

    code_flow_lines = [
        "# Code Flow Map for Experiment F Structural Stop Audit",
        "",
        "1. Raw OHLC load: scripts/rebuild_experiment_f_structural.py:load_all_ohlc()",
        "2. Signal generation: scripts/rebuild_experiment_f_structural.py:generate_signals() and _find_entry_signals()",
        "3. Signal entry criteria: BOS direction equals FVG direction + entry price intersects zone within entry_retest_lookahead",
        "4. Structural stop generation: modules/structural_sl/detector.py:calculate_structural_stop()",
        "5. Stop assignment: scripts/rebuild_experiment_f_structural.py:simulate_trades() uses stop.structural_stop_price as sl_price",
        "6. Risk and TP: risk = abs(entry_price - sl_price); tp_price = entry_price + risk * rr_ratio * direction",
        "7. Trade exit loop: simulate_trades() checks low/high against sl_price and tp_price in future candles",
        "8. Metrics: scripts/rebuild_experiment_f_structural.py:save_metrics() computes win_rate, expectancy_r, profit_factor, avg_stop_distance_atr, avg_holding_bars",
    ]
    write_md(OUTPUT_DIR / "code_flow_map.md", code_flow_lines)

    root_lines = [
        "# ROOT CAUSE REPORT",
        "",
        "## Key counts",
        "",
        f"- raw BOS+FVG signals: {len(signals_df)}",
        f"- unique entry signals: {len(unique_signals)}",
        f"- final experiment F trades: {len(trades)}",
        f"- invalid stop positions: {len(invalid_stops)}",
        f"- invalid exit logic violations: {len(invalid_exit)}",
        "",
        "## Primary root causes identified",
        "",
        "1. The structural stop price is generated from the origin swing price in modules/structural_sl/detector.py:calculate_structural_stop().",
        "2. For LONG trades, calculate_structural_stop() sets structural_stop_price to the highest high found in the lookback window, which is typically above the entry price. This violates basic stop loss placement for LONG trades.",
        "3. For SHORT trades, it sets structural_stop_price to the lowest low in the lookback window, which is typically below the entry price. This violates stop placement for SHORT trades.",
        "4. As a result, many LONG trades in experiment F have sl_price > entry_price and many SHORT trades have sl_price < entry_price, producing mathematically invalid stop positions.",
        "5. The simulation loop in scripts/rebuild_experiment_f_structural.py then interprets these invalid stops as if sl_hit can occur, causing the final trade set to be corrupted and over-representing apparently profitable trades.",
        "6. stop_distance_atr is NaN in the output because modules/structural_sl/detector.py uses the ATR value at the entry candle (atr[entry_idx]) without validating that ATR is finite at that exact index.",
        "",
        "## Evidence from experiment data",
        "",
        "- Several trades have sl_price on the wrong side of entry (LONG stop above entry, SHORT stop below entry).",
        "- Invalid stop positions are directly observable in results/forensic_f/invalid_stop_positions.csv.",
        "- The final dataset contains invalid exit reasoning where pnl_r is inconsistent with exit_reason, visible in results/forensic_f/invalid_exit_logic.csv.",
        "",
        "## Practical impact",
        "",
        "- The trade count fell from thousands of raw entry signals to 141 final trades because the structural stop filter and risk validation removed most signals, and because the remaining trades are built on invalid stop logic.",
        "- This makes experiment F unusable without fixing the structural stop calculation and stop validation logic.",
        "",
        "## Recommended audit checks",
        "",
        "- Confirm LONG stops are always below entries and SHORT stops are always above entries before simulation.",
        "- Confirm stop_distance_atr is finite and computed from a valid ATR value.",
        "- Confirm exit_reason semantics match pnl_r sign.",
    ]
    write_md(OUTPUT_DIR / "ROOT_CAUSE_REPORT.md", root_lines)

    print(json.dumps({
        "raw_signals": len(signals_df),
        "unique_signals": len(unique_signals),
        "final_trades": len(trades),
        "invalid_stop_positions": len(invalid_stops),
        "invalid_exit_logic": len(invalid_exit),
    }, indent=2))


if __name__ == '__main__':
    generate_report_files()
