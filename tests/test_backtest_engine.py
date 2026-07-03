from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
import pytest

from smc_successor.backtest import CombinedBacktestConfig, CombinedTrade, metrics_pass_thresholds
from smc_successor.signals import ScalpingSignal


def test_combined_trade_dataclass():
    trade = CombinedTrade(
        symbol="EURUSD",
        entry_time="2024-01-01 00:00:00",
        exit_time="2024-01-01 01:00:00",
        direction=1,
        confidence=0.75,
        entry=1.1000,
        exit=1.1050,
        pnl_r=2.0,
    )
    assert trade.symbol == "EURUSD"
    assert trade.direction == 1
    assert trade.pnl_r == 2.0


def test_metrics_pass_thresholds():
    good = {
        "total_trades": 250,
        "win_rate": 0.55,
        "profit_factor": 1.8,
        "max_drawdown_pct": 5.0,
        "max_daily_drawdown_pct": 2.0,
        "sharpe_ratio": 1.5,
        "expectancy_r": 0.1,
    }
    assert metrics_pass_thresholds(good)

    bad = {
        "total_trades": 50,
        "win_rate": 0.40,
        "profit_factor": 1.0,
        "max_drawdown_pct": 10.0,
        "max_daily_drawdown_pct": 5.0,
        "sharpe_ratio": 0.5,
        "expectancy_r": -0.1,
    }
    assert not metrics_pass_thresholds(bad)


def test_metrics_pass_thresholds_edge_cases():
    assert not metrics_pass_thresholds({})
    assert not metrics_pass_thresholds({"total_trades": 0})


class TestSimulateTrade:
    def _make_frame(self, highs: list[float], lows: list[float]):
        n = len(highs)
        times = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
        return pd.DataFrame({
            "time": times,
            "open": [1.1000] * n,
            "high": highs,
            "low": lows,
            "close": [1.1000] * n,
            "tick_volume": [1000] * n,
        })

    def test_simulate_long_hit_tp(self):
        from smc_successor.backtest.engine import _simulate_trade_with_stats

        frame = self._make_frame(
            highs=[1.1010, 1.1050, 1.1010],
            lows=[1.0995, 1.0995, 1.0995],
        )

        signal = ScalpingSignal(
            symbol="EURUSD",
            time=str(frame["time"].iloc[0]),
            direction=1,
            confidence=0.75,
            entry=1.1000,
            stop_loss=1.0990,
            take_profit=1.1040,
        )

        trade, stats = _simulate_trade_with_stats(frame, signal, max_hold_bars=10)
        assert trade is not None, f"stats={stats}"
        assert stats["exit_reason"] == "TP", f"stats={stats}"
        assert trade.pnl_r > 0

    def test_simulate_long_hit_sl(self):
        from smc_successor.backtest.engine import _simulate_trade_with_stats

        frame = self._make_frame(
            highs=[1.1010, 1.1010, 1.1010],
            lows=[1.0995, 1.0985, 1.0995],
        )

        signal = ScalpingSignal(
            symbol="EURUSD",
            time=str(frame["time"].iloc[0]),
            direction=1,
            confidence=0.75,
            entry=1.1000,
            stop_loss=1.0990,
            take_profit=1.1040,
        )

        trade, stats = _simulate_trade_with_stats(frame, signal, max_hold_bars=10)
        assert trade is not None, f"stats={stats}"
        assert stats["exit_reason"] == "SL", f"stats={stats}"
        assert trade.pnl_r < 0

    def test_simulate_short_hit_tp(self):
        from smc_successor.backtest.engine import _simulate_trade_with_stats

        frame = self._make_frame(
            highs=[1.1005, 1.1005, 1.1005],
            lows=[1.0995, 1.0975, 1.0995],
        )

        signal = ScalpingSignal(
            symbol="EURUSD",
            time=str(frame["time"].iloc[0]),
            direction=-1,
            confidence=0.75,
            entry=1.1000,
            stop_loss=1.1010,
            take_profit=1.0980,
        )

        trade, stats = _simulate_trade_with_stats(frame, signal, max_hold_bars=10)
        assert trade is not None, f"stats={stats}"
        assert stats["exit_reason"] == "TP", f"stats={stats}"
        assert trade.pnl_r > 0

    def test_signal_not_found(self):
        from smc_successor.backtest.engine import _simulate_trade_with_stats

        times = pd.date_range("2024-01-01", periods=10, freq="15min", tz="UTC")
        frame = pd.DataFrame({
            "time": times,
            "open": 1.1000,
            "high": 1.1010,
            "low": 1.0990,
            "close": 1.1000,
            "tick_volume": 1000,
        })

        signal = ScalpingSignal(
            symbol="EURUSD",
            time="2024-06-01 00:00:00",
            direction=1,
            confidence=0.75,
            entry=1.1000,
            stop_loss=1.0990,
            take_profit=1.1040,
        )

        trade, stats = _simulate_trade_with_stats(frame, signal, max_hold_bars=10)
        assert trade is None
        assert stats["exit_reason"] == "time_not_found"


def test_safe_float():
    from smc_successor.backtest.engine import _safe_float

    assert _safe_float(1.5) == 1.5
    assert _safe_float("abc", default=0.0) == 0.0
    assert _safe_float(float("nan"), default=0.0) == 0.0
    assert _safe_float(float("inf"), default=0.0) == 0.0
    assert _safe_float(None, default=0.0) == 0.0


def test_compute_metrics():
    from smc_successor.backtest.engine import _compute_metrics

    trades = pd.DataFrame({
        "symbol": ["EURUSD"] * 5,
        "direction": [1] * 5,
        "pnl_r": [1.0, 1.0, -0.5, 1.0, -0.5],
        "entry_time": pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC"),
    })
    metrics = _compute_metrics(trades)
    assert metrics["total_trades"] == 5
    assert metrics["win_rate"] == 0.6
    assert metrics["profit_factor"] == 3.0 / 1.0
    assert metrics["expectancy_r"] == pytest.approx(0.4)
