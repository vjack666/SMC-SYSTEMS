from __future__ import annotations

import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

INPUT_CSV = RESULTS / "experiment_E.csv"


def _find_date_col(df: pd.DataFrame) -> str:
    candidates = [c for c in df.columns if "time" in c.lower() or "date" in c.lower()]
    if "exit_time" in df.columns:
        return "exit_time"
    if "entry_time" in df.columns:
        return "entry_time"
    if candidates:
        return candidates[0]
    raise ValueError("No fecha encontrada en columnas")


def _load_data() -> pd.DataFrame:
    df = pd.read_csv(INPUT_CSV)
    date_col = _find_date_col(df)
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    if df[date_col].isna().any():
        raise ValueError(f"Valores NaT en columna de fecha {date_col}: {df[date_col].isna().sum()}")
    df = df.sort_values(date_col).reset_index(drop=True)
    df["_date_col"] = date_col
    return df


def build_streaks(df: pd.DataFrame) -> pd.DataFrame:
    signs = []
    for pnl in df["pnl_r"]:
        if pd.isna(pnl):
            signs.append("flat")
        elif pnl > 0:
            signs.append("win")
        elif pnl < 0:
            signs.append("loss")
        else:
            signs.append("flat")
    streaks = []
    current = None
    for idx, sign in enumerate(signs):
        if current is None or sign != current["sign"]:
            current = {
                "sign": sign,
                "start_idx": idx,
                "end_idx": idx,
                "length": 1,
                "pnl_r": float(df.loc[idx, "pnl_r"] if pd.notna(df.loc[idx, "pnl_r"]) else 0.0),
                "pnl_usd": float(df.loc[idx, "pnl_usd"] if "pnl_usd" in df.columns and pd.notna(df.loc[idx, "pnl_usd"]) else 0.0),
            }
            streaks.append(current)
        else:
            current["end_idx"] = idx
            current["length"] += 1
            current["pnl_r"] += float(df.loc[idx, "pnl_r"] if pd.notna(df.loc[idx, "pnl_r"]) else 0.0)
            current["pnl_usd"] += float(df.loc[idx, "pnl_usd"] if "pnl_usd" in df.columns and pd.notna(df.loc[idx, "pnl_usd"]) else 0.0)
    records = []
    for i, s in enumerate(streaks, 1):
        start_row = df.loc[s["start_idx"]]
        end_row = df.loc[s["end_idx"]]
        records.append({
            "streak_id": i,
            "sign": s["sign"],
            "length": s["length"],
            "start_time": start_row[_find_date_col(df)],
            "end_time": end_row[_find_date_col(df)],
            "pnl_r": s["pnl_r"],
            "pnl_usd": s["pnl_usd"],
            "start_setup_id": start_row["setup_id"],
            "end_setup_id": end_row["setup_id"],
        })
    return pd.DataFrame(records)


def write_streak_report(streak_df: pd.DataFrame) -> None:
    loss_streaks = streak_df[streak_df["sign"] == "loss"]
    win_streaks = streak_df[streak_df["sign"] == "win"]
    report = []
    report.append("# Streak Analysis Report\n")
    report.append(f"Total trades: {int(sum(streak_df['length']))}\n")
    report.append(f"Total streaks: {len(streak_df)}\n")
    report.append("\n## Winning / Losing streaks\n")
    if not win_streaks.empty:
        report.append(f"- Longest winning streak: {int(win_streaks['length'].max())} trades\n")
        report.append(f"- Mean winning streak length: {win_streaks['length'].mean():.2f}\n")
    else:
        report.append("- No winning streaks encontrados.\n")
    if not loss_streaks.empty:
        report.append(f"- Longest losing streak: {int(loss_streaks['length'].max())} trades\n")
        report.append(f"- 95th percentile losing streak length: {int(np.percentile(loss_streaks['length'], 95))}\n")
        report.append(f"- Mean losing streak length: {loss_streaks['length'].mean():.2f}\n")
    else:
        report.append("- No losing streaks encontrados.\n")
    report.append("\n## Distribution of streaks\n")
    counts = streak_df.groupby(["sign", "length"]).size().reset_index(name="count")
    report.append(counts.to_string(index=False))
    report_text = "\n".join(report)
    (RESULTS / "streak_report.md").write_text(report_text, encoding="utf-8")


def build_drawdown_timeline(df: pd.DataFrame) -> pd.DataFrame:
    date_col = _find_date_col(df)
    df = df.copy()
    df["date"] = df[date_col].dt.floor("D")
    if "pnl_usd" not in df.columns:
        raise ValueError("Campo pnl_usd requerido para drawdown timeline")
    daily = df.groupby("date")["pnl_usd"].sum().reset_index()
    daily = daily.sort_values("date").reset_index(drop=True)
    daily["equity"] = daily["pnl_usd"].cumsum()
    daily["peak"] = daily["equity"].cummax()
    daily["drawdown_usd"] = daily["peak"] - daily["equity"]
    daily["drawdown_pct"] = np.where(daily["peak"] > 0, daily["drawdown_usd"] / daily["peak"], 0.0)
    daily["period_type"] = "daily"

    weekly = daily.set_index("date").resample("W-SUN")["pnl_usd"].sum().reset_index()
    weekly["equity"] = weekly["pnl_usd"].cumsum()
    weekly["peak"] = weekly["equity"].cummax()
    weekly["drawdown_usd"] = weekly["peak"] - weekly["equity"]
    weekly["drawdown_pct"] = np.where(weekly["peak"] > 0, weekly["drawdown_usd"] / weekly["peak"], 0.0)
    weekly["period_type"] = "weekly"

    monthly = daily.set_index("date").resample("ME")["pnl_usd"].sum().reset_index()
    monthly["equity"] = monthly["pnl_usd"].cumsum()
    monthly["peak"] = monthly["equity"].cummax()
    monthly["drawdown_usd"] = monthly["peak"] - monthly["equity"]
    monthly["drawdown_pct"] = np.where(monthly["peak"] > 0, monthly["drawdown_usd"] / monthly["peak"], 0.0)
    monthly["period_type"] = "monthly"

    timeline = pd.concat([daily, weekly, monthly], ignore_index=True, sort=False)
    timeline = timeline[["period_type", "date", "pnl_usd", "equity", "peak", "drawdown_usd", "drawdown_pct"]]
    timeline.to_csv(RESULTS / "drawdown_timeline.csv", index=False)
    return timeline


def plot_drawdown(timeline: pd.DataFrame) -> None:
    daily = timeline[timeline["period_type"] == "daily"].copy()
    fig, axs = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    axs[0].plot(daily["date"], daily["equity"], label="Equity (USD)")
    axs[0].fill_between(daily["date"], daily["equity"], daily["peak"], color="red", alpha=0.2)
    axs[0].set_ylabel("Equity USD")
    axs[0].set_title("Daily Equity Curve")
    axs[0].legend()
    axs[1].plot(daily["date"], daily["drawdown_pct"] * 100, color="tab:red", label="Drawdown %")
    axs[1].set_ylabel("Drawdown %")
    axs[1].set_title("Daily Drawdown")
    axs[1].set_xlabel("Date")
    axs[1].legend()
    fig.tight_layout()
    fig.savefig(RESULTS / "drawdown_timeline.png")
    plt.close(fig)


def simulate_funding(df: pd.DataFrame) -> pd.DataFrame:
    if "pnl_r" not in df.columns:
        raise ValueError("Campo pnl_r requerido para simulación de fondeo")
    date_col = _find_date_col(df)
    df = df.copy()
    df["trade_date"] = df[date_col].dt.floor("D")
    accounts = [10000, 25000, 50000, 100000]
    rows = []
    for start_cap in accounts:
        equity = float(start_cap)
        peak = equity
        start_equity = equity
        daily_start_equity = equity
        current_day = None
        reason = "not reached"
        days_to_pass = None
        passed = False
        for _, row in df.iterrows():
            trade_day = row["trade_date"]
            if current_day is None:
                current_day = trade_day
                daily_start_equity = equity
            elif trade_day != current_day:
                current_day = trade_day
                daily_start_equity = equity
            pnl_r = float(row["pnl_r"])
            pnl_usd = equity * pnl_r * 0.01
            equity += pnl_usd
            if equity > peak:
                peak = equity
            daily_dd = max(0.0, daily_start_equity - equity)
            total_dd = max(0.0, peak - equity)
            if daily_dd > start_cap * 0.05:
                reason = "daily drawdown breach"
                break
            if total_dd > start_cap * 0.10:
                reason = "total drawdown breach"
                break
            if equity >= start_equity * 1.08:
                passed = True
                days_to_pass = (trade_day - df.loc[0, date_col].floor("D")).days + 1
                reason = "target reached"
                break
        if not passed and reason == "not reached":
            reason = "no target reached"
        rows.append({
            "start_capital": start_cap,
            "passed": passed,
            "pass_pct": 100.0 if passed else 0.0,
            "days_to_pass": days_to_pass if passed else None,
            "reason": reason,
            "final_equity": equity,
            "max_drawdown_usd": float(total_dd),
            "max_drawdown_pct": float(total_dd / start_cap * 100.0),
        })
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "funding_simulation_summary.csv", index=False)
    return out


def write_funding_report(summary: pd.DataFrame) -> None:
    lines = ["# Funding Simulation Report", ""]
    for _, row in summary.iterrows():
        lines.append(f"## Capital inicial {int(row['start_capital']):,}")
        lines.append(f"- Passed: {row['passed']} ({row['pass_pct']:.1f}%)")
        lines.append(f"- Days to pass: {int(row['days_to_pass']) if not pd.isna(row['days_to_pass']) else 'N/A'}")
        lines.append(f"- Final equity: ${row['final_equity']:.2f}")
        lines.append(f"- Max drawdown: ${row['max_drawdown_usd']:.2f} ({row['max_drawdown_pct']:.2f}%)")
        lines.append(f"- Failure reason: {row['reason']}\n")
    (RESULTS / "funding_simulation_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    df = _load_data()
    streak_df = build_streaks(df)
    streak_df.to_csv(RESULTS / "streak_analysis.csv", index=False)
    write_streak_report(streak_df)
    timeline = build_drawdown_timeline(df)
    plot_drawdown(timeline)
    funding_summary = simulate_funding(df)
    write_funding_report(funding_summary)
    print("Completed analysis and saved outputs to results/")


if __name__ == "__main__":
    main()
