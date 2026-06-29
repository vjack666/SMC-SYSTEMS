from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit


def run_walk_forward_probabilities(
    frame: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    n_splits: int = 5,
) -> tuple[pd.Series, dict[str, Any], RandomForestClassifier | None]:
    data = frame.copy().reset_index(drop=True)
    probs = pd.Series(np.nan, index=data.index, dtype=float)

    clean = data.dropna(subset=feature_cols + [target_col]).reset_index()
    if len(clean) < max(200, n_splits * 40):
        return probs, {"n_folds": 0, "auc_mean": float("nan"), "auc_std": float("nan")}, None

    splitter = TimeSeriesSplit(n_splits=n_splits)
    aucs: list[float] = []

    for train_idx, test_idx in splitter.split(clean):
        train = clean.iloc[train_idx]
        test = clean.iloc[test_idx]

        x_train = train[feature_cols]
        y_train = train[target_col].astype(int)
        x_test = test[feature_cols]
        y_test = test[target_col].astype(int)

        if y_train.nunique() < 2 or y_test.nunique() < 2:
            continue

        model = RandomForestClassifier(
            n_estimators=120,
            max_depth=8,
            min_samples_leaf=3,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        )
        model.fit(x_train, y_train)
        p = model.predict_proba(x_test)[:, 1]
        probs.loc[test["index"].to_numpy()] = p

        order = np.argsort(p)
        ranks = np.empty_like(order)
        ranks[order] = np.arange(len(order))
        auc = (ranks[y_test.to_numpy() == 1].mean() - ranks[y_test.to_numpy() == 0].mean()) / max(1, len(y_test))
        aucs.append(float(auc))

    final_model: RandomForestClassifier | None = None
    y_all = clean[target_col].astype(int)
    if y_all.nunique() >= 2:
        final_model = RandomForestClassifier(
            n_estimators=160,
            max_depth=9,
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        )
        final_model.fit(clean[feature_cols], y_all)

    report = {
        "n_folds": len(aucs),
        "auc_mean": float(np.mean(aucs)) if aucs else float("nan"),
        "auc_std": float(np.std(aucs)) if aucs else float("nan"),
        "samples": int(len(clean)),
    }
    return probs, report, final_model


def check_no_lookahead(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {"ok": True, "violations": 0}

    entry = pd.to_datetime(trades["entry_time"], utc=True, errors="coerce")
    exit_ = pd.to_datetime(trades["exit_time"], utc=True, errors="coerce")
    create = pd.to_datetime(trades.get("create_time", trades["entry_time"]), utc=True, errors="coerce")

    violations = int(((entry < create) | (exit_ < entry)).sum())
    return {"ok": violations == 0, "violations": violations}


def check_reproducibility(paths: list[Path]) -> dict[str, Any]:
    digest_map: dict[str, str] = {}
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        digest_map[str(path)] = h
    return {"files": len(digest_map), "sha256": digest_map}


def write_validation_snapshot(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
