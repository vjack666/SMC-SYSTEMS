from __future__ import annotations

import argparse
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
    from scipy.stats import chi2_contingency, mannwhitneyu
except ImportError:  # pragma: no cover
    chi2_contingency = None
    mannwhitneyu = None


SYMBOLS = ("EURUSD", "GBPUSD", "XAUUSD")
HORIZON = 10
TARGETS = ("signed_return_10", "mfe_r_10", "continuity_10")


def _out_path(results_dir: Path, filename: str, suffix: str) -> Path:
    if not suffix:
        return results_dir / filename
    stem, dot, ext = filename.partition(".")
    name = f"{stem}_{suffix}.{ext}" if dot else f"{filename}_{suffix}"
    return results_dir / name


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

    future_close = pd.to_numeric(out["close"].shift(-HORIZON), errors="coerce").to_numpy(dtype=float)
    out["signed_return_10"] = sign * (future_close - close) / atr

    max_future = _future_window_max(high, HORIZON)
    min_future = _future_window_min(low, HORIZON)

    mfe_bull = (max_future - close) / atr
    mfe_bear = (close - min_future) / atr
    out["mfe_r_10"] = np.where(sign > 0, mfe_bull, np.where(sign < 0, mfe_bear, np.nan))

    out["continuity_10"] = (pd.to_numeric(out["signed_return_10"], errors="coerce") > 0).astype(float)
    out.loc[sign == 0, "continuity_10"] = np.nan

    bos_break_bull = min_future < swing_low_ref
    bos_break_bear = max_future > swing_high_ref
    out["post_structure_break_10"] = np.where(sign > 0, bos_break_bull, np.where(sign < 0, bos_break_bear, np.nan))

    return out


def _assign_top_mid_bottom(df: pd.DataFrame, metric: str) -> tuple[pd.Series, float, float]:
    series = pd.to_numeric(df[metric], errors="coerce")
    q1 = float(series.quantile(0.25))
    q3 = float(series.quantile(0.75))
    labels = pd.Series("MID_50", index=df.index, dtype=object)
    labels.loc[series <= q1] = "BOTTOM_25"
    labels.loc[series >= q3] = "TOP_25"
    return labels, q1, q3


def _numeric_stats(top: pd.Series, bottom: pd.Series) -> tuple[float, float, float, float, float | None]:
    top = pd.to_numeric(top, errors="coerce").dropna()
    bottom = pd.to_numeric(bottom, errors="coerce").dropna()
    top_mean = float(top.mean()) if len(top) else np.nan
    bottom_mean = float(bottom.mean()) if len(bottom) else np.nan
    delta = float(top_mean - bottom_mean) if np.isfinite(top_mean) and np.isfinite(bottom_mean) else np.nan

    pooled = np.sqrt((top.var(ddof=1) + bottom.var(ddof=1)) / 2.0) if len(top) > 1 and len(bottom) > 1 else np.nan
    effect = float(delta / pooled) if np.isfinite(pooled) and pooled > 0 else np.nan

    p_value: float | None = None
    if mannwhitneyu is not None and len(top) > 1 and len(bottom) > 1:
        try:
            _, p = mannwhitneyu(top.to_numpy(), bottom.to_numpy(), alternative="two-sided")
            p_value = float(p)
        except ValueError:
            p_value = None
    return top_mean, bottom_mean, delta, effect, p_value


def _categorical_stats(top: pd.Series, bottom: pd.Series) -> tuple[pd.DataFrame, float | None]:
    top_counts = top.astype(str).value_counts()
    bottom_counts = bottom.astype(str).value_counts()
    cats = sorted(set(top_counts.index).union(set(bottom_counts.index)))

    rows: list[dict[str, float | str]] = []
    for c in cats:
        t = int(top_counts.get(c, 0))
        b = int(bottom_counts.get(c, 0))
        top_share = t / max(1, len(top))
        bottom_share = b / max(1, len(bottom))
        ratio = (top_share / bottom_share) if bottom_share > 0 else np.nan
        rows.append(
            {
                "category": c,
                "top_count": t,
                "bottom_count": b,
                "top_share": float(top_share),
                "bottom_share": float(bottom_share),
                "share_ratio_top_over_bottom": float(ratio) if np.isfinite(ratio) else np.nan,
            }
        )

    p_value: float | None = None
    if chi2_contingency is not None and len(cats) > 1:
        contingency = np.array([[int(top_counts.get(c, 0)), int(bottom_counts.get(c, 0))] for c in cats], dtype=int)
        if contingency.sum() > 0:
            try:
                _, p, _, _ = chi2_contingency(contingency)
                p_value = float(p)
            except ValueError:
                p_value = None

    return pd.DataFrame(rows), p_value


def _depth_selected(df: pd.DataFrame) -> pd.Series:
    return np.where(
        df["macro_direction"] == "BULLISH",
        pd.to_numeric(df["pullback_depth_up_atr"], errors="coerce"),
        np.where(
            df["macro_direction"] == "BEARISH",
            pd.to_numeric(df["pullback_depth_down_atr"], errors="coerce"),
            np.nan,
        ),
    )


def _band_conf(series: pd.Series) -> pd.Series:
    return pd.cut(series, bins=[-np.inf, 0.35, 0.50, np.inf], labels=["LOW", "MID", "HIGH"])


def _band_depth(series: pd.Series) -> pd.Series:
    return pd.cut(series, bins=[-np.inf, 1.0, 2.0, np.inf], labels=["SHALLOW", "MEDIUM", "DEEP"])


def _band_atr(series: pd.Series) -> pd.Series:
    return pd.cut(series, bins=[-np.inf, 0.9, 1.2, np.inf], labels=["LOW", "NORMAL", "HIGH"])


def _band_trend(series: pd.Series) -> pd.Series:
    abs_score = series.abs()
    return pd.cut(abs_score, bins=[-np.inf, 30.0, 60.0, np.inf], labels=["WEAK", "MEDIUM", "STRONG"])


def _top_combo_table(df: pd.DataFrame, combo_col: str, group_col: str) -> pd.DataFrame:
    top = df[df[group_col] == "TOP_25"]
    all_valid = df

    top_counts = top[combo_col].astype(str).value_counts()
    all_counts = all_valid[combo_col].astype(str).value_counts()

    rows: list[dict[str, float | int | str]] = []
    for combo, n_top in top_counts.items():
        n_all = int(all_counts.get(combo, 0))
        top_share = n_top / max(1, len(top))
        all_share = n_all / max(1, len(all_valid))
        lift = (top_share / all_share) if all_share > 0 else np.nan
        rows.append(
            {
                "combo": combo,
                "top_count": int(n_top),
                "all_count": n_all,
                "top_share": float(top_share),
                "all_share": float(all_share),
                "lift": float(lift) if np.isfinite(lift) else np.nan,
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["lift", "top_count"], ascending=[False, False])


def main() -> None:
    parser = argparse.ArgumentParser(description="VALID-only pullback audit")
    parser.add_argument("--no-rsi", action="store_true", help="Run pullback view without RSI in classification filters")
    parser.add_argument("--output-suffix", default="", help="Suffix appended to output files")
    args = parser.parse_args()

    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)

    frames: list[pd.DataFrame] = []
    for symbol in SYMBOLS:
        v = build_pullback_view(symbol=symbol, timeframe="M15", data_dir=Path("data/mt5"), use_rsi=not args.no_rsi)
        v["symbol"] = symbol
        frames.append(v)
    df = pd.concat(frames, ignore_index=True)
    df = _add_forward_metrics(df)

    valid = df[df["pullback_ready"] == True].copy()  # noqa: E712
    valid = valid.sort_values("time").reset_index(drop=True)

    if valid.empty:
        raise RuntimeError("No VALID pullbacks found.")

    # PART 1
    p1_rows: list[dict[str, object]] = []
    for metric in TARGETS:
        labels, q1, q3 = _assign_top_mid_bottom(valid, metric)
        valid[f"group_{metric}"] = labels
        counts = labels.value_counts()
        p1_rows.append(
            {
                "metric": metric,
                "q1": q1,
                "q3": q3,
                "top_25_n": int(counts.get("TOP_25", 0)),
                "mid_50_n": int(counts.get("MID_50", 0)),
                "bottom_25_n": int(counts.get("BOTTOM_25", 0)),
                "valid_n": int(len(valid)),
            }
        )
    part1 = pd.DataFrame(p1_rows)
    part1.to_csv(_out_path(results_dir, "valid_pullback_part1_quartiles.csv", args.output_suffix), index=False)

    # PART 2
    num_features = [
        "trend_score",
        "trend_confidence",
        "atr_ratio",
        "rsi",
        "pullback_depth_up_atr",
        "pullback_depth_down_atr",
    ]
    cat_features = ["trend_alignment", "regime_state", "macro_direction"]

    p2_num_rows: list[dict[str, object]] = []
    p2_cat_rows: list[dict[str, object]] = []
    p2_cat_dist: list[pd.DataFrame] = []

    for metric in TARGETS:
        gcol = f"group_{metric}"
        top = valid[valid[gcol] == "TOP_25"]
        bottom = valid[valid[gcol] == "BOTTOM_25"]

        for feat in num_features:
            top_mean, bottom_mean, delta, effect, p_val = _numeric_stats(top[feat], bottom[feat])
            p2_num_rows.append(
                {
                    "target_metric": metric,
                    "feature": feat,
                    "top_mean": top_mean,
                    "bottom_mean": bottom_mean,
                    "delta_mean": delta,
                    "effect_size_cohen_d": effect,
                    "p_value_mannwhitney": p_val,
                }
            )

        for feat in cat_features:
            dist, p_val = _categorical_stats(top[feat], bottom[feat])
            p2_cat_rows.append(
                {
                    "target_metric": metric,
                    "feature": feat,
                    "p_value_chi2": p_val,
                    "top_n": int(len(top)),
                    "bottom_n": int(len(bottom)),
                }
            )
            if not dist.empty:
                dist.insert(0, "feature", feat)
                dist.insert(0, "target_metric", metric)
                p2_cat_dist.append(dist)

    part2_num = pd.DataFrame(p2_num_rows)
    part2_cat = pd.DataFrame(p2_cat_rows)
    part2_num.to_csv(_out_path(results_dir, "valid_pullback_part2_numeric_top_vs_bottom.csv", args.output_suffix), index=False)
    part2_cat.to_csv(_out_path(results_dir, "valid_pullback_part2_categorical_top_vs_bottom.csv", args.output_suffix), index=False)
    if p2_cat_dist:
        pd.concat(p2_cat_dist, ignore_index=True).to_csv(
            _out_path(results_dir, "valid_pullback_part2_categorical_distributions.csv", args.output_suffix), index=False
        )

    # PART 3 combinations
    valid["depth_selected"] = _depth_selected(valid)
    valid["conf_band"] = _band_conf(pd.to_numeric(valid["trend_confidence"], errors="coerce")).astype(str)
    valid["depth_band"] = _band_depth(pd.to_numeric(valid["depth_selected"], errors="coerce")).astype(str)
    valid["atr_band"] = _band_atr(pd.to_numeric(valid["atr_ratio"], errors="coerce")).astype(str)
    valid["trend_band"] = _band_trend(pd.to_numeric(valid["trend_score"], errors="coerce")).astype(str)

    valid["combo_align_regime"] = valid["trend_alignment"].astype(str) + "|" + valid["regime_state"].astype(str)
    valid["combo_conf_depth"] = valid["conf_band"] + "|" + valid["depth_band"]
    valid["combo_atr_trend"] = valid["atr_band"] + "|" + valid["trend_band"]
    valid["combo_bos_choch"] = valid["bos_direction"].astype(str) + "|" + valid["choch_signal"].astype(str)

    fvg_any = (valid["fvg_bullish"].astype(bool) | valid["fvg_bearish"].astype(bool)).map({True: "FVG", False: "NO_FVG"})
    ob_any = (valid["ob_bullish"].astype(bool) | valid["ob_bearish"].astype(bool)).map({True: "OB", False: "NO_OB"})
    valid["combo_fvg_ob"] = fvg_any.astype(str) + "|" + ob_any.astype(str)

    combo_cols = [
        "combo_align_regime",
        "combo_conf_depth",
        "combo_atr_trend",
        "combo_bos_choch",
        "combo_fvg_ob",
    ]

    part3_tables: list[pd.DataFrame] = []
    for metric in TARGETS:
        gcol = f"group_{metric}"
        for combo_col in combo_cols:
            t = _top_combo_table(valid, combo_col, gcol)
            if t.empty:
                continue
            t = t[t["top_count"] >= 5].copy()
            t.insert(0, "combo_type", combo_col)
            t.insert(0, "target_metric", metric)
            part3_tables.append(t.head(20))

    if part3_tables:
        pd.concat(part3_tables, ignore_index=True).to_csv(
            _out_path(results_dir, "valid_pullback_part3_top_combinations.csv", args.output_suffix), index=False
        )

    # PART 4 descriptive ranking
    desc_rows: list[dict[str, object]] = []
    for metric in TARGETS:
        gcol = f"group_{metric}"
        top = valid[valid[gcol] == "TOP_25"]
        bottom = valid[valid[gcol] == "BOTTOM_25"]

        for feat in num_features:
            top_mean, bottom_mean, delta, effect, p_val = _numeric_stats(top[feat], bottom[feat])
            desc_rows.append(
                {
                    "target_metric": metric,
                    "feature": feat,
                    "descriptor_type": "numeric",
                    "top_mean": top_mean,
                    "bottom_mean": bottom_mean,
                    "delta_mean": delta,
                    "effect_size": effect,
                    "p_value": p_val,
                    "abs_effect": abs(effect) if np.isfinite(effect) else np.nan,
                }
            )

    part4_rank = pd.DataFrame(desc_rows).sort_values(["target_metric", "abs_effect"], ascending=[True, False])
    part4_rank.to_csv(_out_path(results_dir, "valid_pullback_part4_descriptive_ranking.csv", args.output_suffix), index=False)

    # PART 5 temporal validation
    valid = valid.sort_values("time").reset_index(drop=True)
    n = len(valid)
    cut1 = n // 3
    cut2 = (2 * n) // 3
    valid["time_block"] = "FINAL"
    valid.loc[: cut1 - 1, "time_block"] = "INICIO"
    valid.loc[cut1: cut2 - 1, "time_block"] = "MITAD"

    p5_rows: list[dict[str, object]] = []
    for block, sub in valid.groupby("time_block"):
        row: dict[str, object] = {
            "time_block": block,
            "n": int(len(sub)),
            "signed_return_10_mean": float(pd.to_numeric(sub["signed_return_10"], errors="coerce").mean()),
            "mfe_r_10_mean": float(pd.to_numeric(sub["mfe_r_10"], errors="coerce").mean()),
            "continuity_10_mean": float(pd.to_numeric(sub["continuity_10"], errors="coerce").mean()),
            "trend_confidence_mean": float(pd.to_numeric(sub["trend_confidence"], errors="coerce").mean()),
            "pullback_score_mean": float(pd.to_numeric(sub["pullback_score"], errors="coerce").mean()),
        }
        p5_rows.append(row)
    part5 = pd.DataFrame(p5_rows)
    part5.to_csv(_out_path(results_dir, "valid_pullback_part5_temporal_blocks.csv", args.output_suffix), index=False)

    # PART 6 final evidence summary
    summary = {
        "dataset": {
            "valid_n": int(len(valid)),
            "symbols": list(SYMBOLS),
            "horizon": HORIZON,
            "use_rsi": bool(not args.no_rsi),
        },
        "files": {
            "part1": str(_out_path(results_dir, "valid_pullback_part1_quartiles.csv", args.output_suffix)),
            "part2_numeric": str(_out_path(results_dir, "valid_pullback_part2_numeric_top_vs_bottom.csv", args.output_suffix)),
            "part2_categorical": str(_out_path(results_dir, "valid_pullback_part2_categorical_top_vs_bottom.csv", args.output_suffix)),
            "part2_categorical_dist": str(_out_path(results_dir, "valid_pullback_part2_categorical_distributions.csv", args.output_suffix)),
            "part3": str(_out_path(results_dir, "valid_pullback_part3_top_combinations.csv", args.output_suffix)),
            "part4": str(_out_path(results_dir, "valid_pullback_part4_descriptive_ranking.csv", args.output_suffix)),
            "part5": str(_out_path(results_dir, "valid_pullback_part5_temporal_blocks.csv", args.output_suffix)),
        },
    }
    _out_path(results_dir, "valid_pullback_part6_summary.json", args.output_suffix).write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
