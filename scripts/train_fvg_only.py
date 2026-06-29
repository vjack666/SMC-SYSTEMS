from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backtest.retrain_models import _collect_m15, _evaluate_walk_forward
from modules.fvg.detector import detect_fvg
from modules.fvg.ml_model import FEATURE_COLUMNS as FVG_FEATURES
from modules.fvg.ml_model import build_feature_frame as fvg_build_feature_frame
from modules.fvg.ml_model import build_labels as fvg_build_labels


def _save_fvg_model(model: RandomForestClassifier) -> str:
    model_dir = Path("modules/fvg/models")
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "fvg_v3.pkl"
    joblib.dump({"model": model, "feature_columns": FVG_FEATURES}, model_path)
    return str(model_path)


def main() -> None:
    print("Training FVG-only model...")
    m15 = _collect_m15()
    fvg_data = detect_fvg(m15.copy())
    fvg_feats = fvg_build_feature_frame(fvg_data)
    fvg_feats["target"] = fvg_build_labels(fvg_feats)

    clean = fvg_feats.dropna(subset=FVG_FEATURES + ["target"]).reset_index(drop=True)
    if clean.empty:
        raise RuntimeError("No training rows available for FVG-only model.")

    cv_mean, cv_std, cv_n = _evaluate_walk_forward(
        fvg_feats,
        FVG_FEATURES,
        "target",
        lambda: RandomForestClassifier(n_estimators=70, random_state=42, n_jobs=1),
    )

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=9,
        min_samples_leaf=2,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(clean[FVG_FEATURES], clean["target"].astype(int))
    model_path = _save_fvg_model(model)

    fi = pd.Series(model.feature_importances_, index=FVG_FEATURES).sort_values(ascending=False)
    feature_importance = [
        {"feature": str(feature), "importance": float(importance)}
        for feature, importance in fi.items()
    ]

    summary = {
        "module": "fvg_only",
        "n_samples": int(cv_n),
        "n_features": len(FVG_FEATURES),
        "features": list(FVG_FEATURES),
        "positive_rate": float(clean["target"].astype(int).mean()),
        "cv_mean": float(cv_mean),
        "cv_std": float(cv_std),
        "model_path": model_path,
        "feature_importance": feature_importance,
        "target_definition": "1 if directional move after FVG reaches >= 0.4*ATR within 8 bars; else 0",
    }

    out_dir = Path("results")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "fvg_only_training_summary.json"
    out_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
