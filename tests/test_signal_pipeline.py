from __future__ import annotations

from pathlib import Path

import pytest

from detectors import detect_fvg, detect_order_blocks
from fixtures.synthetic_ohlcv import generate_synthetic_ohlcv
from indicators import add_atr, add_ema, add_rsi
from signals import ScalpingConfig, summarize_filter_diagnosis
from ict_backtest.market_structure import StructureConfig, detect_market_structure


@pytest.fixture
def synth_frame():
    return generate_synthetic_ohlcv(n_bars=500, seed=42)


class TestDetectorsCanonical:
    """BOS/CHOCH ahora vienen del motor canonico (market_structure)."""

    def test_market_structure_adds_columns(self, synth_frame):
        ms = detect_market_structure(synth_frame, StructureConfig(swing_lookback=5, confirm_bars=2))
        assert "bos_dir" in ms.columns
        assert "choch_dir" in ms.columns
        assert "bos_status" in ms.columns

    def test_fvg_detector_adds_columns(self, synth_frame):
        result = detect_fvg(synth_frame)
        assert "fvg_bullish" in result.columns
        assert "fvg_bearish" in result.columns

    def test_ob_detector_adds_columns(self, synth_frame):
        result = detect_order_blocks(synth_frame)
        assert "ob_bullish" in result.columns
        assert "ob_bearish" in result.columns


class TestPipelineIntegration:
    def test_filter_diagnosis_on_synth_data(self, synth_frame):
        from signals.pipeline import _session_filter, _last_anchor

        frame = synth_frame.copy()
        ms = detect_market_structure(frame, StructureConfig(swing_lookback=5, confirm_bars=2))
        frame["bos_dir"] = ms["bos_dir"].values
        frame["choch_dir"] = ms["choch_dir"].values
        frame["bos_direction"] = ms["bos_dir"].map({1: "BULLISH", -1: "BEARISH"}).fillna("NONE").astype(str).values
        frame["choch_signal"] = ms["choch_dir"].map({1: "CHOCH_BULLISH", -1: "CHOCH_BEARISH"}).fillna("NONE").astype(str).values
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
        from risk import GovernorConfig, GovernorState, next_state
        state = GovernorState()
        cfg = GovernorConfig()
        result = next_state(state, cfg)
        assert result.mode == "NORMAL"

    def test_caution_after_losses(self):
        from risk import GovernorConfig, GovernorState, next_state
        state = GovernorState(consecutive_losses=2)
        cfg = GovernorConfig(caution_after_losses=2)
        result = next_state(state, cfg)
        assert result.mode == "CAUTION"

    def test_defensive_after_losses(self):
        from risk import GovernorConfig, GovernorState, next_state
        state = GovernorState(consecutive_losses=3)
        cfg = GovernorConfig(defensive_after_losses=3)
        result = next_state(state, cfg)
        assert result.mode == "DEFENSIVE"

    def test_lockdown_after_losses(self):
        from risk import GovernorConfig, GovernorState, next_state
        state = GovernorState(consecutive_losses=5)
        cfg = GovernorConfig(lockdown_after_losses=5)
        result = next_state(state, cfg)
        assert result.mode == "LOCKDOWN"

    def test_mode_threshold_add(self):
        from risk import mode_threshold_add, mode_risk_multiplier
        assert mode_threshold_add("NORMAL") == 0.0
        assert mode_threshold_add("CAUTION") == 0.03
        assert mode_threshold_add("DEFENSIVE") == 0.08
        assert mode_threshold_add("LOCKDOWN") == 1.00
        assert mode_risk_multiplier("NORMAL") == 1.0
        assert mode_risk_multiplier("CAUTION") == 0.75
        assert mode_risk_multiplier("DEFENSIVE") == 0.50
        assert mode_risk_multiplier("LOCKDOWN") == 0.0

    def test_drawdown_triggers(self):
        from risk import GovernorConfig, GovernorState, next_state
        cfg = GovernorConfig(caution_day_dd=2.0, defensive_day_dd=5.0, lockdown_day_dd=8.0)
        state = GovernorState(day_drawdown_pct=3.0)
        result = next_state(state, cfg)
        assert result.mode == "CAUTION"


class TestRegimeDetector:
    def test_detect_regimes_adds_column(self, synth_frame):
        from regime import detect_regimes
        frame = synth_frame.copy()
        frame["atr"] = add_atr(frame, 14)
        frame["ema_fast"] = add_ema(frame, 20)
        frame["ema_slow"] = add_ema(frame, 50)
        frame["atr_ratio"] = frame["atr"] / frame["atr"].rolling(20).mean().replace(0.0, float("nan"))
        result = detect_regimes(frame)
        assert "market_regime" in result.columns

    def test_classify_row(self, synth_frame):
        from regime import classify_row
        row = synth_frame.iloc[-1]
        result = classify_row(row)
        assert result in ("TRENDING", "RANGING", "HIGH_VOL", "LOW_VOL", "CHAOTIC")
