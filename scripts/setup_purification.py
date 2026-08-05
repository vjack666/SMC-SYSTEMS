from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

RESULTS_DIR = Path("results")
PURIFICATION_DIR = RESULTS_DIR / "setup_purification"
EXPERIMENT_E_PATH = RESULTS_DIR / "experiment_E.csv"
FORNSIC_PATH = RESULTS_DIR / "forensic_trades_dataset.csv"

PURIFICATION_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class PurificationExperiment:
    code: str
    label: str
    description: str
    filter_fn: Callable[[pd.DataFrame], pd.Series]


def _load_experiment_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df = df.copy()
    df["session_bucket"] = df["session_bucket"].astype(str).str.lower()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    df["hour"] = pd.to_numeric(df.get("hour", pd.Series([], dtype="float64")), errors="coerce").astype(pd.Int64Dtype())
    df["mitigation_depth_pct"] = pd.to_numeric(df["mitigation_depth_pct"], errors="coerce")
    df["pnl_r"] = pd.to_numeric(df["pnl_r"], errors="coerce")
    return df


def _load_forensic_features(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df = df.copy()
    df["setup_id"] = df["setup_id"].astype(str)
    df["symbol"] = df["symbol"].astype(str).str.upper()
    df["side"] = df["side"].astype(str)
    df["entry_idx"] = pd.to_numeric(df["entry_idx"], errors="coerce").astype(pd.Int64Dtype())
    df["sl_atr_mult"] = pd.to_numeric(df["sl_atr_mult"], errors="coerce")
    df["fvg_size_atr"] = pd.to_numeric(df["fvg_size_atr"], errors="coerce")
    df["hour"] = pd.to_numeric(df["hour"], errors="coerce").astype(pd.Int64Dtype())
    return df[["setup_id", "symbol", "side", "entry_idx", "sl_atr_mult", "fvg_size_atr", "hour"]]


def _calculate_metrics(df: pd.DataFrame) -> dict[str, float | int]:
    trades = df["pnl_r"].dropna().astype(float)
    count = int(len(trades))
    if count == 0:
        return {
            "trades": 0,
            "winrate": float("nan"),
            "profit_factor": float("nan"),
            "expectancy": float("nan"),
            "sharpe": float("nan"),
            "max_drawdown": float("nan"),
            "equity_final": 0.0,
        }

    wins = trades[trades > 0].sum()
    losses = -trades[trades < 0].sum()
    profit_factor = float(wins / losses) if losses > 0 else float("inf")
    expectancy = float(trades.mean())
    net_r = float(trades.sum())
    equity_curve = trades.cumsum()
    drawdown = float((equity_curve - equity_curve.cummax()).min())
    max_drawdown = abs(drawdown)
    sharpe = (
        float((trades.mean() / trades.std(ddof=0)) * np.sqrt(count))
        if count > 1 and trades.std(ddof=0) > 0
        else float("nan")
    )

    return {
        "trades": count,
        "winrate": float((trades > 0).mean()),
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "equity_final": net_r,
    }


def _baseline_metrics(df_e: pd.DataFrame) -> dict[str, float | int]:
    return _calculate_metrics(df_e)


def _select_best_candidate(summary: pd.DataFrame, baseline_dd: float) -> dict[str, object]:
    thresholds = {
        "profit_factor": 1.80,
        "expectancy": 0.40,
        "max_drawdown": baseline_dd,
    }

    candidate_df = summary.copy()
    candidate_df["meets_pf"] = candidate_df["profit_factor"] > thresholds["profit_factor"]
    candidate_df["meets_expectancy"] = candidate_df["expectancy"] > thresholds["expectancy"]
    candidate_df["meets_dd"] = candidate_df["max_drawdown"] < thresholds["max_drawdown"]
    candidate_df["meets_all"] = candidate_df["meets_pf"] & candidate_df["meets_expectancy"] & candidate_df["meets_dd"]

    if not candidate_df[candidate_df["meets_all"]].empty:
        winner = candidate_df[candidate_df["meets_all"]].sort_values(
            by=["expectancy", "profit_factor", "trades"], ascending=[False, False, False]
        ).iloc[0]
        reason = "Meets all success thresholds."
    else:
        candidate_df["score"] = (
            0.4 * np.minimum(candidate_df["profit_factor"], thresholds["profit_factor"]) / thresholds["profit_factor"]
            + 0.4 * np.minimum(candidate_df["expectancy"], thresholds["expectancy"]) / thresholds["expectancy"]
            + 0.2 * np.minimum(baseline_dd / (candidate_df["max_drawdown"] + 1e-9), 1.0)
        )
        winner = candidate_df.sort_values(by=["score", "expectancy", "profit_factor"], ascending=[False, False, False]).iloc[0]
        reason = "Best candidate by weighted improvement score; no experiment met all thresholds."

    return {
        "code": winner["code"],
        "label": winner["label"],
        "description": winner["description"],
        "metrics": {
            "trades": int(winner["trades"]),
            "winrate": float(winner["winrate"]),
            "profit_factor": float(winner["profit_factor"]),
            "expectancy": float(winner["expectancy"]),
            "sharpe": float(winner["sharpe"]),
            "max_drawdown": float(winner["max_drawdown"]),
            "equity_final": float(winner["equity_final"]),
        },
        "meets_all": bool(winner["meets_all"]),
        "reason": reason,
    }


def _write_best_candidate(candidate: dict[str, object], baseline: dict[str, float | int], path: Path) -> None:
    report = [
        f"# Best Setup Candidate for Setup Purification\n",
        f"**Selected experiment**: {candidate['code']} — {candidate['label']}\n",
        f"**Description**: {candidate['description']}\n",
        f"**Meets all target thresholds**: {candidate['meets_all']}\n",
        f"**Reason**: {candidate['reason']}\n",
        "## Baseline Experiment E Metrics\n",
        f"- trades: {baseline['trades']}\n",
        f"- winrate: {baseline['winrate']:.4f}\n",
        f"- profit_factor: {baseline['profit_factor']:.4f}\n",
        f"- expectancy: {baseline['expectancy']:.4f}R\n",
        f"- sharpe: {baseline['sharpe']:.4f}\n",
        f"- max_drawdown: {baseline['max_drawdown']:.4f}R\n",
        f"- equity_final: {baseline['equity_final']:.4f}R\n",
        "## Best Candidate Metrics\n",
        f"- trades: {candidate['metrics']['trades']}\n",
        f"- winrate: {candidate['metrics']['winrate']:.4f}\n",
        f"- profit_factor: {candidate['metrics']['profit_factor']:.4f}\n",
        f"- expectancy: {candidate['metrics']['expectancy']:.4f}R\n",
        f"- sharpe: {candidate['metrics']['sharpe']:.4f}\n",
        f"- max_drawdown: {candidate['metrics']['max_drawdown']:.4f}R\n",
        f"- equity_final: {candidate['metrics']['equity_final']:.4f}R\n",
    ]
    path.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    df_e = _load_experiment_dataset(EXPERIMENT_E_PATH)
    forensic_features = _load_forensic_features(FORNSIC_PATH)

    merge_keys = ["setup_id", "symbol", "side", "entry_idx", "sl_atr_mult"]
    df_e = df_e.merge(forensic_features, on=merge_keys, how="left", validate="many_to_one")

    if df_e["fvg_size_atr"].isna().any():
        missing = int(df_e["fvg_size_atr"].isna().sum())
        raise ValueError(f"Missing fvg_size_atr for {missing} experiment E rows after merge.")

    if "hour" not in df_e.columns or df_e["hour"].isna().any():
        df_e["hour"] = pd.to_datetime(df_e["create_time"], utc=True).dt.hour
    df_e["hour"] = pd.to_numeric(df_e["hour"], errors="coerce").astype(pd.Int64Dtype())
    df_e["session_bucket"] = df_e["session_bucket"].astype(str).str.lower()
    df_e["symbol"] = df_e["symbol"].astype(str).str.upper()

    baseline = _baseline_metrics(df_e)
    baseline_dd = float(baseline["max_drawdown"])

    experiments = [
        PurificationExperiment(
            code="P1",
            label="Exclude London session",
            description="Exclude trades occurring in session_bucket == 'london'.",
            filter_fn=lambda x: x["session_bucket"] != "london",
        ),
        PurificationExperiment(
            code="P2",
            label="Exclude EURUSD",
            description="Exclude symbol == 'EURUSD'.",
            filter_fn=lambda x: x["symbol"] != "EURUSD",
        ),
        PurificationExperiment(
            code="P3",
            label="Only XAUUSD and GBPUSD",
            description="Keep only symbol values XAUUSD or GBPUSD.",
            filter_fn=lambda x: x["symbol"].isin(["XAUUSD", "GBPUSD"]),
        ),
        PurificationExperiment(
            code="P4",
            label="Only hours 7, 14, 15, 16, 17 UTC",
            description="Filter to hour values in {7,14,15,16,17}.",
            filter_fn=lambda x: x["hour"].isin([7, 14, 15, 16, 17]),
        ),
        PurificationExperiment(
            code="P5",
            label="Filter large FVG size",
            description="Keep only trades with fvg_size_atr >= 2.",
            filter_fn=lambda x: x["fvg_size_atr"] >= 2.0,
        ),
        PurificationExperiment(
            code="P6",
            label="Filter mitigation depth between 20% and 40%",
            description="Keep only trades with 0.20 <= mitigation_depth_pct <= 0.40.",
            filter_fn=lambda x: (x["mitigation_depth_pct"] >= 0.20) & (x["mitigation_depth_pct"] <= 0.40),
        ),
        PurificationExperiment(
            code="P7",
            label="Combine P1+P3+P4+P5+P6",
            description=(
                "Exclude London, keep only XAUUSD and GBPUSD, hour in {7,14,15,16,17}, "
                "fvg_size_atr >= 2, and 0.20 <= mitigation_depth_pct <= 0.40."
            ),
            filter_fn=lambda x: (
                (x["session_bucket"] != "london")
                & x["symbol"].isin(["XAUUSD", "GBPUSD"])
                & x["hour"].isin([7, 14, 15, 16, 17])
                & (x["fvg_size_atr"] >= 2.0)
                & (x["mitigation_depth_pct"] >= 0.20)
                & (x["mitigation_depth_pct"] <= 0.40)
            ),
        ),
    ]

    rows = []
    for exp in experiments:
        subset = df_e[exp.filter_fn(df_e)].copy()
        metrics = _calculate_metrics(subset)
        metrics_row = {
            "code": exp.code,
            "label": exp.label,
            "description": exp.description,
            **metrics,
        }
        rows.append(metrics_row)
        subset.to_csv(PURIFICATION_DIR / f"{exp.code}_trades.csv", index=False)

    summary = pd.DataFrame(rows)
    summary = summary[
        ["code", "label", "description", "trades", "winrate", "profit_factor", "expectancy", "sharpe", "max_drawdown", "equity_final"]
    ]
    summary.to_csv(PURIFICATION_DIR / "purification_comparison.csv", index=False)

    candidate = _select_best_candidate(summary, baseline_dd)
    _write_best_candidate(candidate, baseline, PURIFICATION_DIR / "best_setup_candidate.md")

    print("Purification analysis completed.")
    print(f"Baseline Experiment E metrics: {baseline}")
    print(f"Best candidate: {candidate['code']} - {candidate['label']}")
    print(f"Saved comparison CSV to {PURIFICATION_DIR / 'purification_comparison.csv'}")
    print(f"Saved markdown summary to {PURIFICATION_DIR / 'best_setup_candidate.md'}")


if __name__ == '__main__':
    main()
