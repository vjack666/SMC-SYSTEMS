from __future__ import annotations

import numpy as np
import pytest

from ml.stats_validator import (
    PurgedKFold,
    bootstrap_confidence_interval,
    compute_cvar,
    compute_deflated_sharpe_ratio,
    compute_full_validation,
    compute_pbo,
)


class TestComputeCVaR:
    def test_positive_returns(self) -> None:
        returns = np.array([0.01, 0.02, 0.015, 0.03, 0.025])
        result = compute_cvar(returns, confidence_level=0.05)
        assert result > 0

    def test_negative_returns(self) -> None:
        returns = np.array([-0.01, -0.02, -0.015, -0.03, -0.025])
        result = compute_cvar(returns, confidence_level=0.05)
        assert result < 0


class TestPurgedKFold:
    def test_three_splits(self) -> None:
        X = np.arange(100).reshape(-1, 1)
        pkf = PurgedKFold(n_splits=3)
        splits = list(pkf.split(X))
        assert len(splits) == 3

    def test_get_n_splits(self) -> None:
        pkf = PurgedKFold(n_splits=5)
        assert pkf.get_n_splits() == 5

    def test_splits_are_disjoint(self) -> None:
        X = np.arange(100).reshape(-1, 1)
        pkf = PurgedKFold(n_splits=3)
        for train_idx, val_idx in pkf.split(X):
            assert len(set(train_idx) & set(val_idx)) == 0


class TestDeflatedSharpeRatio:
    def test_between_zero_and_one(self) -> None:
        sharpe_ratios = np.array([0.5, 0.6, 0.55, 0.65, 0.7])
        result = compute_deflated_sharpe_ratio(sharpe_ratios, num_trials=10)
        assert 0 <= result <= 1.0


class TestBootstrapCI:
    def test_returns_dict_with_keys(self) -> None:
        returns = np.random.default_rng(42).normal(0.001, 0.02, size=200)
        result = bootstrap_confidence_interval(returns, n_iterations=500, statistic="sharpe")
        assert "lower" in result
        assert "upper" in result
        assert "observed" in result
        assert "std_error" in result
        assert result["lower"] < result["upper"]


class TestComputePBO:
    def test_pbo_range(self) -> None:
        matrix = np.random.default_rng(42).normal(0.01, 0.1, size=(5, 20))
        result = compute_pbo(matrix, n_simulations=200)
        assert 0 <= result <= 1.0


class TestComputeFullValidation:
    def test_returns_stats_validation_result(self) -> None:
        returns = np.array([0.01, -0.005, 0.02, -0.01, 0.015, 0.005, -0.002, 0.008])
        result = compute_full_validation(returns, num_trials=1)
        assert result.total_trades == 8
        assert result.sharpe_ratio != 0.0
        assert "lower" in result.bootstrap_ci_sharpe
        assert "lower" in result.bootstrap_ci_win_rate

    def test_empty_returns(self) -> None:
        result = compute_full_validation(np.array([]))
        assert result.total_trades == 0
