from __future__ import annotations

from pathlib import Path

import pytest

from smc_successor.detectors import BosConfig, CHOCH_BEARISH, CHOCH_BULLISH, detect_bos, detect_choch, detect_fvg, detect_order_blocks
from smc_successor.fixtures.synthetic_ohlcv import generate_synthetic_ohlcv
from smc_successor.indicators import add_atr, add_ema, add_rsi
from smc_successor.signals import ScalpingConfig, summarize_filter_diagnosis


@pytest.fixture
def synth_frame():
    return generate_synthetic_ohlcv(n_bars=500, seed=42)


class TestDetectors:
    def test_bos_detector_adds_columns(self, synth_frame):
        result = detect_bos(synth_frame)
        assert "bos_direction" in result.columns
        assert "bos_level" in result.columns
        assert "liquidity_sweep_down" in result.columns
        assert "liquidity_sweep_up" in result.columns

    def test_bos_detector_with_config(self, synth_frame):
        cfg = BosConfig(swing_lookback=3, followthrough_bars=5)
        result = detect_bos(synth_frame, cfg)
        assert "bos_direction" in result.columns

    def test_choch_detector_adds_columns(self, synth_frame):
        result = detect_choch(synth_frame)
        assert "choch_signal" in result.columns
        assert set(result["choch_signal"].unique()).issubset({"NONE", CHOCH_BULLISH, CHOCH_BEARISH})

    def test_fvg_detector_adds_columns(self, synth_frame):
        result = detect_fvg(synth_frame)
        assert "fvg_bullish" in result.columns
        assert "fvg_bearish" in result.columns

    def test_ob_detector_adds_columns(self, synth_frame):
        result = detect_order_blocks(synth_frame)
        assert "ob_bullish" in result.columns
        assert "ob_bearish" in result.columns

    def test_indicators(self, synth_frame):
        atr = add_atr(synth_frame, 14)
        assert len(atr) == len(synth_frame)
        ema = add_ema(synth_frame, 20)
        assert len(ema) == len(synth_frame)
        rsi = add_rsi(synth_frame, 14)
        assert len(rsi) == len(synth_frame)

    def test_filter_diagnosis_on_synth_data(self, synth_frame):
        from smc_successor.detectors import detect_bos, detect_choch, detect_fvg, detect_order_blocks
        from smc_successor.indicators import add_atr, add_ema, add_rsi
        from smc_successor.signals.pipeline import _session_filter, _last_anchor

        frame = synth_frame.copy()
        frame = detect_bos(frame)
        frame = detect_choch(frame)
        frame = detect_fvg(frame)
        frame = detect_order_blocks(frame)
        frame["atr"] = add_atr(frame, 14)
        frame["ema_fast"] = add_ema(frame, 20)
        frame["ema_slow"] = add_ema(frame, 50)
        frame["rsi"] = add_rsi(frame, 14)
        frame["atr_ratio"] = frame["atr"] / frame["atr"].rolling(20).mean().replace(0.0, float("nan"))
        frame["macro_direction"] = "RANGING"
        frame["trend_confidence"] = 0.0
        frame["regime_state"] = "RANGING"
        frame["filter_trend"] = False
        frame["filter_session"] = _session_filter(frame["time"], "EURUSD", False)
        frame["filter_atr"] = frame["atr_ratio"].fillna(0.0) > 0.5
        frame["filter_ob_fvg"] = False
        frame["filter_bos"] = False
        frame["filter_volume"] = True
        frame["filter_micro"] = False
        frame["filter_choch"] = True
        frame["filter_swing"] = True
        frame["signal_direction"] = 0
        frame["passed_all_filters"] = False

        confluences = (
            frame["filter_trend"].astype(int)
            + frame["filter_bos"].astype(int)
            + frame["filter_ob_fvg"].astype(int)
            + frame["filter_choch"].astype(int)
            + frame["filter_swing"].astype(int)
        )
        frame["confluence_score"] = confluences
        frame["signal_confidence"] = (0.40 + (confluences / 5.0) * 0.55).clip(lower=0.40, upper=0.95)

        result = summarize_filter_diagnosis(frame)
        assert isinstance(result, dict)
        assert "total_bars" in result
        assert result["total_bars"] > 0


class TestRiskGovernor:
    def test_normal_state(self):
        from smc_successor.risk import GovernorConfig, GovernorState, next_state
        state = GovernorState()
        cfg = GovernorConfig()
        result = next_state(state, cfg)
        assert result.mode == "NORMAL"

    def test_caution_after_losses(self):
        from smc_successor.risk import GovernorConfig, GovernorState, next_state
        state = GovernorState(consecutive_losses=2)
        cfg = GovernorConfig(caution_after_losses=2)
        result = next_state(state, cfg)
        assert result.mode == "CAUTION"

    def test_defensive_after_losses(self):
        from smc_successor.risk import GovernorConfig, GovernorState, next_state
        state = GovernorState(consecutive_losses=3)
        cfg = GovernorConfig(defensive_after_losses=3)
        result = next_state(state, cfg)
        assert result.mode == "DEFENSIVE"

    def test_lockdown_after_losses(self):
        from smc_successor.risk import GovernorConfig, GovernorState, next_state
        state = GovernorState(consecutive_losses=5)
        cfg = GovernorConfig(lockdown_after_losses=5)
        result = next_state(state, cfg)
        assert result.mode == "LOCKDOWN"

    def test_mode_threshold_add(self):
        from smc_successor.risk import mode_threshold_add, mode_risk_multiplier
        assert mode_threshold_add("NORMAL") == 0.0
        assert mode_threshold_add("CAUTION") == 0.03
        assert mode_threshold_add("DEFENSIVE") == 0.08
        assert mode_threshold_add("LOCKDOWN") == 1.00
        assert mode_risk_multiplier("NORMAL") == 1.0
        assert mode_risk_multiplier("CAUTION") == 0.75
        assert mode_risk_multiplier("DEFENSIVE") == 0.50
        assert mode_risk_multiplier("LOCKDOWN") == 0.0

    def test_drawdown_triggers(self):
        from smc_successor.risk import GovernorConfig, GovernorState, next_state
        cfg = GovernorConfig(caution_day_dd=2.0, defensive_day_dd=5.0, lockdown_day_dd=8.0)
        state = GovernorState(day_drawdown_pct=3.0)
        result = next_state(state, cfg)
        assert result.mode == "CAUTION"


class TestRegimeDetector:
    def test_detect_regimes_adds_column(self, synth_frame):
        from smc_successor.regime import detect_regimes
        frame = synth_frame.copy()
        frame["atr"] = add_atr(frame, 14)
        frame["ema_fast"] = add_ema(frame, 20)
        frame["ema_slow"] = add_ema(frame, 50)
        frame["atr_ratio"] = frame["atr"] / frame["atr"].rolling(20).mean().replace(0.0, float("nan"))
        result = detect_regimes(frame)
        assert "market_regime" in result.columns

    def test_classify_row(self, synth_frame):
        from smc_successor.regime import classify_row
        row = synth_frame.iloc[-1]
        result = classify_row(row)
        assert result in ("TRENDING", "RANGING", "HIGH_VOL", "LOW_VOL", "CHAOTIC")


class TestThresholdEngine:
    def test_threshold_for_regime(self):
        from smc_successor.risk import DynamicThresholdConfig, threshold_for_regime
        cfg = DynamicThresholdConfig()
        assert threshold_for_regime("TRENDING", cfg) == pytest.approx(0.60)
        assert threshold_for_regime("HIGH_VOL", cfg) == pytest.approx(0.68)
        assert threshold_for_regime("CHAOTIC", cfg) == pytest.approx(0.75)
        assert threshold_for_regime("LOW_VOL", cfg) == pytest.approx(0.65)
