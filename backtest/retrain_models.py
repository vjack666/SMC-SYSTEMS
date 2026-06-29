from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from modules.bos.detector import BosConfig, detect_bos
from modules.bos.ml_model import FEATURE_COLUMNS as BOS_FEATURES
from modules.bos.ml_model import build_training_set as bos_build_training_set
from modules.bos.ml_model import train_model as bos_train_model
from modules.choch.detector import detect_choch
from modules.choch.ml_model import FEATURE_COLUMNS as CHOCH_FEATURES
from modules.choch.ml_model import build_feature_frame as choch_build_feature_frame
from modules.choch.ml_model import build_labels as choch_build_labels
from modules.choch.ml_model import train_model as choch_train_model
from modules.fractal.fractal_detector import FractalConfig, detect_fractals
from modules.fractal.ml_model import FEATURE_COLUMNS as FRACTAL_FEATURES
from modules.fractal.ml_model import build_feature_frame as fractal_build_feature_frame
from modules.fractal.ml_model import build_labels as fractal_build_labels
from modules.fractal.ml_model import train_model as fractal_train_model
from modules.fvg.detector import detect_fvg
from modules.fvg.ml_model import FEATURE_COLUMNS as FVG_FEATURES
from modules.fvg.ml_model import build_feature_frame as fvg_build_feature_frame
from modules.fvg.ml_model import build_labels as fvg_build_labels
from modules.fvg.ml_model import train_model as fvg_train_model
from modules.indicators.ml_model import FEATURE_COLUMNS as IND_FEATURES
from modules.indicators.ml_model import build_feature_frame as ind_build_feature_frame
from modules.indicators.ml_model import build_labels as ind_build_labels
from modules.indicators.ml_model import train_model as ind_train_model
from modules.ob.detector import detect_order_blocks
from modules.ob.ml_model import FEATURE_COLUMNS as OB_FEATURES
from modules.ob.ml_model import build_feature_frame as ob_build_feature_frame
from modules.ob.ml_model import build_labels as ob_build_labels
from modules.ob.ml_model import train_model as ob_train_model
from modules.swing.ml_model import FEATURE_COLUMNS as SWING_FEATURES
from modules.swing.ml_model import build_feature_frame as swing_build_feature_frame
from modules.swing.ml_model import build_labels as swing_build_labels
from modules.swing.ml_model import train_model as swing_train_model
from modules.trend.ml_model import FEATURE_COLUMNS as TREND_FEATURES
from modules.trend.ml_model import build_feature_frame as trend_build_feature_frame
from modules.trend.ml_model import build_labels as trend_build_labels


DATA_DIR = Path("data/mt5")
RESULTS_DIR = Path("results")
SYMBOLS = ("EURUSD", "GBPUSD", "XAUUSD")


def _load(symbol: str, timeframe: str) -> pd.DataFrame:
    path = DATA_DIR / f"{symbol}_{timeframe}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing market data file: {path}")
    frame = pd.read_parquet(path).copy()
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame["symbol"] = symbol
    return frame.sort_values("time").reset_index(drop=True)


def _collect_m15() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for symbol in SYMBOLS:
        frame = _load(symbol, "M15")
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _compute_atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = frame["high"] - frame["low"]
    high_prev_close = (frame["high"] - frame["close"].shift(1)).abs()
    low_prev_close = (frame["low"] - frame["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _ema_trend(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame[["time", "close", "high", "low"]].copy().reset_index(drop=True)
    data["atr"] = _compute_atr(data, 14)
    ema_fast = data["close"].ewm(span=20, adjust=False).mean()
    ema_slow = data["close"].ewm(span=50, adjust=False).mean()
    spread = (ema_fast - ema_slow) / data["atr"].replace(0.0, np.nan)

    trend = pd.Series("RANGING", index=data.index, dtype=object)
    trend[spread > 0.01] = "BULLISH"
    trend[spread < -0.01] = "BEARISH"
    return pd.DataFrame({"time": data["time"], "trend": trend})


def _prepare_trend_frame() -> pd.DataFrame:
    per_symbol: list[pd.DataFrame] = []
    for symbol in SYMBOLS:
        d1 = _load(symbol, "D1")
        h4 = _load(symbol, "H4")
        m15 = _load(symbol, "M15")

        d1_trend = _ema_trend(d1).rename(columns={"trend": "d1_trend"})
        h4_trend = _ema_trend(h4).rename(columns={"trend": "h4_trend"})

        base = m15[["time", "open", "high", "low", "close", "tick_volume"]].copy().sort_values("time")
        base = pd.merge_asof(base, d1_trend.sort_values("time"), on="time", direction="backward")
        base = pd.merge_asof(base, h4_trend.sort_values("time"), on="time", direction="backward")

        agree = base["d1_trend"].isin(["BULLISH", "BEARISH"]) & (base["d1_trend"] == base["h4_trend"])
        macro = pd.Series(np.where(agree, base["d1_trend"], "RANGING"), index=base.index)

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


def _evaluate_walk_forward(
    data: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    model_factory: Callable[[], object],
) -> tuple[float, float, int]:
    data = data.dropna(subset=feature_cols + [target_col]).reset_index(drop=True)
    if len(data) < 500:
        raise ValueError("Not enough rows for 5-fold walk-forward CV.")

    splitter = TimeSeriesSplit(n_splits=5)
    scores: list[float] = []

    for train_idx, test_idx in splitter.split(data):
        train = data.iloc[train_idx]
        test = data.iloc[test_idx]

        y_train = train[target_col].astype(int)
        y_test = test[target_col].astype(int)
        if y_train.nunique() < 2 or y_test.nunique() < 2:
            continue

        model = model_factory()
        model.fit(train[feature_cols], y_train)

        if hasattr(model, "predict_proba"):
            prob = model.predict_proba(test[feature_cols])[:, 1]
            score = float(roc_auc_score(y_test, prob))
        else:
            pred = model.predict(test[feature_cols])
            score = float((pred == y_test).mean())

        scores.append(score)

    if not scores:
        raise ValueError("Unable to compute CV scores with available class balance.")

    return float(np.mean(scores)), float(np.std(scores)), int(len(data))


def _save_model(module: str, model: object, feature_cols: list[str]) -> str:
    model_dir = Path("modules") / module / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    target = model_dir / f"{module}_v3.pkl"
    payload = {"model": model, "feature_columns": feature_cols}
    joblib.dump(payload, target)
    return str(target)


def _dataset_stats(data: pd.DataFrame, feature_cols: list[str], target_col: str = "target") -> tuple[int, float]:
    clean = data.dropna(subset=feature_cols + [target_col]).reset_index(drop=True)
    if clean.empty:
        return 0, 0.0
    pos_rate = float(clean[target_col].astype(int).mean())
    return int(len(clean)), pos_rate


def retrain_all() -> dict[str, dict[str, float | int | str]]:
    m15 = _collect_m15()

    summaries: dict[str, dict[str, float | int | str]] = {}

    # Swing
    print("Retraining swing ML model. This may take several minutes depending on dataset size.")
    swing_data = m15.copy().reset_index(drop=True)
    swing_data["swing_high"] = swing_data["high"] >= swing_data["high"].rolling(9, center=True, min_periods=5).max()
    swing_data["swing_low"] = swing_data["low"] <= swing_data["low"].rolling(9, center=True, min_periods=5).min()
    swing_feats = swing_build_feature_frame(swing_data)
    swing_feats["target"] = swing_build_labels(swing_feats)
    swing_n_samples, swing_pos_rate = _dataset_stats(swing_feats, SWING_FEATURES)
    print(
        f"Module swing: {swing_n_samples} training samples, {len(SWING_FEATURES)} features, "
        f"class balance: {100.0 * swing_pos_rate:.2f}% positive"
    )
    swing_cv_mean, swing_cv_std, swing_n = _evaluate_walk_forward(
        swing_feats,
        SWING_FEATURES,
        "target",
        lambda: RandomForestClassifier(n_estimators=80, random_state=42, n_jobs=1),
    )
    print(f"Module swing CV: mean={swing_cv_mean:.4f} std={swing_cv_std:.4f}")
    swing_model = swing_train_model(swing_data)
    swing_path = _save_model("swing", swing_model, SWING_FEATURES)
    summaries["swing"] = {
        "n_samples": swing_n,
        "n_features": len(SWING_FEATURES),
        "cv_mean": swing_cv_mean,
        "cv_std": swing_cv_std,
        "positive_rate": swing_pos_rate,
        "confidence_floor": 0.50 if swing_cv_mean < 0.52 else 0.55,
        "model_path": swing_path,
    }

    # CHOCH
    print("Retraining choch ML model. This may take several minutes depending on dataset size.")
    choch_data = detect_choch(m15.copy())
    choch_feats = choch_build_feature_frame(choch_data)
    choch_feats["target"] = choch_build_labels(choch_feats)
    choch_n_samples, choch_pos_rate = _dataset_stats(choch_feats, CHOCH_FEATURES)
    print(
        f"Module choch: {choch_n_samples} training samples, {len(CHOCH_FEATURES)} features, "
        f"class balance: {100.0 * choch_pos_rate:.2f}% positive"
    )
    choch_cv_mean, choch_cv_std, choch_n = _evaluate_walk_forward(
        choch_feats,
        CHOCH_FEATURES,
        "target",
        lambda: RandomForestClassifier(n_estimators=80, random_state=42, n_jobs=1),
    )
    print(f"Module choch CV: mean={choch_cv_mean:.4f} std={choch_cv_std:.4f}")
    choch_model = choch_train_model(choch_data)
    choch_path = _save_model("choch", choch_model, CHOCH_FEATURES)
    summaries["choch"] = {
        "n_samples": choch_n,
        "n_features": len(CHOCH_FEATURES),
        "cv_mean": choch_cv_mean,
        "cv_std": choch_cv_std,
        "positive_rate": choch_pos_rate,
        "confidence_floor": 0.50 if choch_cv_mean < 0.52 else 0.55,
        "model_path": choch_path,
    }

    # FVG
    print("Retraining fvg ML model. This may take several minutes depending on dataset size.")
    fvg_data = detect_fvg(m15.copy())
    fvg_feats = fvg_build_feature_frame(fvg_data)
    fvg_feats["target"] = fvg_build_labels(fvg_feats)
    fvg_n_samples, fvg_pos_rate = _dataset_stats(fvg_feats, FVG_FEATURES)
    print(
        f"Module fvg: {fvg_n_samples} training samples, {len(FVG_FEATURES)} features, "
        f"class balance: {100.0 * fvg_pos_rate:.2f}% positive"
    )
    fvg_cv_mean, fvg_cv_std, fvg_n = _evaluate_walk_forward(
        fvg_feats,
        FVG_FEATURES,
        "target",
        lambda: RandomForestClassifier(n_estimators=70, random_state=42, n_jobs=1),
    )
    print(f"Module fvg CV: mean={fvg_cv_mean:.4f} std={fvg_cv_std:.4f}")
    fvg_model = fvg_train_model(fvg_data)
    fvg_path = _save_model("fvg", fvg_model, FVG_FEATURES)
    summaries["fvg"] = {
        "n_samples": fvg_n,
        "n_features": len(FVG_FEATURES),
        "cv_mean": fvg_cv_mean,
        "cv_std": fvg_cv_std,
        "positive_rate": fvg_pos_rate,
        "confidence_floor": 0.50 if fvg_cv_mean < 0.52 else 0.55,
        "model_path": fvg_path,
    }

    # OB
    print("Retraining ob ML model. This may take several minutes depending on dataset size.")
    ob_data = detect_order_blocks(m15.copy())
    ob_feats = ob_build_feature_frame(ob_data)
    ob_feats["target"] = ob_build_labels(ob_feats)
    ob_n_samples, ob_pos_rate = _dataset_stats(ob_feats, OB_FEATURES)
    print(
        f"Module ob: {ob_n_samples} training samples, {len(OB_FEATURES)} features, "
        f"class balance: {100.0 * ob_pos_rate:.2f}% positive"
    )
    ob_cv_mean, ob_cv_std, ob_n = _evaluate_walk_forward(
        ob_feats,
        OB_FEATURES,
        "target",
        lambda: RandomForestClassifier(n_estimators=70, random_state=42, n_jobs=1),
    )
    print(f"Module ob CV: mean={ob_cv_mean:.4f} std={ob_cv_std:.4f}")
    ob_model = ob_train_model(ob_data)
    ob_path = _save_model("ob", ob_model, OB_FEATURES)
    summaries["ob"] = {
        "n_samples": ob_n,
        "n_features": len(OB_FEATURES),
        "cv_mean": ob_cv_mean,
        "cv_std": ob_cv_std,
        "positive_rate": ob_pos_rate,
        "confidence_floor": 0.50 if ob_cv_mean < 0.52 else 0.55,
        "model_path": ob_path,
    }

    # Fractal
    print("Retraining fractal ML model. This may take several minutes depending on dataset size.")
    fractal_data = detect_fractals(m15.copy(), FractalConfig(window=2))
    fractal_feats = fractal_build_feature_frame(fractal_data)
    fractal_feats["target"] = fractal_build_labels(fractal_feats)
    fractal_n_samples, fractal_pos_rate = _dataset_stats(fractal_feats, FRACTAL_FEATURES)
    print(
        f"Module fractal: {fractal_n_samples} training samples, {len(FRACTAL_FEATURES)} features, "
        f"class balance: {100.0 * fractal_pos_rate:.2f}% positive"
    )
    fractal_cv_mean, fractal_cv_std, fractal_n = _evaluate_walk_forward(
        fractal_feats,
        FRACTAL_FEATURES,
        "target",
        lambda: RandomForestClassifier(n_estimators=70, random_state=42, n_jobs=1),
    )
    print(f"Module fractal CV: mean={fractal_cv_mean:.4f} std={fractal_cv_std:.4f}")
    fractal_model = fractal_train_model(fractal_data)
    fractal_path = _save_model("fractal", fractal_model, FRACTAL_FEATURES)
    summaries["fractal"] = {
        "n_samples": fractal_n,
        "n_features": len(FRACTAL_FEATURES),
        "cv_mean": fractal_cv_mean,
        "cv_std": fractal_cv_std,
        "positive_rate": fractal_pos_rate,
        "confidence_floor": 0.50 if fractal_cv_mean < 0.52 else 0.55,
        "model_path": fractal_path,
    }

    # Indicators
    print("Retraining indicators ML model. This may take several minutes depending on dataset size.")
    ind_feats = ind_build_feature_frame(m15.copy())
    ind_feats["target"] = ind_build_labels(ind_feats)
    ind_n_samples, ind_pos_rate = _dataset_stats(ind_feats, IND_FEATURES)
    print(
        f"Module indicators: {ind_n_samples} training samples, {len(IND_FEATURES)} features, "
        f"class balance: {100.0 * ind_pos_rate:.2f}% positive"
    )
    ind_cv_mean, ind_cv_std, ind_n = _evaluate_walk_forward(
        ind_feats,
        IND_FEATURES,
        "target",
        lambda: RandomForestClassifier(n_estimators=80, random_state=42, n_jobs=1),
    )
    print(f"Module indicators CV: mean={ind_cv_mean:.4f} std={ind_cv_std:.4f}")
    ind_model = ind_train_model(m15.copy())
    ind_path = _save_model("indicators", ind_model, IND_FEATURES)
    summaries["indicators"] = {
        "n_samples": ind_n,
        "n_features": len(IND_FEATURES),
        "cv_mean": ind_cv_mean,
        "cv_std": ind_cv_std,
        "positive_rate": ind_pos_rate,
        "confidence_floor": 0.50 if ind_cv_mean < 0.52 else 0.55,
        "model_path": ind_path,
    }

    # BOS
    print("Retraining bos ML model. This may take several minutes depending on dataset size.")
    bos_base = detect_bos(m15.copy(), BosConfig(followthrough_bars=18))
    bos_feats = bos_build_training_set(bos_base)
    bos_events = bos_feats.loc[bos_feats["bos_direction"] != 0].copy()
    bos_n_samples, bos_pos_rate = _dataset_stats(bos_events, BOS_FEATURES)
    print(
        f"Module bos: {bos_n_samples} training samples, {len(BOS_FEATURES)} features, "
        f"class balance: {100.0 * bos_pos_rate:.2f}% positive"
    )
    bos_cv_mean, bos_cv_std, bos_n = _evaluate_walk_forward(
        bos_events,
        BOS_FEATURES,
        "target",
        lambda: GradientBoostingClassifier(random_state=42),
    )
    print(f"Module bos CV: mean={bos_cv_mean:.4f} std={bos_cv_std:.4f}")
    bos_model = bos_train_model(bos_feats)
    bos_path = _save_model("bos", bos_model, BOS_FEATURES)
    summaries["bos"] = {
        "n_samples": bos_n,
        "n_features": len(BOS_FEATURES),
        "cv_mean": bos_cv_mean,
        "cv_std": bos_cv_std,
        "positive_rate": bos_pos_rate,
        "confidence_floor": 0.50 if bos_cv_mean < 0.52 else 0.55,
        "model_path": bos_path,
    }

    # Trend
    print("Retraining trend ML model. This may take several minutes depending on dataset size.")
    trend_feats = _prepare_trend_frame()
    trend_n_samples, trend_pos_rate = _dataset_stats(trend_feats, TREND_FEATURES)
    print(
        f"Module trend: {trend_n_samples} training samples, {len(TREND_FEATURES)} features, "
        f"class balance: {100.0 * trend_pos_rate:.2f}% positive"
    )
    trend_cv_mean, trend_cv_std, trend_n = _evaluate_walk_forward(
        trend_feats,
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
    print(f"Module trend CV: mean={trend_cv_mean:.4f} std={trend_cv_std:.4f}")
    trend_data = trend_feats.dropna(subset=TREND_FEATURES + ["target"])
    trend_model = RandomForestClassifier(
        n_estimators=60,
        max_depth=10,
        min_samples_leaf=2,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=1,
    )
    trend_model.fit(trend_data[TREND_FEATURES], trend_data["target"].astype(int))
    trend_path = _save_model("trend", trend_model, TREND_FEATURES)
    summaries["trend"] = {
        "n_samples": trend_n,
        "n_features": len(TREND_FEATURES),
        "cv_mean": trend_cv_mean,
        "cv_std": trend_cv_std,
        "positive_rate": trend_pos_rate,
        "confidence_floor": 0.50 if trend_cv_mean < 0.52 else 0.55,
        "model_path": trend_path,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "training_summary.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    return summaries


def main() -> None:
    summaries = retrain_all()
    for name, summary in summaries.items():
        print(
            f"{name}: n_samples={summary['n_samples']}, n_features={summary['n_features']}, "
            f"CV={float(summary['cv_mean']):.4f} ± {float(summary['cv_std']):.4f}, model={summary['model_path']}"
        )


if __name__ == "__main__":
    main()
