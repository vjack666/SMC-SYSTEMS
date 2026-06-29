from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from smc_successor.ml.trainer import (
    FEATURES_ML_V3,
    chronological_train_test_split,
    compute_feature_importance,
    evaluate_trade_metrics,
    find_optimal_threshold,
    load_dataset,
    load_model,
    save_model,
    train_model,
)
from smc_successor.ml.trainer import ModelMetadata

DATA_DIR = Path("data/ml")
EURUSD_V3 = DATA_DIR / "EURUSD" / "v3_EURUSD.parquet"
MODEL_PATH = Path("models/quality_filter.pkl")

pytestmark = pytest.mark.skipif(
    not EURUSD_V3.exists(),
    reason="v3 EURUSD parquet dataset required",
)


class TestLoadDataset:
    def test_loads_parquet(self) -> None:
        X, y, feature_names, schema_version = load_dataset(EURUSD_V3, FEATURES_ML_V3)
        assert len(X) > 0
        assert len(y) > 0
        assert len(feature_names) > 0
        assert "v3" in schema_version

    def test_target_is_binary(self) -> None:
        X, y, _, _ = load_dataset(EURUSD_V3, FEATURES_ML_V3)
        assert set(y.unique()).issubset({0, 1})

    def test_no_future_leakage(self) -> None:
        X, y, feature_names, _ = load_dataset(EURUSD_V3, FEATURES_ML_V3)
        leakage = [c for c in ("pnl_r", "win", "future_return",
                                "max_favorable_excursion", "max_adverse_excursion",
                                "exit_reason") if c in X.columns]
        assert len(leakage) == 0, f"Leakage columns found in features: {leakage}"

    def test_all_expected_features_present(self) -> None:
        X, y, feature_names, _ = load_dataset(EURUSD_V3, FEATURES_ML_V3)
        expected_subset = [
            "bos_detected", "fvg_fill_status", "displacement_magnitude",
            "premium_discount_zone", "ote_long_min",
            "agent_wyckoff_spring", "agent_decision_confidence",
        ]
        for col in expected_subset:
            assert col in X.columns, f"Expected feature not found: {col}"


class TestChronologicalSplit:
    def test_preserves_temporal_order(self) -> None:
        X = pd.DataFrame({"val": range(100)})
        y = pd.Series([0, 1] * 50)
        X_train, X_test, X_val, y_train, y_test, y_val = chronological_train_test_split(
            X, y, test_size=0.2, val_size=0.0
        )
        assert len(X_train) == 80
        assert len(X_test) == 20
        assert X_train["val"].iloc[-1] < X_test["val"].iloc[0]

    def test_no_shuffle_by_default(self) -> None:
        X = pd.DataFrame({"order": range(50)})
        y = pd.Series([0] * 25 + [1] * 25)
        X_train, X_test, _, y_train, y_test, _ = chronological_train_test_split(
            X, y, test_size=0.3
        )
        assert list(X_train["order"]) == list(range(35))
        assert list(X_test["order"]) == list(range(35, 50))

    def test_with_validation_set(self) -> None:
        X = pd.DataFrame({"val": range(100)})
        y = pd.Series(range(100))
        X_train, X_test, X_val, _, _, _ = chronological_train_test_split(
            X, y, test_size=0.2, val_size=0.1
        )
        assert len(X_train) == 70
        assert len(X_test) == 20
        assert len(X_val) == 10


class TestTrainModel:
    def test_trains_without_error(self) -> None:
        X = pd.DataFrame({
            "fvg_detected": np.random.randint(0, 2, 20),
            "atr": np.random.rand(20) * 0.01,
            "rsi": np.random.rand(20) * 100,
            "volume_ratio": np.random.rand(20),
        })
        y = pd.Series(np.random.randint(0, 2, 20))
        model, metrics = train_model(X, y)
        assert hasattr(model, "predict_proba")
        proba = model.predict_proba(X)
        assert proba.shape == (20, 2)

    def test_deterministic_training(self) -> None:
        X = pd.DataFrame({
            "fvg_detected": np.random.randint(0, 2, 30),
            "atr": np.random.rand(30) * 0.01,
            "rsi": np.random.rand(30) * 100,
        })
        y = pd.Series(np.random.randint(0, 2, 30))
        model1, _ = train_model(X, y, random_state=42)
        model2, _ = train_model(X, y, random_state=42)
        p1 = model1.predict_proba(X)
        p2 = model2.predict_proba(X)
        np.testing.assert_array_almost_equal(p1, p2)

    def test_no_future_leakage_in_features(self) -> None:
        X, y, feature_names, _ = load_dataset(EURUSD_V3, FEATURES_ML_V3)
        forbidden = {"pnl_r", "win", "future_return", "exit_reason",
                      "max_favorable_excursion", "max_adverse_excursion"}
        assert len(forbidden & set(X.columns)) == 0


class TestEvaluateTradeMetrics:
    def test_returns_required_keys(self) -> None:
        y_true = pd.Series([1, 0, 1, 0, 1])
        y_prob = np.array([0.9, 0.1, 0.8, 0.2, 0.7])
        metrics = evaluate_trade_metrics(y_true, y_prob, threshold=0.5)
        for key in ("accuracy", "precision", "recall", "roc_auc"):
            assert key in metrics

    def test_with_pnl_returns_trading_metrics(self) -> None:
        y_true = pd.Series([1, 0, 1, 0, 1])
        y_prob = np.array([0.9, 0.1, 0.8, 0.4, 0.7])
        pnl = pd.Series([2.0, -1.0, 1.5, -0.5, 3.0])
        metrics = evaluate_trade_metrics(y_true, y_prob, pnl_r=pnl, threshold=0.5)
        assert "win_rate_impact" in metrics
        assert "profit_factor_impact" in metrics
        assert "expectancy_impact" in metrics
        assert "accepted_win_rate" in metrics


class TestFindOptimalThreshold:
    def test_finds_threshold(self) -> None:
        y_true = pd.Series([1, 0, 1, 0, 1, 1, 0, 0, 1, 0])
        y_prob = np.linspace(0.1, 0.9, 10)
        pnl = pd.Series([2, -1, 3, -0.5, 1, 2.5, -2, -1, 4, -0.5])
        result = find_optimal_threshold(y_true, y_prob, pnl_r=pnl, metric="profit_factor")
        assert 0.1 <= result["recommended_threshold"] <= 0.9
        assert result["metric"] == "profit_factor"
        assert len(result["threshold_scan"]) > 0


class TestSaveLoadModel:
    def test_save_and_load(self, tmp_path: Path) -> None:
        X = pd.DataFrame({"fvg_detected": [0, 1, 0, 1], "atr": [0.001, 0.002, 0.001, 0.003]})
        y = pd.Series([0, 1, 0, 1])
        model, _ = train_model(X, y)

        model_path = tmp_path / "test_model.pkl"
        metadata = ModelMetadata(
            feature_names=["fvg_detected", "atr"],
            schema_version="v3",
            training_date="2025-01-01T00:00:00Z",
            metrics={"accuracy": 0.75},
            model_name="xgboost",
            n_samples=4,
            feature_importance=[{"feature": "fvg_detected", "importance": 0.6},
                                {"feature": "atr", "importance": 0.4}],
        )
        save_model(model, metadata, model_path)
        assert model_path.exists()
        assert model_path.with_suffix(".json").exists()

        loaded_model, loaded_meta = load_model(model_path)
        assert loaded_meta["feature_names"] == ["fvg_detected", "atr"]
        assert loaded_meta["schema_version"] == "v3"
        assert loaded_meta["training_date"] == "2025-01-01T00:00:00Z"
        proba = loaded_model.predict_proba(X)
        assert proba.shape == (4, 2)


class TestFeatureSchemaCompatibility:
    def test_v3_dataset_has_all_features(self) -> None:
        df = pd.read_parquet(EURUSD_V3)
        expected = [
            "bos_detected", "fvg_fill_status", "fvg_direction",
            "displacement_magnitude", "displacement_bullish", "displacement_bearish",
            "premium_discount_zone", "premium_distance", "ote_long_min", "ote_short_min",
            "agent_wyckoff_spring", "agent_wyckoff_upthrust",
            "agent_wyckoff_sos", "agent_wyckoff_sow", "agent_wyckoff_effort_divergence",
        ]
        for col in expected:
            assert col in df.columns, f"Expected v3 column not found: {col}"

    def test_no_legacy_columns(self) -> None:
        df = pd.read_parquet(EURUSD_V3)
        legacy = {"displacement_strength"}
        found = legacy & set(df.columns)
        assert len(found) == 0, f"Legacy columns still present: {found}"


class TestModelLoadsCorrectly:
    def test_production_model_loads(self) -> None:
        if not MODEL_PATH.exists():
            pytest.skip("Production model not found")
        model, metadata = load_model(MODEL_PATH)
        assert "feature_names" in metadata
        assert "training_date" in metadata
        assert "metrics" in metadata
        assert len(metadata["feature_names"]) > 0
        assert hasattr(model, "predict_proba")

    def test_model_predicts_probability(self) -> None:
        if not MODEL_PATH.exists():
            pytest.skip("Production model not found")
        model, metadata = load_model(MODEL_PATH)
        n_features = len(metadata["feature_names"])
        X_dummy = pd.DataFrame(np.random.randn(3, n_features), columns=metadata["feature_names"])
        proba = model.predict_proba(X_dummy)
        assert proba.shape == (3, 2)
        assert (proba >= 0).all()
        assert (proba <= 1).all()
