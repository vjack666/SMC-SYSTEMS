from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import scipy.stats as ss
from sklearn.model_selection import TimeSeriesSplit


class PurgedKFold:
    def __init__(self, n_splits: int = 5, embargo: int = 0, purge: int = 0):
        self.n_splits = n_splits
        self.embargo = embargo
        self.purge = purge

    def split(self, X, y=None, times=None):
        if times is None:
            yield from TimeSeriesSplit(n_splits=self.n_splits).split(X, y)
            return

        n = len(X)
        test_size = n // (self.n_splits + 1)
        remainder = n - test_size * (self.n_splits + 1)

        for split_idx in range(self.n_splits):
            val_start = (split_idx + 1) * test_size + min(remainder, split_idx)
            if split_idx < remainder:
                val_end = val_start + test_size + 1
            else:
                val_end = val_start + test_size

            train_end = val_start - self.purge
            if train_end < 0:
                train_end = 0

            train_idx = np.arange(0, train_end)

            val_start_adjusted = val_start
            val_end_adjusted = val_end

            val_idx = np.arange(val_start_adjusted, val_end_adjusted)

            if train_end > 0 and self.embargo > 0:
                train_idx = train_idx[times[train_idx] < times[val_start] - self.purge]
                if len(train_idx) == 0:
                    train_idx = np.array([], dtype=int)

            yield (train_idx, val_idx)

    def get_n_splits(self):
        return self.n_splits


def compute_cvar(returns: np.ndarray, confidence_level: float = 0.05) -> float:
    var = np.quantile(returns, confidence_level)
    cvar = returns[returns <= var].mean()
    return float(cvar)


def compute_deflated_sharpe_ratio(
    sharpe_ratios: np.ndarray,
    num_trials: int,
    skew: float | None = None,
    kurtosis: float | None = None,
    df: int = 0,
) -> float:
    T = len(sharpe_ratios) if df == 0 else df
    var_SR = 1.0 / max(T - 1, 1)
    euler_gamma = 0.5772156649
    z_max = np.sqrt(2 * np.log(num_trials))
    log_log = np.log(np.log(num_trials)) if num_trials > 1 else 0.0
    E_max_SR = np.sqrt(var_SR) * ((1 - euler_gamma) * z_max + euler_gamma * log_log)
    observed_SR = np.mean(sharpe_ratios) / np.std(sharpe_ratios) if np.std(sharpe_ratios) > 0 else 0.0
    dsr = ss.norm.cdf((observed_SR - E_max_SR) / np.sqrt(var_SR))
    return float(dsr)


def compute_pbo(
    fold_performance: np.ndarray,
    threshold_sharpe: float = 0.0,
    n_simulations: int = 1000,
    random_state: int = 42,
) -> float:
    rng = np.random.default_rng(random_state)
    n_splits, n_strategies = fold_performance.shape
    overfit_count = 0

    for _ in range(n_simulations):
        assignment = rng.integers(0, 2, size=n_splits)
        train_mask = assignment == 0
        test_mask = assignment == 1

        if train_mask.sum() == 0 or test_mask.sum() == 0:
            continue

        train_perf = fold_performance[train_mask].mean(axis=0)
        test_perf = fold_performance[test_mask].mean(axis=0)

        best_strategy_idx = np.argmax(train_perf)
        best_test_value = test_perf[best_strategy_idx]
        rank = np.sum(test_perf > best_test_value)

        if rank >= n_strategies / 2:
            overfit_count += 1

    return overfit_count / n_simulations


def bootstrap_confidence_interval(
    returns: np.ndarray,
    n_iterations: int = 10000,
    alpha: float = 0.05,
    statistic: str = "sharpe",
    random_state: int = 42,
) -> dict[str, float]:
    rng = np.random.default_rng(random_state)
    n = len(returns)
    boot_stats = np.zeros(n_iterations)

    for i in range(n_iterations):
        sample = rng.choice(returns, size=n, replace=True)
        if statistic == "sharpe":
            boot_stats[i] = np.mean(sample) / np.std(sample) if np.std(sample) > 0 else 0.0
        elif statistic == "mean":
            boot_stats[i] = np.mean(sample)
        elif statistic == "win_rate":
            boot_stats[i] = np.mean(sample > 0)
        elif statistic == "profit_factor":
            gains = sample[sample > 0].sum()
            losses = abs(sample[sample < 0].sum())
            boot_stats[i] = gains / losses if losses > 0 else float("inf")
        else:
            raise ValueError(f"Unknown statistic: {statistic}")

    boot_stats = boot_stats[~np.isinf(boot_stats)]
    lower = np.percentile(boot_stats, 100 * alpha / 2)
    upper = np.percentile(boot_stats, 100 * (1 - alpha / 2))

    if statistic == "sharpe":
        observed = float(np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0.0)
    elif statistic == "mean":
        observed = float(np.mean(returns))
    elif statistic == "win_rate":
        observed = float(np.mean(returns > 0))
    elif statistic == "profit_factor":
        gains = returns[returns > 0].sum()
        losses = abs(returns[returns < 0].sum())
        observed = float(gains / losses) if losses > 0 else float("inf")
    else:
        raise ValueError(f"Unknown statistic: {statistic}")

    return {
        "lower": float(lower),
        "upper": float(upper),
        "observed": float(observed),
        "std_error": float(np.std(boot_stats)),
    }


@dataclass
class StatsValidationResult:
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    cvar_95: float = 0.0
    cvar_99: float = 0.0
    deflated_sharpe: float = 0.0
    pbo: float = 0.0
    bootstrap_ci_sharpe: dict = field(default_factory=dict)
    bootstrap_ci_win_rate: dict = field(default_factory=dict)
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0


def compute_full_validation(
    trade_returns: np.ndarray,
    strategy_sharpe_matrix: np.ndarray | None = None,
    num_trials: int = 1,
    n_bootstrap: int = 1000,
    n_pbo_simulations: int = 500,
    random_state: int = 42,
) -> StatsValidationResult:
    trade_returns = np.asarray(trade_returns, dtype=float)
    n = len(trade_returns)

    if n == 0:
        return StatsValidationResult()

    mean_ret = float(np.mean(trade_returns))
    std_ret = float(np.std(trade_returns, ddof=1))

    sharpe = mean_ret / std_ret if std_ret > 0 else 0.0

    downside = trade_returns[trade_returns < 0]
    downside_std = float(np.std(downside, ddof=1)) if len(downside) > 1 else 1.0
    sortino = mean_ret / downside_std if downside_std > 0 else 0.0

    cum = np.cumsum(trade_returns)
    peak = np.maximum.accumulate(cum)
    drawdown = peak - cum
    max_dd = float(np.max(drawdown))
    calmar = mean_ret / max_dd if max_dd > 1e-10 else 0.0

    cvar_95 = compute_cvar(trade_returns, 0.05)
    cvar_99 = compute_cvar(trade_returns, 0.01)

    total_trades = n
    win_rate = float(np.mean(trade_returns > 0))
    gains = trade_returns[trade_returns > 0].sum()
    losses = abs(trade_returns[trade_returns < 0].sum())
    profit_factor = float(gains / losses) if losses > 1e-10 else float("inf")

    bootstrap_ci_sharpe = bootstrap_confidence_interval(
        trade_returns, n_iterations=n_bootstrap, statistic="sharpe", random_state=random_state
    )
    bootstrap_ci_win_rate = bootstrap_confidence_interval(
        trade_returns, n_iterations=n_bootstrap, statistic="win_rate", random_state=random_state
    )

    if num_trials > 0:
        sharpe_ratios = np.array([sharpe])
        deflated_sharpe = compute_deflated_sharpe_ratio(
            sharpe_ratios, num_trials=max(num_trials, 1)
        )
    else:
        deflated_sharpe = 0.0

    pbo = 0.0
    if strategy_sharpe_matrix is not None and strategy_sharpe_matrix.shape[1] > 1:
        pbo = compute_pbo(
            strategy_sharpe_matrix,
            n_simulations=n_pbo_simulations,
            random_state=random_state,
        )

    return StatsValidationResult(
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        cvar_95=cvar_95,
        cvar_99=cvar_99,
        deflated_sharpe=deflated_sharpe,
        pbo=pbo,
        bootstrap_ci_sharpe=bootstrap_ci_sharpe,
        bootstrap_ci_win_rate=bootstrap_ci_win_rate,
        total_trades=total_trades,
        win_rate=win_rate,
        profit_factor=profit_factor,
        max_drawdown=max_dd,
    )
