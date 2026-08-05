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


SYMBOLS = ("EURUSD", "GBPUSD", "XAUUSD")
HORIZONS = (1, 3, 5, 10, 20)


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

    for h in HORIZONS:
        future_close = pd.to_numeric(out["close"].shift(-h), errors="coerce").to_numpy(dtype=float)
        raw_ret = (future_close - close) / close
        signed_ret = sign * (future_close - close) / atr

        max_future = _future_window_max(high, h)
        min_future = _future_window_min(low, h)

        mfe_bull = (max_future - close) / atr
        mae_bull = (min_future - close) / atr
        mfe_bear = (close - min_future) / atr
        mae_bear = (close - max_future) / atr

        mfe = np.where(sign > 0, mfe_bull, np.where(sign < 0, mfe_bear, np.nan))
        mae = np.where(sign > 0, mae_bull, np.where(sign < 0, mae_bear, np.nan))

        continuation = (signed_ret > 0).astype(float)
        continuation[sign == 0] = np.nan

        bos_break_bull = min_future < swing_low_ref
        bos_break_bear = max_future > swing_high_ref
        post_break = np.where(sign > 0, bos_break_bull, np.where(sign < 0, bos_break_bear, np.nan))

        out[f"raw_return_{h}"] = raw_ret
        out[f"signed_return_{h}"] = signed_ret
        out[f"mfe_r_{h}"] = mfe
        out[f"mae_r_{h}"] = mae
        out[f"continuity_{h}"] = continuation
        out[f"post_structure_break_{h}"] = post_break

    return out


def _compare_groups(df: pd.DataFrame, left_mask: pd.Series, right_mask: pd.Series, label_left: str, label_right: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    left = df[left_mask]
    right = df[right_mask]

    for h in HORIZONS:
        for metric in (f"signed_return_{h}", f"raw_return_{h}", f"mfe_r_{h}", f"mae_r_{h}", f"continuity_{h}", f"post_structure_break_{h}"):
            l = pd.to_numeric(left[metric], errors="coerce")
            r = pd.to_numeric(right[metric], errors="coerce")
            rows.append(
                {
                    "horizon": h,
                    "metric": metric,
                    f"{label_left}_mean": float(l.mean()),
                    f"{label_left}_median": float(l.median()),
                    f"{label_right}_mean": float(r.mean()),
                    f"{label_right}_median": float(r.median()),
                    "delta_mean": float(l.mean() - r.mean()),
                    "delta_median": float(l.median() - r.median()),
                    f"{label_left}_n": int(l.notna().sum()),
                    f"{label_right}_n": int(r.notna().sum()),
                }
            )

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rigorous pullback audit")
    parser.add_argument("--no-rsi", action="store_true", help="Run pullback view without RSI in classification filters")
    parser.add_argument("--output-suffix", default="", help="Suffix appended to output files")
    args = parser.parse_args()

    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)

    frames: list[pd.DataFrame] = []
    for symbol in SYMBOLS:
        view = build_pullback_view(symbol=symbol, timeframe="M15", data_dir=Path("data/mt5"), use_rsi=not args.no_rsi)
        view["symbol"] = symbol
        frames.append(view)

    df = pd.concat(frames, ignore_index=True)
    df = _add_forward_metrics(df)

    df["is_valid"] = df["pullback_ready"].astype(bool)
    df["is_invalid"] = df["pullback_state"].isin(["BULLISH_PULLBACK_INVALID", "BEARISH_PULLBACK_INVALID"])
    df["is_discarded"] = ~df["is_valid"]

    # Part 1: circular-bias mapping.
    part1 = pd.DataFrame(
        [
            {"metric": "trend_alignment", "used_in_classifier": False, "direct_or_indirect": "indirect (upstream trend engine)", "evidence_strength": "weak_for_validation"},
            {"metric": "trend_score", "used_in_classifier": True, "direct_or_indirect": "direct", "evidence_strength": "none (circular)"},
            {"metric": "macro_direction", "used_in_classifier": True, "direct_or_indirect": "direct (from trend_score threshold)", "evidence_strength": "none (circular)"},
            {"metric": "trend_confidence", "used_in_classifier": True, "direct_or_indirect": "direct", "evidence_strength": "none (circular)"},
            {"metric": "regime_state", "used_in_classifier": True, "direct_or_indirect": "direct", "evidence_strength": "none (circular)"},
            {"metric": "rsi", "used_in_classifier": True, "direct_or_indirect": "direct", "evidence_strength": "none (circular)"},
            {"metric": "bos_direction", "used_in_classifier": True, "direct_or_indirect": "direct", "evidence_strength": "none (circular)"},
            {"metric": "choch_signal", "used_in_classifier": True, "direct_or_indirect": "direct", "evidence_strength": "none (circular)"},
            {"metric": "pullback_score", "used_in_classifier": False, "direct_or_indirect": "indirect (derived from classifier inputs)", "evidence_strength": "weak_for_validation"},
            {"metric": "atr_ratio", "used_in_classifier": False, "direct_or_indirect": "indirect (through trend/regime features)", "evidence_strength": "low"},
            {"metric": "pullback_depth_up_atr", "used_in_classifier": False, "direct_or_indirect": "independent_of_ready_rule", "evidence_strength": "medium"},
            {"metric": "pullback_depth_down_atr", "used_in_classifier": False, "direct_or_indirect": "independent_of_ready_rule", "evidence_strength": "medium"},
            {"metric": "signed_return_h", "used_in_classifier": False, "direct_or_indirect": "independent_post_event", "evidence_strength": "strong"},
            {"metric": "mfe_r_h", "used_in_classifier": False, "direct_or_indirect": "independent_post_event", "evidence_strength": "strong"},
            {"metric": "mae_r_h", "used_in_classifier": False, "direct_or_indirect": "independent_post_event", "evidence_strength": "strong"},
            {"metric": "continuity_h", "used_in_classifier": False, "direct_or_indirect": "independent_post_event", "evidence_strength": "strong"},
            {"metric": "post_structure_break_h", "used_in_classifier": False, "direct_or_indirect": "independent_post_event", "evidence_strength": "strong"},
        ]
    )
    part1.loc[part1["metric"] == "rsi", "used_in_classifier"] = not args.no_rsi
    part1.loc[part1["metric"] == "rsi", "direct_or_indirect"] = "direct" if not args.no_rsi else "not_used"
    part1.loc[part1["metric"] == "rsi", "evidence_strength"] = "none (circular)" if not args.no_rsi else "independent"
    part1.to_csv(_out_path(results_dir, "pullback_part1_bias_table.csv", args.output_suffix), index=False)

    # Part 3: VALID vs INVALID + VALID vs DISCARDED.
    part3_valid_invalid = _compare_groups(df, df["is_valid"], df["is_invalid"], "valid", "invalid")
    part3_valid_discarded = _compare_groups(df, df["is_valid"], df["is_discarded"], "valid", "discarded")
    part3_valid_invalid.to_csv(_out_path(results_dir, "pullback_part3_valid_vs_invalid.csv", args.output_suffix), index=False)
    part3_valid_discarded.to_csv(_out_path(results_dir, "pullback_part3_valid_vs_discarded.csv", args.output_suffix), index=False)

    # Part 4: robustness by regime (BULLISH/BEARISH/RANGING via macro_direction).
    regime_rows: list[dict[str, object]] = []
    for regime in ("BULLISH", "BEARISH", "RANGING"):
        sub = df[df["macro_direction"] == regime]
        row: dict[str, object] = {
            "regime": regime,
            "n": int(len(sub)),
            "valid_rate": float(sub["is_valid"].mean()),
            "score_mean": float(pd.to_numeric(sub["pullback_score"], errors="coerce").mean()),
        }
        for h in HORIZONS:
            row[f"signed_return_{h}_mean"] = float(pd.to_numeric(sub.loc[sub["is_valid"], f"signed_return_{h}"], errors="coerce").mean())
            row[f"continuity_{h}_mean"] = float(pd.to_numeric(sub.loc[sub["is_valid"], f"continuity_{h}"], errors="coerce").mean())
        regime_rows.append(row)
    part4 = pd.DataFrame(regime_rows)
    part4.to_csv(_out_path(results_dir, "pullback_part4_regime.csv", args.output_suffix), index=False)

    # Part 5: robustness by symbol.
    symbol_rows: list[dict[str, object]] = []
    for symbol in SYMBOLS:
        sub = df[df["symbol"] == symbol]
        row = {
            "symbol": symbol,
            "n": int(len(sub)),
            "valid_n": int(sub["is_valid"].sum()),
            "valid_rate": float(sub["is_valid"].mean()),
            "score_mean": float(pd.to_numeric(sub.loc[sub["is_valid"], "pullback_score"], errors="coerce").mean()),
        }
        for h in HORIZONS:
            row[f"signed_return_{h}_mean"] = float(pd.to_numeric(sub.loc[sub["is_valid"], f"signed_return_{h}"], errors="coerce").mean())
            row[f"continuity_{h}_mean"] = float(pd.to_numeric(sub.loc[sub["is_valid"], f"continuity_{h}"], errors="coerce").mean())
        symbol_rows.append(row)
    part5 = pd.DataFrame(symbol_rows)
    part5.to_csv(_out_path(results_dir, "pullback_part5_symbol.csv", args.output_suffix), index=False)

    # Part 6: score bins (fixed 0..100 by 10).
    bins = list(range(0, 110, 10))
    labels = [f"{i}-{i + 10}" for i in range(0, 100, 10)]
    score_series = pd.to_numeric(df["pullback_score"], errors="coerce").clip(lower=0.0, upper=100.0)
    df["score_bin"] = pd.cut(score_series, bins=bins, labels=labels, include_lowest=True, right=False)

    bin_rows: list[dict[str, object]] = []
    for b in labels:
        sub = df[df["score_bin"].astype(str) == b]
        row: dict[str, object] = {
            "score_bin": b,
            "n": int(len(sub)),
            "valid_rate": float(sub["is_valid"].mean()) if len(sub) else np.nan,
        }
        for h in HORIZONS:
            row[f"signed_return_{h}_mean"] = float(pd.to_numeric(sub[f"signed_return_{h}"], errors="coerce").mean()) if len(sub) else np.nan
            row[f"continuity_{h}_mean"] = float(pd.to_numeric(sub[f"continuity_{h}"], errors="coerce").mean()) if len(sub) else np.nan
            row[f"mfe_r_{h}_mean"] = float(pd.to_numeric(sub[f"mfe_r_{h}"], errors="coerce").mean()) if len(sub) else np.nan
        bin_rows.append(row)
    part6 = pd.DataFrame(bin_rows)
    part6.to_csv(_out_path(results_dir, "pullback_part6_score_bins.csv", args.output_suffix), index=False)

    # Optional score-bin charts.
    try:
        import matplotlib.pyplot as plt

        fig, ax1 = plt.subplots(figsize=(10, 5))
        x = np.arange(len(part6))
        ax1.bar(x - 0.2, part6["valid_rate"], width=0.4, label="valid_rate")
        ax1.set_xticks(x)
        ax1.set_xticklabels(part6["score_bin"], rotation=45)
        ax1.set_ylabel("valid_rate")

        ax2 = ax1.twinx()
        ax2.plot(x + 0.2, part6["signed_return_10_mean"], marker="o", label="signed_return_10_mean")
        ax2.set_ylabel("signed_return_10_mean")

        ax1.set_title("Pullback Score Bin vs Valid Rate and Future Return")
        fig.tight_layout()
        fig.savefig(_out_path(results_dir, "pullback_part6_score_bins.png", args.output_suffix), dpi=150)
        plt.close(fig)
    except (ImportError, ValueError, OSError):
        pass

    # Part 7: correlations with independent future outcomes.
    feature_cols = [
        "trend_score",
        "trend_confidence",
        "atr_ratio",
        "rsi",
        "pullback_depth_up_atr",
        "pullback_depth_down_atr",
        "pullback_score",
    ]
    outcome_cols = [
        "signed_return_1",
        "signed_return_3",
        "signed_return_5",
        "signed_return_10",
        "signed_return_20",
        "continuity_5",
        "continuity_10",
        "continuity_20",
        "mfe_r_5",
        "mfe_r_10",
        "mfe_r_20",
    ]

    corr_rows: list[dict[str, object]] = []
    for f in feature_cols:
        for o in outcome_cols:
            temp = df[[f, o]].copy()
            temp[f] = pd.to_numeric(temp[f], errors="coerce")
            temp[o] = pd.to_numeric(temp[o], errors="coerce")
            temp = temp.dropna()
            corr = temp[f].corr(temp[o]) if len(temp) >= 2 else np.nan
            corr_rows.append({"feature": f, "outcome": o, "pearson_corr": float(corr) if pd.notna(corr) else np.nan, "n": int(len(temp))})
    part7 = pd.DataFrame(corr_rows)
    part7.to_csv(_out_path(results_dir, "pullback_part7_correlations.csv", args.output_suffix), index=False)

    # Evidence summary.
    h_key = 10
    valid = df[df["is_valid"]]
    invalid = df[df["is_invalid"]]
    discarded = df[df["is_discarded"]]

    evidence_for = {
        "valid_vs_invalid_signed_return_10_delta_mean": float(pd.to_numeric(valid[f"signed_return_{h_key}"], errors="coerce").mean() - pd.to_numeric(invalid[f"signed_return_{h_key}"], errors="coerce").mean()),
        "valid_vs_invalid_continuity_10_delta_mean": float(pd.to_numeric(valid[f"continuity_{h_key}"], errors="coerce").mean() - pd.to_numeric(invalid[f"continuity_{h_key}"], errors="coerce").mean()),
        "valid_vs_invalid_mfe_10_delta_mean": float(pd.to_numeric(valid[f"mfe_r_{h_key}"], errors="coerce").mean() - pd.to_numeric(invalid[f"mfe_r_{h_key}"], errors="coerce").mean()),
    }

    evidence_against = {
        "circular_features_used": ["trend_score", "macro_direction", "trend_confidence", "regime_state", "rsi", "bos_direction", "choch_signal"],
        "valid_rate_global": float(df["is_valid"].mean()),
        "ranging_valid_share": float((valid["macro_direction"] == "RANGING").mean()) if len(valid) else 0.0,
        "valid_vs_discarded_signed_return_10_delta_mean": float(pd.to_numeric(valid[f"signed_return_{h_key}"], errors="coerce").mean() - pd.to_numeric(discarded[f"signed_return_{h_key}"], errors="coerce").mean()),
    }

    summary = {
        "dataset": {
            "rows": int(len(df)),
            "valid_n": int(df["is_valid"].sum()),
            "invalid_n": int(df["is_invalid"].sum()),
            "discarded_n": int(df["is_discarded"].sum()),
            "use_rsi": bool(not args.no_rsi),
        },
        "hypothesis": "VALID pullbacks represent higher-quality pullbacks with better continuation than discarded pullbacks.",
        "evidence_for": evidence_for,
        "evidence_against": evidence_against,
        "confidence_level": "medium",
        "output_files": {
            "part1": str(_out_path(results_dir, "pullback_part1_bias_table.csv", args.output_suffix)),
            "part3_valid_vs_invalid": str(_out_path(results_dir, "pullback_part3_valid_vs_invalid.csv", args.output_suffix)),
            "part3_valid_vs_discarded": str(_out_path(results_dir, "pullback_part3_valid_vs_discarded.csv", args.output_suffix)),
            "part4": str(_out_path(results_dir, "pullback_part4_regime.csv", args.output_suffix)),
            "part5": str(_out_path(results_dir, "pullback_part5_symbol.csv", args.output_suffix)),
            "part6": str(_out_path(results_dir, "pullback_part6_score_bins.csv", args.output_suffix)),
            "part6_plot": str(_out_path(results_dir, "pullback_part6_score_bins.png", args.output_suffix)),
            "part7": str(_out_path(results_dir, "pullback_part7_correlations.csv", args.output_suffix)),
        },
    }

    _out_path(results_dir, "pullback_rigorous_audit_summary.json", args.output_suffix).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
