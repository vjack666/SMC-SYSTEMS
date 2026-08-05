from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import BaseCrossValidator


# ---------------------------------------------------------------------------
# Purged KFold with Embargo
# ---------------------------------------------------------------------------

class PurgedKFold(BaseCrossValidator):
    """Time-series KFold that purges overlapping data and applies an embargo gap.

    Parameters
    ----------
    n_splits : int
        Number of folds.
    embargo_pct : float
        Fraction of test set length to embargo after each train set.
    """

    def __init__(self, n_splits: int = 5, embargo_pct: float = 0.05) -> None:
        self.n_splits = n_splits
        self.embargo_pct = embargo_pct

    def split(
        self, X: pd.DataFrame, y: Any = None, groups: Any = None
    ) -> list[tuple[np.ndarray, np.ndarray]]:
        if not isinstance(X, pd.DataFrame) or "time" not in X.columns:
            raise ValueError("PurgedKFold requires a DataFrame with a 'time' column.")
        times = pd.to_datetime(X["time"], utc=True)
        sorted_idx = np.argsort(times.values)
        n = len(sorted_idx)
        fold_sizes = np.full(self.n_splits, n // self.n_splits, dtype=int)
        fold_sizes[: n % self.n_splits] += 1
        current = 0
        folds: list[tuple[np.ndarray, np.ndarray]] = []
        for fold_size in fold_sizes:
            test_start = current
            test_end = current + fold_size
            test_idx = sorted_idx[test_start:test_end]
            test_times = times.iloc[test_idx]
            test_min = test_times.min()
            test_max = test_times.max()
            embargo = (test_max - test_min) * self.embargo_pct
            purge_before = test_min
            purge_after = test_max + embargo

            train_idx = []
            for i in sorted_idx:
                t = times.iloc[i]
                if t >= purge_before:
                    continue
                if t <= purge_after:
                    continue
                train_idx.append(i)

            if len(train_idx) == 0:
                train_idx = np.array([], dtype=int)
            else:
                train_idx = np.array(train_idx, dtype=int)

            folds.append((train_idx, test_idx))
            current += fold_size
        return folds

    def get_n_splits(self, X: Any = None, y: Any = None, groups: Any = None) -> int:
        return self.n_splits


def run_purged_cv(
    trades: pd.DataFrame,
    n_splits: int = 5,
    embargo_pct: float = 0.05,
    metric_fn: Any = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run Purged K-Fold cross-validation on trade data.

    Parameters
    ----------
    trades : pd.DataFrame
        Must contain 'pnl_r' and 'time' (or 'entry_time') columns.
    n_splits : int
        Number of folds.
    embargo_pct : float
        Embargo as fraction of test window.
    metric_fn : callable, optional
        Function that takes a DataFrame and returns a metrics dict.
        Defaults to _basic_metrics.

    Returns
    -------
    fold_df : pd.DataFrame
        Metrics per fold.
    summary : dict
        Aggregated results with mean, std, min, max across folds.
    """
    df = trades.copy()
    if "time" not in df.columns and "entry_time" in df.columns:
        df["time"] = df["entry_time"]
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.sort_values("time").reset_index(drop=True)

    if metric_fn is None:
        metric_fn = _basic_metrics

    cv = PurgedKFold(n_splits=n_splits, embargo_pct=embargo_pct)
    fold_results: list[dict[str, Any]] = []
    for fold_idx, (train_idx, test_idx) in enumerate(cv.split(df)):
        train_df = df.iloc[train_idx] if len(train_idx) else pd.DataFrame()
        test_df = df.iloc[test_idx]
        train_metrics = metric_fn(train_df) if len(train_df) else {}
        test_metrics = metric_fn(test_df)
        fold_results.append({
            "fold": fold_idx + 1,
            "train_trades": len(train_df),
            "test_trades": len(test_df),
            **{f"train_{k}": v for k, v in train_metrics.items()},
            **{f"test_{k}": v for k, v in test_metrics.items()},
        })

    fold_df = pd.DataFrame(fold_results)
    summary = _aggregate_folds(fold_df)
    return fold_df, summary


# ---------------------------------------------------------------------------
# Bootstrap Validation
# ---------------------------------------------------------------------------

def bootstrap_validation(
    trades: pd.DataFrame,
    n_iterations: int = 1000,
    random_state: int = 42,
) -> dict[str, Any]:
    """Resample trades with replacement to estimate distribution of metrics.

    Parameters
    ----------
    trades : pd.DataFrame
        Must contain 'pnl_r'.
    n_iterations : int
        Number of bootstrap samples.
    random_state : int
        Random seed.

    Returns
    -------
    dict
        Bootstrap distribution summary with percentiles and confidence intervals.
    """
    pnl = pd.to_numeric(trades["pnl_r"], errors="coerce").dropna().to_numpy()
    if len(pnl) == 0:
        return {"n_iterations": 0, "error": "No valid pnl_r values"}

    rng = np.random.default_rng(random_state)
    n = len(pnl)
    metrics_list: list[dict[str, float]] = []
    for _ in range(n_iterations):
        sample = rng.choice(pnl, size=n, replace=True)
        metrics_list.append(_pnl_metrics(sample))

    result = _bootstrap_summary(metrics_list, n_iterations)
    result["n_iterations"] = n_iterations
    result["n_original_trades"] = n
    return result


# ---------------------------------------------------------------------------
# Risk Metrics
# ---------------------------------------------------------------------------

def calculate_var(pnl: np.ndarray, alpha: float = 0.05) -> float:
    """Value at Risk - percentile loss at given alpha."""
    if len(pnl) == 0:
        return 0.0
    return float(np.quantile(pnl, alpha))


def calculate_cvar(pnl: np.ndarray, alpha: float = 0.05) -> float:
    """Conditional VaR (Expected Shortfall) - mean loss beyond VaR."""
    if len(pnl) == 0:
        return 0.0
    var = calculate_var(pnl, alpha)
    tail = pnl[pnl <= var]
    if len(tail) == 0:
        return float(var)
    return float(tail.mean())


def calculate_drawdown_duration(equity: pd.Series) -> dict[str, float]:
    """Time Under Water statistics.

    Parameters
    ----------
    equity : pd.Series
        Cumulative PnL series (indexed by time).

    Returns
    -------
    dict
        avg_duration, max_duration, median_duration in bars/trades.
    """
    peak = equity.cummax()
    dd = equity - peak
    in_drawdown = dd < 0
    if not in_drawdown.any():
        return {"avg_duration_bars": 0.0, "max_duration_bars": 0.0, "median_duration_bars": 0.0}

    durations: list[int] = []
    current_len = 0
    for flag in in_drawdown:
        if flag:
            current_len += 1
        else:
            if current_len > 0:
                durations.append(current_len)
            current_len = 0
    if current_len > 0:
        durations.append(current_len)

    if not durations:
        return {"avg_duration_bars": 0.0, "max_duration_bars": 0.0, "median_duration_bars": 0.0}

    return {
        "avg_duration_bars": float(np.mean(durations)),
        "max_duration_bars": float(np.max(durations)),
        "median_duration_bars": float(np.median(durations)),
    }


def calculate_ulcer_index(equity: pd.Series) -> float:
    """Ulcer Index - square root of mean squared drawdown depth."""
    peak = equity.cummax()
    dd_pct = (equity - peak) / peak
    dd_sq = (dd_pct.clip(upper=0)) ** 2
    return float(np.sqrt(dd_sq.mean()))


def calculate_sortino_ratio(pnl: np.ndarray, risk_free: float = 0.0) -> float:
    """Sortino Ratio - excess return over downside deviation."""
    if len(pnl) == 0:
        return 0.0
    excess = pnl.mean() - risk_free
    downside = pnl[pnl < 0]
    if len(downside) == 0:
        return float(excess / max(pnl.std(), 1e-9) * np.sqrt(252))
    dd_std = np.std(downside)
    if dd_std == 0:
        return 0.0
    return float(excess / dd_std * np.sqrt(252))


def calculate_omega_ratio(pnl: np.ndarray, threshold: float = 0.0) -> float:
    """Omega Ratio - probability-weighted gain/loss ratio."""
    if len(pnl) == 0:
        return 1.0
    gains = pnl[pnl > threshold].sum()
    losses = abs(pnl[pnl <= threshold].sum())
    if losses == 0:
        return float("inf")
    return float(gains / losses)


def calculate_gain_to_pain(pnl: np.ndarray) -> float:
    """Gain-to-Pain Ratio - sum of all gains / sum of all losses."""
    if len(pnl) == 0:
        return 0.0
    gains = pnl[pnl > 0].sum()
    losses = abs(pnl[pnl < 0].sum())
    if losses == 0:
        return float(gains / 1e-9) if gains > 0 else 0.0
    return float(gains / losses)


def calculate_tail_ratio(pnl: np.ndarray, percentile: float = 5.0) -> float:
    """Ratio of right-tail (gains) to left-tail (losses) at given percentile."""
    if len(pnl) == 0:
        return 1.0
    left = abs(np.percentile(pnl, percentile))
    right = np.percentile(pnl, 100 - percentile)
    if left == 0:
        return float("inf")
    return float(right / left)


def calculate_recovery_factor(pnl: np.ndarray) -> float:
    """Recovery Factor - total return / max drawdown."""
    if len(pnl) == 0:
        return 0.0
    total = pnl.sum()
    equity = np.cumsum(pnl)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak).min()
    if dd == 0:
        return float(total / 1e-9)
    return float(abs(total / dd))


def calculate_risk_of_ruin(pnl: np.ndarray, simulations: int = 10000) -> float:
    """Probability of ruin (drawdown exceeding -10R) via Monte Carlo."""
    if len(pnl) == 0:
        return 1.0
    rng = np.random.default_rng(42)
    n = len(pnl)
    ruin_count = 0
    for _ in range(simulations):
        sample = rng.choice(pnl, size=n, replace=True)
        eq = np.cumsum(sample)
        peak = np.maximum.accumulate(eq)
        dd = (eq - peak).min()
        if dd <= -10.0:
            ruin_count += 1
    return float(ruin_count / simulations)


def calculate_k_ratio(pnl: np.ndarray) -> float:
    """K-Ratio - slope of equity curve divided by its standard error."""
    if len(pnl) < 3:
        return 0.0
    equity = np.cumsum(pnl)
    x = np.arange(len(equity))
    slope, _ = np.polyfit(x, equity, 1)
    residuals = equity - (slope * x + np.mean(equity) * (1 - slope * x.mean() / np.var(x) if np.var(x) > 0 else 0))
    std_err = np.std(residuals) / np.sqrt(len(equity)) if len(equity) > 1 else 1.0
    if std_err == 0:
        return float(slope / 1e-9)
    return float(slope / std_err)


# ---------------------------------------------------------------------------
# Rolling Stability Metrics
# ---------------------------------------------------------------------------

def rolling_sharpe(pnl: pd.Series, window: int = 50) -> pd.Series:
    """Rolling Sharpe Ratio (annualized) over a window of trades."""
    roll = pnl.rolling(window, min_periods=max(10, window // 4))
    sharpe = roll.mean() / roll.std().clip(lower=1e-9) * np.sqrt(252)
    return sharpe.fillna(0.0)


def rolling_profit_factor(pnl: pd.Series, window: int = 50) -> pd.Series:
    """Rolling Profit Factor over a window of trades."""
    roll = pnl.rolling(window, min_periods=max(10, window // 4))
    pf = roll.apply(
        lambda x: x[x > 0].sum() / max(abs(x[x <= 0].sum()), 1e-9),
        raw=True,
    )
    return pf.fillna(1.0)


def rolling_expectancy(pnl: pd.Series, window: int = 50) -> pd.Series:
    """Rolling mean PnL (expectancy) over a window."""
    return pnl.rolling(window, min_periods=1).mean().fillna(0.0)


# ---------------------------------------------------------------------------
# Overfitting Tests
# ---------------------------------------------------------------------------

def deflated_sharpe_ratio(
    observed_sharpe: float,
    num_trials: int,
    num_trades: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Deflated Sharpe Ratio - adjusts for multiple testing.

    Parameters
    ----------
    observed_sharpe : float
        The observed Sharpe ratio.
    num_trials : int
        Number of independent trials/strategies tested.
    num_trades : int
        Number of trades in the sample.
    skewness : float
        Skewness of returns (default 0).
    kurtosis : float
        Kurtosis of returns (default 3 for normal).

    Returns
    -------
    float
        Probability that the observed Sharpe exceeds the expected maximum
        under the null of no skill. Higher = more likely real.
    """
    from scipy.stats import norm

    if num_trades < 3:
        return 0.5

    gamma3 = skewness
    gamma4 = kurtosis

    var_sharpe = (1 + 0.5 * gamma4 - gamma3**2) / (num_trades - 1)
    std_sharpe = np.sqrt(var_sharpe) if var_sharpe > 0 else 1.0

    emax = std_sharpe * (
        (1 - np.euler_gamma) * norm.ppf(1 - 1.0 / num_trials)
        + np.euler_gamma * norm.ppf(1 - 1.0 / (num_trials * np.e))
    )

    if std_sharpe == 0:
        return 0.5

    dsr = (observed_sharpe - emax) / std_sharpe
    p_value = 1 - norm.cdf(dsr) if np.isfinite(dsr) else 0.5
    return float(p_value)


def probability_of_backtest_overfitting(
    trades: pd.DataFrame,
    n_splits: int = 20,
    n_shuffles: int = 100,
    random_state: int = 42,
) -> dict[str, Any]:
    """Estimate Probability of Backtest Overfitting (PBO) via CSCV.

    Uses the Combinatorial Symmetric Cross-Validation (CSCV) approach
    from Bailey et al. (2016). Returns the probability that the strategy
    selection would have been a disappointment out-of-sample.

    Simplified implementation using rank-based logit metric.
    """
    pnl = pd.to_numeric(trades["pnl_r"], errors="coerce").dropna()
    if len(pnl) < n_splits * 5:
        return {"pbo": 0.5, "error": f"Not enough trades ({len(pnl)}), need at least {n_splits * 5}"}

    n = len(pnl)
    rng = np.random.default_rng(random_state)

    shuffled_indices = np.arange(n)
    count_rank_above = 0

    for _ in range(n_shuffles):
        rng.shuffle(shuffled_indices)
        shuffled = pnl.iloc[shuffled_indices].values

        fold_size = n // n_splits
        in_sample_sr = []
        out_sample_sr = []
        for i in range(n_splits):
            test_start = i * fold_size
            test_end = test_start + fold_size if i < n_splits - 1 else n
            test_slice = shuffled[test_start:test_end]
            train_slice = np.concatenate([shuffled[:test_start], shuffled[test_end:]])

            train_sr = _sharpe_ratio(train_slice)
            test_sr = _sharpe_ratio(test_slice)
            in_sample_sr.append(train_sr)
            out_sample_sr.append(test_sr)

        in_sample_sr = np.array(in_sample_sr)
        out_sample_sr = np.array(out_sample_sr)

        best_is_idx = np.argmax(in_sample_sr)
        rank_os = np.sum(out_sample_sr > out_sample_sr[best_is_idx])
        count_rank_above += rank_os / (n_splits - 1) if n_splits > 1 else 0

    pbo = count_rank_above / n_shuffles
    return {"pbo": float(pbo), "n_splits": n_splits, "n_shuffles": n_shuffles}


# ---------------------------------------------------------------------------
# Comprehensive Metrics Computation
# ---------------------------------------------------------------------------

def compute_all_risk_metrics(trades: pd.DataFrame) -> dict[str, Any]:
    """Compute all risk and stability metrics from a trades DataFrame.

    Parameters
    ----------
    trades : pd.DataFrame
        Must contain 'pnl_r'. May contain 'exit_time' or 'entry_time' for rolling.

    Returns
    -------
    dict
        Flat dictionary of all computed metrics.
    """
    pnl = pd.to_numeric(trades["pnl_r"], errors="coerce").dropna()
    arr = pnl.to_numpy()
    n = len(arr)
    if n == 0:
        return {"total_trades": 0}

    wins = arr[arr > 0]
    losses = arr[arr <= 0]
    equity = pnl.cumsum()

    win_rate = float((arr > 0).mean())
    pf = float(wins.sum() / max(abs(losses.sum()), 1e-9)) if len(losses) > 0 else float("inf")
    expectancy = float(arr.mean())
    total_r = float(arr.sum())
    std_r = float(arr.std())

    peak = equity.cummax()
    dd_series = (equity - peak) / equity.abs().clip(lower=1e-9)
    max_dd_r = float((equity - peak).min())
    max_peak = float(peak.max())
    max_dd_pct = float(abs(max_dd_r) / max(abs(max_peak), 1.0)) * 100.0 if max_peak != 0 else 0.0

    sharpe = float(arr.mean() / max(arr.std(), 1e-9) * np.sqrt(252))

    dd_duration = calculate_drawdown_duration(equity)
    var_95 = calculate_var(arr, 0.05)
    var_99 = calculate_var(arr, 0.01)
    cvar_95 = calculate_cvar(arr, 0.05)
    sortino = calculate_sortino_ratio(arr)
    omega = calculate_omega_ratio(arr)
    gain_to_pain = calculate_gain_to_pain(arr)
    tail_ratio_5 = calculate_tail_ratio(arr, 5.0)
    tail_ratio_10 = calculate_tail_ratio(arr, 10.0)
    recovery = calculate_recovery_factor(arr)
    ulcer = calculate_ulcer_index(equity)
    ruin = calculate_risk_of_ruin(arr)
    k_ratio = calculate_k_ratio(arr)

    rolling_sharpe_series = rolling_sharpe(pnl, window=min(50, max(n // 4, 10)))
    rolling_pf_series = rolling_profit_factor(pnl, window=min(50, max(n // 4, 10)))
    rolling_exp_series = rolling_expectancy(pnl, window=min(50, max(n // 4, 10)))

    def _ci(series: pd.Series) -> tuple[float, float]:
        s = series.dropna()
        if len(s) < 2:
            return 0.0, 1.0
        return float(s.quantile(0.05)), float(s.quantile(0.95))

    roll_sharpe_ci = _ci(rolling_sharpe_series)
    roll_pf_ci = _ci(rolling_pf_series)
    roll_exp_ci = _ci(rolling_exp_series)

    rolling_sharpe_5pct = float(rolling_sharpe_series.quantile(0.05))
    rolling_sharpe_95pct = float(rolling_sharpe_series.quantile(0.95))
    rolling_pf_5pct = float(rolling_pf_series.quantile(0.05))
    rolling_pf_95pct = float(rolling_pf_series.quantile(0.95))

    num_wins = len(wins)
    num_losses = len(losses)

    return {
        "total_trades": n,
        "win_rate": round(win_rate, 4),
        "profit_factor": round(pf, 4) if np.isfinite(pf) else None,
        "expectancy_r": round(expectancy, 4),
        "total_r": round(total_r, 4),
        "std_r": round(std_r, 4),
        "max_drawdown_r": round(float(max_dd_r), 4),
        "max_drawdown_pct": round(max_dd_pct, 4),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "omega_ratio": round(omega, 4) if np.isfinite(omega) else None,
        "gain_to_pain_ratio": round(gain_to_pain, 4),
        "tail_ratio_5pct": round(tail_ratio_5, 4) if np.isfinite(tail_ratio_5) else None,
        "tail_ratio_10pct": round(tail_ratio_10, 4) if np.isfinite(tail_ratio_10) else None,
        "recovery_factor": round(recovery, 4) if np.isfinite(recovery) else None,
        "ulcer_index": round(ulcer, 4),
        "k_ratio": round(k_ratio, 4),
        "var_95": round(var_95, 4),
        "var_99": round(var_99, 4),
        "cvar_95": round(cvar_95, 4),
        "risk_of_ruin": round(ruin, 4),
        **{f"dd_{k}": round(v, 4) for k, v in dd_duration.items()},
        "rolling_sharpe_5pct": round(rolling_sharpe_5pct, 4),
        "rolling_sharpe_95pct": round(rolling_sharpe_95pct, 4),
        "rolling_sharpe_ci_low": round(roll_sharpe_ci[0], 4),
        "rolling_sharpe_ci_high": round(roll_sharpe_ci[1], 4),
        "rolling_pf_5pct": round(rolling_pf_5pct, 4) if np.isfinite(rolling_pf_5pct) else None,
        "rolling_pf_95pct": round(rolling_pf_95pct, 4) if np.isfinite(rolling_pf_95pct) else None,
        "rolling_pf_ci_low": round(roll_pf_ci[0], 4),
        "rolling_pf_ci_high": round(roll_pf_ci[1], 4),
        "rolling_expectancy_5pct": round(float(rolling_exp_series.quantile(0.05)), 4),
        "rolling_expectancy_95pct": round(float(rolling_exp_series.quantile(0.95)), 4),
        "rolling_expectancy_ci_low": round(roll_exp_ci[0], 4),
        "rolling_expectancy_ci_high": round(roll_exp_ci[1], 4),
        "num_win_trades": int(num_wins),
        "num_loss_trades": int(num_losses),
        "avg_win_r": round(float(wins.mean()), 4) if len(wins) > 0 else None,
        "avg_loss_r": round(float(losses.mean()), 4) if len(losses) > 0 else None,
    }


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------

def generate_validation_report(
    trades: pd.DataFrame,
    output_dir: Path = Path("results/robust_validation"),
    symbol: str = "ALL",
) -> dict[str, Any]:
    """Generate a complete robust validation report.

    Parameters
    ----------
    trades : pd.DataFrame
        Trade data with 'pnl_r' and optionally 'entry_time', 'symbol'.
    output_dir : Path
        Output directory for report artifacts.
    symbol : str
        Label for the report (e.g., symbol name or 'ALL').

    Returns
    -------
    dict
        All computed results.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    pnl = pd.to_numeric(trades["pnl_r"], errors="coerce").dropna()
    n = len(pnl)

    results: dict[str, Any] = {
        "symbol": symbol,
        "total_trades": int(n),
    }

    # 1. Basic + advanced metrics
    print(f"  [{symbol}] Computing risk metrics...")
    metrics = compute_all_risk_metrics(trades)
    results["metrics"] = metrics

    # 2. Bootstrap validation
    print(f"  [{symbol}] Running bootstrap validation...")
    bootstrap = bootstrap_validation(trades, n_iterations=min(1000, max(100, n)))
    results["bootstrap"] = bootstrap

    # 3. Purged K-Fold CV
    if n >= 50:
        print(f"  [{symbol}] Running Purged K-Fold CV...")
        fold_df, cv_summary = run_purged_cv(trades)
        fold_df.to_csv(output_dir / f"cv_folds_{symbol}.csv", index=False)
        results["purged_cv"] = cv_summary
    else:
        results["purged_cv"] = {"error": f"Only {n} trades, need >=50"}

    # 4. Overfitting tests
    print(f"  [{symbol}] Running overfitting tests...")
    if n >= 20:
        pbo = probability_of_backtest_overfitting(trades, n_shuffles=min(100, max(20, n // 2)))
        results["pbo"] = pbo
    else:
        results["pbo"] = {"error": f"Only {n} trades, need >=20"}

    sharpe = metrics.get("sharpe_ratio", 0.0)
    dsr = deflated_sharpe_ratio(
        observed_sharpe=sharpe if isinstance(sharpe, (int, float)) else 0.0,
        num_trials=max(1, n // 10),
        num_trades=n,
    )
    results["deflated_sharpe"] = {
        "observed_sharpe": sharpe,
        "num_trials_estimated": max(1, n // 10),
        "dsr_p_value": round(dsr, 4),
    }

    # 5. Write report
    report = _build_report_markdown(results)
    (output_dir / f"validation_report_{symbol}.md").write_text(report, encoding="utf-8")

    # 6. Save JSON
    (output_dir / f"validation_results_{symbol}.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8"
    )

    print(f"  [{symbol}] Report saved to {output_dir / f'validation_report_{symbol}.md'}")
    return results


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _basic_metrics(df: pd.DataFrame) -> dict[str, float]:
    if df.empty or "pnl_r" not in df.columns:
        return {"total_trades": 0, "win_rate": 0.0, "profit_factor": 1.0, "expectancy_r": 0.0, "max_drawdown_r": 0.0}
    pnl = pd.to_numeric(df["pnl_r"], errors="coerce").dropna()
    return _pnl_metrics(pnl.to_numpy())


def _pnl_metrics(arr: np.ndarray) -> dict[str, float]:
    if len(arr) == 0:
        return {"total_trades": 0, "win_rate": 0.0, "profit_factor": 1.0, "expectancy_r": 0.0, "max_drawdown_r": 0.0}
    wins = arr[arr > 0]
    losses = arr[arr <= 0]
    equity = np.cumsum(arr)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak).min()
    pf = wins.sum() / max(abs(losses.sum()), 1e-9) if len(losses) > 0 else float("inf")
    return {
        "total_trades": len(arr),
        "win_rate": round(float((arr > 0).mean()), 4),
        "profit_factor": round(float(pf), 4) if np.isfinite(pf) else None,
        "expectancy_r": round(float(arr.mean()), 4),
        "max_drawdown_r": round(float(dd), 4),
    }


def _sharpe_ratio(arr: np.ndarray) -> float:
    if len(arr) < 2 or arr.std() == 0:
        return 0.0
    return float(arr.mean() / arr.std() * np.sqrt(252))


def _aggregate_folds(fold_df: pd.DataFrame) -> dict[str, Any]:
    test_cols = [c for c in fold_df.columns if c.startswith("test_")]
    if not test_cols:
        return {"error": "No test columns"}
    summary: dict[str, Any] = {}
    for col in test_cols:
        vals = pd.to_numeric(fold_df[col], errors="coerce").dropna()
        if len(vals) == 0:
            continue
        summary[f"{col}_mean"] = round(float(vals.mean()), 4)
        summary[f"{col}_std"] = round(float(vals.std()), 4)
        summary[f"{col}_min"] = round(float(vals.min()), 4)
        summary[f"{col}_max"] = round(float(vals.max()), 4)
        summary[f"{col}_p25"] = round(float(vals.quantile(0.25)), 4)
        summary[f"{col}_p75"] = round(float(vals.quantile(0.75)), 4)
    summary["n_folds"] = int(len(fold_df))
    return summary


def _bootstrap_summary(
    metrics_list: list[dict[str, float]], n_iterations: int
) -> dict[str, Any]:
    keys = list(metrics_list[0].keys())
    result: dict[str, Any] = {"n_iterations": n_iterations}
    for key in keys:
        vals = np.array([m[key] for m in metrics_list], dtype=float)
        result[key] = {
            "mean": round(float(vals.mean()), 4),
            "std": round(float(vals.std()), 4),
            "p5": round(float(np.quantile(vals, 0.05)), 4),
            "p25": round(float(np.quantile(vals, 0.25)), 4),
            "p50": round(float(np.quantile(vals, 0.50)), 4),
            "p75": round(float(np.quantile(vals, 0.75)), 4),
            "p95": round(float(np.quantile(vals, 0.95)), 4),
        }
    return result


def _build_report_markdown(results: dict[str, Any]) -> str:
    symbol = results.get("symbol", "ALL")
    lines = [
        f"# Robust Validation Report — {symbol}",
        "",
        f"- **Total trades**: {results.get('total_trades', 0)}",
        "",
    ]

    # Metrics section
    metrics = results.get("metrics", {})
    if metrics:
        lines += [
            "## Risk & Performance Metrics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
        ]
        for k, v in metrics.items():
            if v is None:
                v_str = "N/A"
            elif isinstance(v, float):
                v_str = f"{v:.4f}"
            else:
                v_str = str(v)
            lines.append(f"| {k} | {v_str} |")
        lines.append("")

    # Bootstrap section
    bootstrap = results.get("bootstrap", {})
    if bootstrap and "win_rate" in bootstrap:
        lines += [
            "## Bootstrap Validation",
            f"- **Iterations**: {bootstrap.get('n_iterations', 0)}",
            f"- **Original trades**: {bootstrap.get('n_original_trades', 0)}",
            "",
            "| Metric | Mean | Std | P5 | P25 | P50 | P75 | P95 |",
            "|--------|------|-----|----|-----|-----|-----|------|",
        ]
        for key in ["win_rate", "profit_factor", "expectancy_r", "max_drawdown_r"]:
            dist = bootstrap.get(key, {})
            if isinstance(dist, dict):
                lines.append(
                    f"| {key} | {dist.get('mean', 'N/A')} | {dist.get('std', 'N/A')} | "
                    f"{dist.get('p5', 'N/A')} | {dist.get('p25', 'N/A')} | {dist.get('p50', 'N/A')} | "
                    f"{dist.get('p75', 'N/A')} | {dist.get('p95', 'N/A')} |"
                )
        lines.append("")

    # Purged CV section
    cv = results.get("purged_cv", {})
    if cv and "error" not in cv:
        lines += [
            "## Purged K-Fold Cross Validation",
            f"- **Folds**: {cv.get('n_folds', 'N/A')}",
            "",
            "| Metric | Mean | Std | Min | Max | P25 | P75 |",
            "|--------|------|-----|-----|-----|------|------|",
        ]
        test_cols = sorted([k for k in cv if k.endswith("_mean")])
        for col in test_cols:
            base = col.replace("_mean", "")
            lines.append(
                f"| {base} | {cv.get(f'{base}_mean', 'N/A')} | {cv.get(f'{base}_std', 'N/A')} | "
                f"{cv.get(f'{base}_min', 'N/A')} | {cv.get(f'{base}_max', 'N/A')} | "
                f"{cv.get(f'{base}_p25', 'N/A')} | {cv.get(f'{base}_p75', 'N/A')} |"
            )
        lines.append("")

    # Overfitting tests
    lines += ["## Overfitting Tests", ""]
    pbo = results.get("pbo", {})
    if "error" not in pbo:
        pbo_val = pbo.get("pbo", 0.5)
        lines += [
            f"- **Probability of Backtest Overfitting (PBO)**: {pbo_val:.4f}",
            f"  - {_pbo_interpretation(pbo_val)}",
            f"- **Shuffles**: {pbo.get('n_shuffles', 'N/A')}",
            "",
        ]
    else:
        lines.append(f"- PBO: {pbo.get('error', 'N/A')}")
        lines.append("")

    dsr = results.get("deflated_sharpe", {})
    if dsr:
        p_val = dsr.get("dsr_p_value", 0.5)
        lines += [
            f"- **Deflated Sharpe Ratio p-value**: {p_val:.4f}",
            f"  - Observed Sharpe: {dsr.get('observed_sharpe', 'N/A')}",
            f"  - Estimated trials: {dsr.get('num_trials_estimated', 'N/A')}",
            f"  - {_dsr_interpretation(p_val)}",
            "",
        ]

    # Interpretation
    lines += [
        "## Interpretation",
        "",
        _build_interpretation(metrics, bootstrap, pbo, dsr),
        "",
    ]

    return "\n".join(lines)


def _pbo_interpretation(pbo: float) -> str:
    if pbo < 0.10:
        return "BAJO riesgo de overfitting — la estrategia es robusta."
    elif pbo < 0.25:
        return "RIESGO MODERADO — posible overfitting, revisar consistencia."
    elif pbo < 0.50:
        return "RIESGO ELEVADO — probable overfitting."
    else:
        return "MUY ALTO riesgo — el rendimiento probablemente es producto del azar."


def _dsr_interpretation(p_val: float) -> str:
    if p_val < 0.01:
        return "ALTAMENTE SIGNIFICATIVO — el Sharpe real supera el azar con >99% confianza."
    elif p_val < 0.05:
        return "SIGNIFICATIVO — el Sharpe real supera el azar con >95% confianza."
    elif p_val < 0.10:
        return "MARGINALMENTE SIGNIFICATIVO — evidencia sugestiva pero no concluyente."
    else:
        return "NO SIGNIFICATIVO — el Sharpe observado es consistente con el azar."


def _build_interpretation(
    metrics: dict[str, Any],
    bootstrap: dict[str, Any],
    pbo: dict[str, Any],
    dsr: dict[str, Any],
) -> str:
    parts = []

    pf = metrics.get("profit_factor")
    sharpe = metrics.get("sharpe_ratio")
    sortino = metrics.get("sortino_ratio")
    win_rate = metrics.get("win_rate")
    var_95 = metrics.get("var_95")
    cvar_95 = metrics.get("cvar_95")
    risk_ruin = metrics.get("risk_of_ruin")
    n = metrics.get("total_trades", 0)

    parts.append(f"**Muestra**: {n} trades.")

    if pf is not None and isinstance(pf, (int, float)):
        if pf > 1.5:
            parts.append(f"Profit Factor {pf:.2f}: BUENO — genera ganancias consistentes.")
        elif pf > 1.0:
            parts.append(f"Profit Factor {pf:.2f}: ACEPTABLE — ligeramente rentable.")
        else:
            parts.append(f"Profit Factor {pf:.2f}: DÉBIL — no cubre pérdidas.")

    if sharpe is not None:
        if sharpe > 2.0:
            parts.append(f"Sharpe {sharpe:.2f}: EXCELENTE.")
        elif sharpe > 1.0:
            parts.append(f"Sharpe {sharpe:.2f}: BUENO.")
        elif sharpe > 0.0:
            parts.append(f"Sharpe {sharpe:.2f}: ACEPTABLE.")
        else:
            parts.append(f"Sharpe {sharpe:.2f}: NEGATIVO — pierde vs risk-free.")

    if sortino is not None:
        if sortino > 2.0:
            parts.append(f"Sortino {sortino:.2f}: Excelente gestión del downside.")
        elif sortino > 1.0:
            parts.append(f"Sortino {sortino:.2f}: Buena gestión del riesgo.")
        else:
            parts.append(f"Sortino {sortino:.2f}: Mejorable.")

    if var_95 is not None:
        parts.append(f"VaR(95%): {var_95:.4f}R por trade — el peor 5% de trades pierde hasta {abs(var_95):.2f}R.")

    if cvar_95 is not None:
        parts.append(f"CVaR(95%): {cvar_95:.4f}R — pérdida esperada en el peor 5%.")

    if risk_ruin is not None:
        if risk_ruin < 0.01:
            parts.append(f"Riesgo de ruina {risk_ruin:.4f}: MUY BAJO — sistema seguro.")
        elif risk_ruin < 0.05:
            parts.append(f"Riesgo de ruina {risk_ruin:.4f}: BAJO.")
        elif risk_ruin < 0.20:
            parts.append(f"Riesgo de ruina {risk_ruin:.4f}: MODERADO — requiere monitoreo.")
        else:
            parts.append(f"Riesgo de ruina {risk_ruin:.4f}: ALTO — sistema vulnerable a rachas perdedoras.")

    bootstrap_win = bootstrap.get("win_rate", {}).get("p5", None) if isinstance(bootstrap.get("win_rate"), dict) else None
    if bootstrap_win is not None:
        parts.append(f"Bootstrap WR P5: {bootstrap_win:.4f} — en el peor 5% de escenarios.")

    if "error" not in pbo:
        pbo_val = pbo.get("pbo", 0.5)
        parts.append(f"PBO: {pbo_val:.2%} — {_pbo_interpretation(pbo_val).lower()}")

    if dsr:
        p_val = dsr.get("dsr_p_value", 0.5)
        parts.append(f"DSR p-value: {p_val:.4f} — {_dsr_interpretation(p_val).lower()}")

    return "  \n".join(parts)
