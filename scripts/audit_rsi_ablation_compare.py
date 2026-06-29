from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from modules.pullback import build_pullback_view

try:
    from scipy.stats import mannwhitneyu
except ImportError:  # pragma: no cover
    mannwhitneyu = None


SYMBOLS = ("EURUSD", "GBPUSD", "XAUUSD")
HORIZONS = (1, 3, 5, 10, 20)
METRICS = (
    "valid_count",
    "invalid_count",
    "valid_rate",
    "signed_return_1",
    "signed_return_3",
    "signed_return_5",
    "signed_return_10",
    "signed_return_20",
    "mfe_r_10",
    "continuity_10",
    "post_structure_break_10",
    "pullback_score_mean",
)


def _future_window_max(arr: np.ndarray, h: int) -> np.ndarray:
    n = len(arr)
    out = np.full(n, np.nan, dtype=float)
    if n <= h:
        return out
    win = np.lib.stride_tricks.sliding_window_view(arr[1:], h)
    out[: n - h] = win.max(axis=1)
    return out


def _future_window_min(arr: np.ndarray, h: int) -> np.ndarray:
    n = len(arr)
    out = np.full(n, np.nan, dtype=float)
    if n <= h:
        return out
    win = np.lib.stride_tricks.sliding_window_view(arr[1:], h)
    out[: n - h] = win.min(axis=1)
    return out


def _add_forward_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()

    sign = out["macro_direction"].map({"BULLISH": 1.0, "BEARISH": -1.0}).fillna(0.0).to_numpy(dtype=float)
    close = pd.to_numeric(out["close"], errors="coerce").to_numpy(dtype=float)
    high = pd.to_numeric(out["high"], errors="coerce").to_numpy(dtype=float)
    low = pd.to_numeric(out["low"], errors="coerce").to_numpy(dtype=float)
    atr = pd.to_numeric(out["atr"], errors="coerce").replace(0.0, np.nan).to_numpy(dtype=float)

    swing_high_ref = pd.to_numeric(out["high"].rolling(20, min_periods=5).max().shift(1), errors="coerce").to_numpy(dtype=float)
    swing_low_ref = pd.to_numeric(out["low"].rolling(20, min_periods=5).min().shift(1), errors="coerce").to_numpy(dtype=float)

    for h in HORIZONS:
        future_close = pd.to_numeric(out["close"].shift(-h), errors="coerce").to_numpy(dtype=float)
        out[f"signed_return_{h}"] = sign * (future_close - close) / atr

        max_future = _future_window_max(high, h)
        min_future = _future_window_min(low, h)

        mfe_bull = (max_future - close) / atr
        mfe_bear = (close - min_future) / atr
        out[f"mfe_r_{h}"] = np.where(sign > 0, mfe_bull, np.where(sign < 0, mfe_bear, np.nan))

        out[f"continuity_{h}"] = (pd.to_numeric(out[f"signed_return_{h}"], errors="coerce") > 0).astype(float)
        out.loc[sign == 0, f"continuity_{h}"] = np.nan

        bos_break_bull = min_future < swing_low_ref
        bos_break_bear = max_future > swing_high_ref
        out[f"post_structure_break_{h}"] = np.where(sign > 0, bos_break_bull, np.where(sign < 0, bos_break_bear, np.nan))

    return out


def _build_variant(use_rsi: bool) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for symbol in SYMBOLS:
        v = build_pullback_view(symbol=symbol, timeframe="M15", data_dir=Path("data/mt5"), use_rsi=use_rsi)
        v["symbol"] = symbol
        frames.append(v)

    df = pd.concat(frames, ignore_index=True)
    df = _add_forward_metrics(df)
    df["is_valid"] = df["pullback_ready"].astype(bool)
    df["is_invalid"] = df["pullback_state"].isin(["BULLISH_PULLBACK_INVALID", "BEARISH_PULLBACK_INVALID"])
    return df


def _metric_summary(df: pd.DataFrame) -> dict[str, float]:
    valid = df[df["is_valid"]]
    out: dict[str, float] = {
        "valid_count": float(valid.shape[0]),
        "invalid_count": float(df["is_invalid"].sum()),
        "valid_rate": float(df["is_valid"].mean()),
        "mfe_r_10": float(pd.to_numeric(valid["mfe_r_10"], errors="coerce").mean()),
        "continuity_10": float(pd.to_numeric(valid["continuity_10"], errors="coerce").mean()),
        "post_structure_break_10": float(pd.to_numeric(valid["post_structure_break_10"], errors="coerce").mean()),
        "pullback_score_mean": float(pd.to_numeric(valid["pullback_score"], errors="coerce").mean()),
    }
    for h in HORIZONS:
        out[f"signed_return_{h}"] = float(pd.to_numeric(valid[f"signed_return_{h}"], errors="coerce").mean())
    return out


def _compare_table(base: dict[str, float], exp: dict[str, float]) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    for m in METRICS:
        b = float(base.get(m, np.nan))
        e = float(exp.get(m, np.nan))
        abs_diff = e - b
        pct_diff = np.nan
        if np.isfinite(b) and b != 0:
            pct_diff = (abs_diff / b) * 100.0
        rows.append(
            {
                "metric": m,
                "baseline_with_rsi": b,
                "experimental_without_rsi": e,
                "abs_diff_no_rsi_minus_base": abs_diff,
                "pct_diff_no_rsi_minus_base": float(pct_diff) if np.isfinite(pct_diff) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _cohen_d(a: pd.Series, b: pd.Series) -> float:
    a = pd.to_numeric(a, errors="coerce").dropna()
    b = pd.to_numeric(b, errors="coerce").dropna()
    if len(a) < 2 or len(b) < 2:
        return np.nan
    pooled = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2.0)
    if not np.isfinite(pooled) or pooled <= 0:
        return np.nan
    return float((a.mean() - b.mean()) / pooled)


def _stat_tests(base_df: pd.DataFrame, exp_df: pd.DataFrame) -> pd.DataFrame:
    base_valid = base_df[base_df["is_valid"]]
    exp_valid = exp_df[exp_df["is_valid"]]

    metric_list = [
        "signed_return_1",
        "signed_return_3",
        "signed_return_5",
        "signed_return_10",
        "signed_return_20",
        "mfe_r_10",
        "continuity_10",
        "post_structure_break_10",
        "pullback_score",
    ]

    rows: list[dict[str, float | int | str]] = []
    for m in metric_list:
        a = pd.to_numeric(base_valid[m], errors="coerce").dropna()
        b = pd.to_numeric(exp_valid[m], errors="coerce").dropna()
        p_value = np.nan
        if mannwhitneyu is not None and len(a) > 1 and len(b) > 1:
            try:
                _, p = mannwhitneyu(a.to_numpy(), b.to_numpy(), alternative="two-sided")
                p_value = float(p)
            except ValueError:
                p_value = np.nan

        rows.append(
            {
                "metric": m,
                "base_mean": float(a.mean()) if len(a) else np.nan,
                "no_rsi_mean": float(b.mean()) if len(b) else np.nan,
                "delta_no_rsi_minus_base": float(b.mean() - a.mean()) if len(a) and len(b) else np.nan,
                "effect_size_cohen_d": _cohen_d(b, a),
                "p_value_mannwhitney": p_value,
                "base_n": int(len(a)),
                "no_rsi_n": int(len(b)),
            }
        )

    return pd.DataFrame(rows)


def _temporal_stability(df: pd.DataFrame, label: str) -> tuple[pd.DataFrame, dict[str, float]]:
    valid = df[df["is_valid"]].sort_values("time").reset_index(drop=True)
    n = len(valid)
    cut1 = n // 3
    cut2 = (2 * n) // 3

    valid["time_block"] = "FINAL"
    valid.loc[: cut1 - 1, "time_block"] = "INICIO"
    valid.loc[cut1: cut2 - 1, "time_block"] = "MITAD"

    rows: list[dict[str, float | int | str]] = []
    for block, sub in valid.groupby("time_block"):
        rows.append(
            {
                "variant": label,
                "time_block": block,
                "n": int(len(sub)),
                "signed_return_10_mean": float(pd.to_numeric(sub["signed_return_10"], errors="coerce").mean()),
                "continuity_10_mean": float(pd.to_numeric(sub["continuity_10"], errors="coerce").mean()),
                "pullback_score_mean": float(pd.to_numeric(sub["pullback_score"], errors="coerce").mean()),
            }
        )

    block_df = pd.DataFrame(rows)
    summary = {
        "variant": label,
        "std_signed_return_10": float(block_df["signed_return_10_mean"].std(ddof=0)) if len(block_df) else np.nan,
        "std_continuity_10": float(block_df["continuity_10_mean"].std(ddof=0)) if len(block_df) else np.nan,
        "range_signed_return_10": float(block_df["signed_return_10_mean"].max() - block_df["signed_return_10_mean"].min()) if len(block_df) else np.nan,
        "range_continuity_10": float(block_df["continuity_10_mean"].max() - block_df["continuity_10_mean"].min()) if len(block_df) else np.nan,
    }
    return block_df, summary


def main() -> None:
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)

    baseline = _build_variant(use_rsi=True)
    no_rsi = _build_variant(use_rsi=False)

    baseline_summary = _metric_summary(baseline)
    no_rsi_summary = _metric_summary(no_rsi)
    comparison = _compare_table(baseline_summary, no_rsi_summary)
    comparison.to_csv(results_dir / "rsi_ablation_comparison_table.csv", index=False)

    stat_tests = _stat_tests(baseline, no_rsi)
    stat_tests.to_csv(results_dir / "rsi_ablation_metric_tests.csv", index=False)

    base_valid = baseline[baseline["is_valid"]][["symbol", "time"]].drop_duplicates()
    no_rsi_valid = no_rsi[no_rsi["is_valid"]][["symbol", "time"]].drop_duplicates()

    merged = base_valid.merge(no_rsi_valid, on=["symbol", "time"], how="outer", indicator=True)
    valid_additional = int((merged["_merge"] == "right_only").sum())
    valid_disappeared = int((merged["_merge"] == "left_only").sum())

    base_blocks, base_stability = _temporal_stability(baseline, "with_rsi")
    no_rsi_blocks, no_rsi_stability = _temporal_stability(no_rsi, "without_rsi")

    temporal_blocks = pd.concat([base_blocks, no_rsi_blocks], ignore_index=True)
    temporal_blocks.to_csv(results_dir / "rsi_ablation_temporal_blocks.csv", index=False)

    temporal_summary = pd.DataFrame([base_stability, no_rsi_stability])
    temporal_summary.to_csv(results_dir / "rsi_ablation_temporal_stability.csv", index=False)

    summary = {
        "baseline": baseline_summary,
        "without_rsi": no_rsi_summary,
        "valid_additional": valid_additional,
        "valid_disappeared": valid_disappeared,
        "temporal_stability": {
            "with_rsi": base_stability,
            "without_rsi": no_rsi_stability,
            "delta_std_signed_return_10": float(no_rsi_stability["std_signed_return_10"] - base_stability["std_signed_return_10"]),
            "delta_std_continuity_10": float(no_rsi_stability["std_continuity_10"] - base_stability["std_continuity_10"]),
        },
        "files": {
            "comparison": "results/rsi_ablation_comparison_table.csv",
            "stat_tests": "results/rsi_ablation_metric_tests.csv",
            "temporal_blocks": "results/rsi_ablation_temporal_blocks.csv",
            "temporal_stability": "results/rsi_ablation_temporal_stability.csv",
        },
    }

    (results_dir / "rsi_ablation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
