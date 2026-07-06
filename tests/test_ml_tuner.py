from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import make_classification

from ml.tuner import TuningConfig, _xgb_params, objective, tune_hyperparameters, train_with_best_params


class TestTuningConfig:
    def test_default_values(self):
        cfg = TuningConfig()
        assert cfg.n_trials == 50
        assert cfg.n_splits == 5
        assert cfg.random_state == 42
        assert cfg.study_name == "smc_xgb_tuning"
        assert cfg.direction == "maximize"
        assert cfg.metrics == ["roc_auc", "profit_factor", "expectancy"]
        assert cfg.weights == [0.4, 0.3, 0.3]

    def test_custom_values(self):
        cfg = TuningConfig(n_trials=100, direction="maximize", metrics=["roc_auc", "logloss"], weights=[0.6, 0.4])
        assert cfg.n_trials == 100
        assert cfg.direction == "maximize"
        assert cfg.metrics == ["roc_auc", "logloss"]
        assert cfg.weights == [0.6, 0.4]

    def test_invalid_weights_length(self):
        with pytest.raises(ValueError):
            TuningConfig(metrics=["roc_auc", "profit_factor"], weights=[0.5])

    def test_invalid_weights_sum(self):
        with pytest.raises(ValueError):
            TuningConfig(metrics=["roc_auc", "profit_factor"], weights=[0.5, 0.3])


class TestXgbParams:
    def test_returns_dict(self):
        trial = MagicMock()
        trial.suggest_int.return_value = 220
        trial.suggest_float.return_value = 0.1

        params = _xgb_params(trial)

        assert isinstance(params, dict)
        assert "n_estimators" in params
        assert "max_depth" in params
        assert "learning_rate" in params
        assert params["n_estimators"] == 220
        assert params["max_depth"] == 220
        assert params["learning_rate"] == 0.1
        assert params["random_state"] == 42
        assert params["objective"] == "binary:logistic"

    def test_calls_suggest_methods(self):
        trial = MagicMock()
        _xgb_params(trial)

        assert trial.suggest_int.call_count >= 3
        assert trial.suggest_float.call_count >= 5


class TestObjective:
    def test_returns_float(self):
        X, y = make_classification(n_samples=100, n_features=2, n_informative=2, n_redundant=0, random_state=42)
        X = pd.DataFrame(X, columns=["feat_a", "feat_b"])
        y = pd.Series(y, name="win")

        from ml.train import _build_feature_pipeline

        preprocess = _build_feature_pipeline(X)
        cfg = TuningConfig(n_splits=2, metrics=["roc_auc"], weights=[1.0])

        trial = MagicMock()
        trial.suggest_int.return_value = 100
        trial.suggest_float.return_value = 0.1

        score = objective(trial, X, y, preprocess, cfg)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_multi_objective_with_pnl(self):
        """Test objective with multiple metrics and PnL data."""
        X, y = make_classification(n_samples=200, n_features=2, n_informative=2, n_redundant=0, random_state=42)
        X = pd.DataFrame(X, columns=["feat_a", "feat_b"])
        y = pd.Series(y, name="win")
        pnl_r = pd.Series(np.random.normal(0, 1, 200))

        from ml.train import _build_feature_pipeline
        import optuna

        preprocess = _build_feature_pipeline(X)
        cfg = TuningConfig(n_splits=2, metrics=["roc_auc", "profit_factor", "expectancy"], weights=[0.4, 0.3, 0.3])

        study = optuna.create_study(direction="maximize")
        trial = study.ask()
        trial.suggest_int = MagicMock(return_value=100)
        trial.suggest_float = MagicMock(return_value=0.1)

        score = objective(trial, X, y, preprocess, cfg, pnl_r=pnl_r)
        assert isinstance(score, float)
        # composite score should be set in user_attrs
        assert "composite_score" in trial.user_attrs
        assert "metrics" in trial.user_attrs
        metrics = trial.user_attrs["metrics"]
        assert "roc_auc" in metrics
        assert "profit_factor" in metrics
        assert "expectancy" in metrics


class TestTuneHyperparameters:
    def test_runs_with_tiny_dataset(self):
        X, y = make_classification(n_samples=100, n_features=2, n_informative=2, n_redundant=0, random_state=42)
        X = pd.DataFrame(X, columns=["feat_a", "feat_b"])
        y = pd.Series(y, name="win")

        cfg = TuningConfig(n_trials=2, n_splits=2, random_state=42, metrics=["roc_auc"], weights=[1.0])
        best_params, best_value = tune_hyperparameters(X, y, cfg)

        assert isinstance(best_params, dict)
        assert isinstance(best_value, float)
        assert "n_estimators" in best_params
        assert best_value > 0.0

    def test_runs_with_pnl_data(self):
        """Test tune_hyperparameters with PnL data for trading metrics."""
        X, y = make_classification(n_samples=100, n_features=2, n_informative=2, n_redundant=0, random_state=42)
        X = pd.DataFrame(X, columns=["feat_a", "feat_b"])
        y = pd.Series(y, name="win")
        pnl_r = pd.Series(np.random.normal(0, 1, 100))

        cfg = TuningConfig(
            n_trials=2,
            n_splits=2,
            random_state=42,
            metrics=["roc_auc", "profit_factor", "expectancy"],
            weights=[0.4, 0.3, 0.3],
        )
        best_params, best_value = tune_hyperparameters(X, y, cfg, pnl_r=pnl_r)

        assert isinstance(best_params, dict)
        assert isinstance(best_value, float)
        assert "n_estimators" in best_params


class TestTrainWithBestParams:
    def test_trains_with_params(self):
        X, y = make_classification(n_samples=100, n_features=2, n_informative=2, n_redundant=0, random_state=42)
        X = pd.DataFrame(X, columns=["feat_a", "feat_b"])
        y = pd.Series(y, name="win")

        best_params = {
            "n_estimators": 100,
            "max_depth": 4,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 1,
            "gamma": 0.0,
            "reg_alpha": 0.0,
            "reg_lambda": 1.0,
            "random_state": 42,
            "objective": "binary:logistic",
        }

        model, metrics = train_with_best_params(X, y, best_params, calibrate=False)

        assert hasattr(model, "predict_proba")
        assert metrics["calibration_used"] is False
        assert metrics["model"] == "xgboost_tuned"