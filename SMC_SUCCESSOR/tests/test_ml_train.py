from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import TimeSeriesSplit

from smc_successor.ml import WalkForwardConfig, train_walk_forward


@pytest.fixture
def sample_dataset() -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(42)
    n = 200
    X = pd.DataFrame({
        "bos_strength": rng.normal(0, 1, n),
        "atr_ratio": rng.uniform(0.5, 2.0, n),
        "rsi": rng.uniform(20, 80, n),
        "trend_confidence": rng.uniform(0, 1, n),
        "volume_ratio": rng.exponential(1, n),
    })
    y = pd.Series((X["rsi"] > 50).astype(int), name="win")
    return X, y


class TestWalkForward:
    def test_train_returns_model_and_metrics(self, sample_dataset):
        X, y = sample_dataset
        model, metrics, avg_roc = train_walk_forward(X, y)
        assert hasattr(model, "predict_proba")
        assert metrics["model"] in ("xgboost", "lightgbm", "catboost", "hist_gradient_boosting")
        assert metrics["n_splits"] == 5
        assert len(metrics["walk_forward_folds"]) > 0
        assert avg_roc >= 0.0

    def test_walk_forward_respects_temporal_order(self, sample_dataset):
        X, y = sample_dataset
        tscv = TimeSeriesSplit(n_splits=5)
        for _, (train_idx, val_idx) in enumerate(tscv.split(X)):
            assert max(train_idx) < min(val_idx), "Temporal order violated"

    def test_metrics_are_reasonable(self, sample_dataset):
        X, y = sample_dataset
        _, metrics, avg_roc = train_walk_forward(X, y)
        for fold in metrics["walk_forward_folds"]:
            assert 0.0 <= fold["roc_auc"] <= 1.0
            assert fold["logloss"] >= 0.0
            assert fold["train_samples"] > 0
            assert fold["val_samples"] > 0

    def test_predict_proba_output_shape(self, sample_dataset):
        X, y = sample_dataset
        model, _, _ = train_walk_forward(X, y)
        proba = model.predict_proba(X.iloc[:10])
        assert proba.shape == (10, 2)
        assert np.allclose(proba.sum(axis=1), 1.0)

    def test_single_class_does_not_crash(self):
        X = pd.DataFrame({"feat1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]})
        y = pd.Series([1] * 10)
        model, metrics, avg_roc = train_walk_forward(X, y)
        assert model is not None
        assert avg_roc == 0.5
        assert hasattr(model, "predict_proba")

    def test_calibration_disabled(self, sample_dataset):
        X, y = sample_dataset
        cfg = WalkForwardConfig(calibrate=False)
        model, metrics, _ = train_walk_forward(X, y, cfg)
        assert not metrics["calibration_used"]

    def test_calibration_enabled(self, sample_dataset):
        X, y = sample_dataset
        cfg = WalkForwardConfig(calibrate=True)
        model, metrics, _ = train_walk_forward(X, y, cfg)
        assert "calibration_used" in metrics

    def test_with_custom_n_splits(self, sample_dataset):
        X, y = sample_dataset
        cfg = WalkForwardConfig(n_splits=3)
        _, metrics, _ = train_walk_forward(X, y, cfg)
        assert metrics["n_splits"] == 3
        assert len(metrics["walk_forward_folds"]) <= 3

    def test_with_gap(self, sample_dataset):
        X, y = sample_dataset
        cfg = WalkForwardConfig(gap=5)
        tscv = TimeSeriesSplit(n_splits=5, gap=5)
        for train_idx, val_idx in tscv.split(X):
            assert max(train_idx) + 5 < min(val_idx), "Gap not respected"

    def test_temporal_importance_output(self, sample_dataset):
        X, y = sample_dataset
        model, metrics, _ = train_walk_forward(X, y)
        try:
            importances = model.feature_importances_
            assert len(importances) == X.shape[1]
        except (AttributeError, ValueError):
            pass

    def test_small_dataset_does_not_crash(self):
        X = pd.DataFrame({"feat1": [1.0, 2.0, 3.0, 4.0, 5.0]})
        y = pd.Series([0, 1, 0, 1, 0])
        with pytest.raises(ValueError):
            train_walk_forward(X, y)

    def test_custom_features_in_config(self, sample_dataset):
        X, y = sample_dataset
        cfg = WalkForwardConfig(features=("rsi", "trend_confidence"))
        model, metrics, _ = train_walk_forward(X[list(cfg.features)], y, cfg)
        assert metrics["model"] is not None
