from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backtest.retrain_models import SYMBOLS, _evaluate_walk_forward, _load
from modules.trend.ml_model import FEATURE_COLUMNS as TREND_FEATURES
from modules.trend.ml_model import build_feature_frame as trend_build_feature_frame
from modules.trend.ml_model import build_labels as trend_build_labels


def compute_atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = frame["high"] - frame["low"]
    high_prev_close = (frame["high"] - frame["close"].shift(1)).abs()
    low_prev_close = (frame["low"] - frame["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def ema_trend(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame[["time", "close", "high", "low"]].copy().reset_index(drop=True)
    data["atr"] = compute_atr(data, 14)
    ema_fast = data["close"].ewm(span=20, adjust=False).mean()
    ema_slow = data["close"].ewm(span=50, adjust=False).mean()
    spread = (ema_fast - ema_slow) / data["atr"].replace(0.0, np.nan)

    trend = pd.Series("RANGING", index=data.index, dtype=object)
    trend[spread > 0.01] = "BULLISH"
    trend[spread < -0.01] = "BEARISH"
    return pd.DataFrame({"time": data["time"], "trend": trend})


def prepare_trend_frame(htf_tf: str, ltf_tf: str) -> pd.DataFrame:
    per_symbol: list[pd.DataFrame] = []
    for symbol in SYMBOLS:
        htf = _load(symbol, htf_tf)
        ltf = _load(symbol, ltf_tf)

        htf_trend = ema_trend(htf).rename(columns={"trend": "htf_trend"})
        ltf_trend = ema_trend(ltf).rename(columns={"trend": "ltf_trend"})

        base = ltf[["time", "open", "high", "low", "close", "tick_volume"]].copy().sort_values("time")
        base = pd.merge_asof(base, htf_trend.sort_values("time"), on="time", direction="backward")
        base = pd.merge_asof(base, ltf_trend.sort_values("time"), on="time", direction="backward")

        agree = base["htf_trend"].isin(["BULLISH", "BEARISH"]) & (base["htf_trend"] == base["ltf_trend"])
        macro = pd.Series(np.where(agree, base["htf_trend"], "RANGING"), index=base.index)

        ema_fast = base["close"].ewm(span=20, adjust=False).mean()
        ema_slow = base["close"].ewm(span=50, adjust=False).mean()

        micro = pd.Series(["UNCLEAR"] * len(base), index=base.index)
        micro[(macro == "BULLISH") & (ema_fast > ema_slow)] = "CONTINUATION"
        micro[(macro == "BULLISH") & (ema_fast <= ema_slow)] = "PULLBACK"
        micro[(macro == "BEARISH") & (ema_fast < ema_slow)] = "CONTINUATION"
        micro[(macro == "BEARISH") & (ema_fast >= ema_slow)] = "PULLBACK"

        agreement = pd.Series(agree.astype(float), index=base.index)
        consecutive = pd.Series(0.0, index=base.index)
        run = 0
        prev = "RANGING"
        for idx, value in enumerate(macro.tolist()):
            if value in ("BULLISH", "BEARISH") and value == prev:
                run += 1
            elif value in ("BULLISH", "BEARISH"):
                run = 1
            else:
                run = 0
            consecutive.iloc[idx] = float(run)
            prev = value

        features = trend_build_feature_frame(base, macro, micro, agreement, consecutive)
        features["symbol"] = symbol
        per_symbol.append(features)

    data = pd.concat(per_symbol, ignore_index=True)
    data["target"] = trend_build_labels(data)
    return data


def train_variant(htf_tf: str, ltf_tf: str) -> dict[str, object]:
    print(f"Training variant {htf_tf}->{ltf_tf} ...", flush=True)
    data = prepare_trend_frame(htf_tf, ltf_tf)
    clean = data.dropna(subset=TREND_FEATURES + ["target"]).reset_index(drop=True)

    cv_mean, cv_std, cv_n = _evaluate_walk_forward(
        data,
        TREND_FEATURES,
        "target",
        lambda: RandomForestClassifier(
            n_estimators=60,
            max_depth=10,
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=1,
        ),
    )

    model = RandomForestClassifier(
        n_estimators=60,
        max_depth=10,
        min_samples_leaf=2,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=1,
    )
    model.fit(clean[TREND_FEATURES], clean["target"].astype(int))

    model_dir = Path("modules/trend/models")
    model_dir.mkdir(parents=True, exist_ok=True)
    variant_name = f"trend_{htf_tf.lower()}_{ltf_tf.lower()}_v3"
    model_path = model_dir / f"{variant_name}.pkl"
    joblib.dump({"model": model, "feature_columns": TREND_FEATURES}, model_path)

    summary = {
        "module": "trend_only_lower_tf",
        "variant": f"{htf_tf}->{ltf_tf}",
        "n_samples": int(len(clean)),
        "n_features": len(TREND_FEATURES),
        "positive_rate": float(clean["target"].astype(int).mean()),
        "cv_mean": float(cv_mean),
        "cv_std": float(cv_std),
        "model_path": str(model_path),
    }
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def main() -> None:
    variants = [("H4", "H1"), ("H1", "M15")]
    summaries: list[dict[str, object]] = []

    Path("results").mkdir(parents=True, exist_ok=True)
    progress_path = Path("results/trend_lower_tf_training_progress.json")

    for htf, ltf in variants:
        try:
            summary = train_variant(htf, ltf)
            summaries.append(summary)
        except Exception as exc:  # noqa: BLE001
            err = {
                "module": "trend_only_lower_tf",
                "variant": f"{htf}->{ltf}",
                "error": str(exc),
            }
            summaries.append(err)
            print(json.dumps(err, indent=2), flush=True)
        progress_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")

    out_path = Path("results/trend_lower_tf_training_summary.json")
    out_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print("DONE trend lower TF training", flush=True)


if __name__ == "__main__":
    main()
