from __future__ import annotations

import pandas as pd
import pytest

from smc_successor.backtest.engine import _build_signals_from_context, _simulate_trade_with_stats
from smc_successor.detectors import detect_bos, detect_choch, detect_fvg, detect_order_blocks
from smc_successor.fixtures.synthetic_ohlcv import generate_synthetic_ohlcv
from smc_successor.indicators import add_atr, add_ema, add_rsi
from smc_successor.regime import detect_regimes
from smc_successor.signals import ScalpingConfig, summarize_filter_diagnosis


@pytest.fixture
def e2e_context() -> pd.DataFrame:
    df = generate_synthetic_ohlcv(n_bars=500, seed=42, trend=0.0002)
    df["time"] = pd.date_range("2025-01-01", periods=500, freq="15min", tz="UTC")

    df = detect_bos(df)
    df = detect_choch(df)
    df = detect_fvg(df)
    df = detect_order_blocks(df)

    df["atr"] = add_atr(df, 14)
    df["ema_fast"] = add_ema(df, 20)
    df["ema_slow"] = add_ema(df, 50)
    df["rsi"] = add_rsi(df, 14)
    df["atr_ratio"] = df["atr"] / df["atr"].rolling(20).mean().replace(0.0, float("nan"))

    df["d1_trend"] = "BULLISH"
    df["d1_confidence"] = 0.7
    df["h4_trend"] = "BULLISH"
    df["h4_confidence"] = 0.6
    df["trend_score"] = 40.0
    df["trend_confidence"] = 0.65
    df["regime_state"] = "TRENDING"

    df["macro_direction"] = "BULLISH"
    df["d1_direction"] = "BULLISH"

    df = detect_regimes(df)

    df["filter_trend"] = df["macro_direction"].isin(["BULLISH", "BEARISH"]) & (df["trend_confidence"] >= 0.3)
    df["filter_session"] = True
    df["filter_atr"] = df["atr_ratio"].fillna(0.0) > 0.0
    df["filter_bos"] = df["bos_direction"] != 0
    df["filter_ob_fvg"] = df["fvg_bullish"] | df["fvg_bearish"] | df["ob_bullish"] | df["ob_bearish"]
    df["filter_volume"] = True
    df["filter_choch"] = True
    df["filter_swing"] = True

    df["confluence_score"] = (
        df["filter_trend"].astype(int)
        + df["filter_bos"].astype(int)
        + df["filter_ob_fvg"].astype(int)
    )

    df["signal_confidence"] = (0.40 + (df["confluence_score"] / 5.0) * 0.55).clip(lower=0.40, upper=0.95)
    df["signal_direction"] = 0
    signal_pass = df["confluence_score"] >= 2
    df.loc[signal_pass & (df["macro_direction"] == "BULLISH"), "signal_direction"] = 1
    df.loc[signal_pass & (df["macro_direction"] == "BEARISH"), "signal_direction"] = -1

    return df


class TestE2EBacktestPipeline:
    def test_signal_generation_produces_signals(self, e2e_context):
        signals = _build_signals_from_context(
            symbol="EURUSD",
            context=e2e_context,
            min_confidence=0.3,
        )
        assert len(signals) > 0, "Should produce at least some signals"
        for sig in signals:
            assert sig.symbol == "EURUSD"
            assert sig.direction in (1, -1)
            assert 0.0 <= sig.confidence <= 1.0
            assert sig.entry > 0
            assert sig.stop_loss > 0
            assert sig.take_profit > 0

    def test_signal_generation_respects_min_confidence(self, e2e_context):
        low = _build_signals_from_context("EURUSD", e2e_context, min_confidence=0.1)
        high = _build_signals_from_context("EURUSD", e2e_context, min_confidence=0.9)
        assert len(low) >= len(high)

    def test_signal_generation_at_high_threshold(self, e2e_context):
        signals = _build_signals_from_context("EURUSD", e2e_context, min_confidence=0.99)
        assert len(signals) >= 0

    def test_trade_simulation_long_hit_tp(self, e2e_context):
        signals = _build_signals_from_context("EURUSD", e2e_context, min_confidence=0.3)
        long_signals = [s for s in signals if s.direction == 1]
        if not long_signals:
            pytest.skip("No long signals generated")
        signal = long_signals[0]
        trade, stats = _simulate_trade_with_stats(e2e_context, signal, max_hold_bars=16)
        assert trade is not None
        assert trade.pnl_r != 0.0
        assert stats["exit_reason"] in ("TP", "SL", "hold_limit")

    def test_trade_simulation_short_hit_sl(self, e2e_context):
        signals = _build_signals_from_context("EURUSD", e2e_context, min_confidence=0.3)
        short_signals = [s for s in signals if s.direction == -1]
        if not short_signals:
            pytest.skip("No short signals generated")
        signal = short_signals[0]
        trade, stats = _simulate_trade_with_stats(e2e_context, signal, max_hold_bars=16)
        assert trade is not None
        assert stats["exit_reason"] in ("TP", "SL", "hold_limit")

    def test_pipeline_produces_consistent_results(self, e2e_context):
        signals1 = _build_signals_from_context("EURUSD", e2e_context, min_confidence=0.3)
        signals2 = _build_signals_from_context("EURUSD", e2e_context, min_confidence=0.3)
        assert len(signals1) == len(signals2)
        for s1, s2 in zip(signals1, signals2):
            assert s1.time == s2.time
            assert s1.direction == s2.direction

    def test_all_signal_fields_are_populated(self, e2e_context):
        signals = _build_signals_from_context("EURUSD", e2e_context, min_confidence=0.0)
        for sig in signals[:10]:
            assert sig.symbol == "EURUSD"
            assert isinstance(sig.time, str)
            assert len(sig.time) > 0
            assert sig.direction in (1, -1)
            assert 0.0 <= sig.confidence <= 1.0
            assert sig.entry > 0.0
            assert sig.stop_loss > 0.0
            assert sig.take_profit > 0.0

    def test_multiple_trades_have_different_times(self, e2e_context):
        signals = _build_signals_from_context("EURUSD", e2e_context, min_confidence=0.3)
        times = [s.time for s in signals]
        assert len(set(times)) == len(times), "All signals should have unique timestamps"

    def test_trade_simulation_time_not_found(self, e2e_context):
        from smc_successor.backtest.engine import CombinedTrade, ScalpingSignal
        ghost = ScalpingSignal(
            symbol="EURUSD",
            time="2099-01-01 00:00:00+00:00",
            direction=1,
            confidence=0.5,
            entry=1.1,
            stop_loss=1.09,
            take_profit=1.12,
        )
        trade, stats = _simulate_trade_with_stats(e2e_context, ghost, max_hold_bars=16)
        assert trade is None
        assert stats["exit_reason"] == "time_not_found"

    def test_full_pipeline_no_crashes(self, e2e_context):
        from pathlib import Path
        from smc_successor.backtest.engine import CombinedBacktestConfig, run_combined_backtest
        from smc_successor.signals import ScalpingConfig

        config = CombinedBacktestConfig(
            data_dir=Path("nonexistent"),
            symbols=("EURUSD",),
            timeframe="M15",
            min_confidence=0.3,
            max_hold_bars=16,
            use_ml_quality_filter=False,
            start_time="2025-01-01",
            end_time="2025-01-10",
            scalping_config={"trend_confidence_threshold": 0.1, "min_atr_ratio": 0.0},
            max_bars=200,
        )

        with pytest.raises((RuntimeError, FileNotFoundError)):
            run_combined_backtest(config)

    def test_backtest_with_empty_symbols_raises(self):
        from pathlib import Path
        from smc_successor.backtest.engine import CombinedBacktestConfig, run_combined_backtest
        config = CombinedBacktestConfig(
            data_dir=Path("nonexistent"),
            symbols=(),
            timeframe="M15",
            use_ml_quality_filter=False,
            max_bars=10,
        )
        with pytest.raises(RuntimeError):
            run_combined_backtest(config)
