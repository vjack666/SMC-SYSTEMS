from __future__ import annotations

import pandas as pd
import pytest

from smc_successor.agents import (
    AgentOrchestrator,
    DecisionAgent,
    ICTAgent,
    StructureAgent,
    WyckoffAgent,
)
from smc_successor.detectors import detect_bos, detect_choch, detect_displacement, detect_fvg, detect_order_blocks, compute_zones
from smc_successor.fixtures.synthetic_ohlcv import generate_synthetic_ohlcv
from smc_successor.indicators import add_atr, add_ema, add_rsi


def _synthetic_context() -> pd.DataFrame:
    n = 100
    df = pd.DataFrame({
        "time": pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC"),
        "open": [1.10 + i * 0.0001 for i in range(n)],
        "high": [1.10 + i * 0.0002 + 0.001 for i in range(n)],
        "low": [1.10 + i * 0.0001 - 0.001 for i in range(n)],
        "close": [1.10 + i * 0.00015 for i in range(n)],
        "tick_volume": [100 + (i % 20) * 10 for i in range(n)],
        "spread": [1] * n,
    })
    df["atr"] = df["high"] - df["low"]
    df["atr"] = df["atr"].rolling(5, min_periods=1).mean()
    df["swing_label"] = "NONE"
    df["swing_label"].iloc[10] = "HH"
    df["swing_label"].iloc[20] = "HH"
    df["swing_label"].iloc[30] = "LL"
    df["swing_label"].iloc[40] = "HH"
    df["swing_label"].iloc[50] = "HH"
    df["macro_direction"] = "BULLISH"
    df["d1_direction"] = "BULLISH"
    df["h4_trend"] = "BULLISH"
    df["trend_confidence"] = 0.6
    df["bos_direction"] = 1
    df["bos_direction"].iloc[:30] = 1
    df["bos_direction"].iloc[30:60] = -1
    df["bos_direction"].iloc[60:] = 1
    df["choch_signal"] = "NONE"
    df["choch_signal"].iloc[35] = "CHOCH_BEARISH"
    df["fvg_bullish"] = False
    df["fvg_bearish"] = False
    df["fvg_size"] = 0.0
    df["fvg_mid"] = pd.NA
    df["fvg_fill_status"] = "none"
    df["ob_bullish"] = False
    df["ob_bearish"] = False
    df["ob_top"] = pd.NA
    df["ob_bottom"] = pd.NA
    df["ob_distance"] = 99.0
    df["liquidity_sweep_up"] = False
    df["liquidity_sweep_down"] = False
    df["recent_sweep_up"] = False
    df["recent_sweep_down"] = False
    df["displacement_bullish"] = False
    df["displacement_bearish"] = False
    df["premium_discount_zone"] = "DISCOUNT"
    df["market_regime"] = "TRENDING"
    df["volatility_regime"] = "NORMAL"
    df["range_compression"] = 0.8
    df["directional_efficiency"] = 0.6
    df["regime_state"] = "NORMAL"
    df["ema_fast"] = df["close"].rolling(5).mean()
    df["ema_slow"] = df["close"].rolling(10).mean()
    df["rsi"] = 55.0
    df["atr_ratio"] = 1.0
    return df


class TestAgentProtocol:
    def test_ict_agent_returns_analysis(self) -> None:
        ctx = _synthetic_context()
        agent = ICTAgent()
        result = agent.analyze(ctx, len(ctx) - 1)
        assert result.agent_name == "ICT"
        assert result.bias in ("BULLISH", "BEARISH", "NEUTRAL")
        assert 0.0 <= result.confidence <= 0.95
        assert isinstance(result.detected_events, list)
        assert isinstance(result.evidence, dict)
        assert "market_structure" in result.evidence

    def test_wyckoff_agent_returns_analysis(self) -> None:
        ctx = _synthetic_context()
        agent = WyckoffAgent()
        result = agent.analyze(ctx, len(ctx) - 1)
        assert result.agent_name == "WYCKOFF"
        assert result.bias in ("BULLISH", "BEARISH", "NEUTRAL")
        assert 0.0 <= result.confidence <= 0.95
        assert "phase" in result.evidence
        assert "volume_regime" in result.evidence

    def test_structure_agent_returns_analysis(self) -> None:
        ctx = _synthetic_context()
        agent = StructureAgent()
        result = agent.analyze(ctx, len(ctx) - 1)
        assert result.agent_name == "STRUCTURE"
        assert result.bias in ("BULLISH", "BEARISH", "NEUTRAL")
        assert 0.0 <= result.confidence <= 0.95
        assert "trend" in result.evidence
        assert "mtf" in result.evidence

    def test_decision_agent_combines_agents(self) -> None:
        ict = ICTAgent().analyze(_synthetic_context(), 99)
        wyckoff = WyckoffAgent().analyze(_synthetic_context(), 99)
        structure = StructureAgent().analyze(_synthetic_context(), 99)
        decision = DecisionAgent()
        result, record = decision.decide(ict=ict, wyckoff=wyckoff, structure=structure, ml_probability=0.65)
        assert result.agent_name == "DECISION"
        assert result.bias in ("BULLISH", "BEARISH", "NEUTRAL")
        assert 0.0 <= result.confidence <= 0.95
        assert "reasons" in result.evidence
        assert "inputs" in result.evidence
        assert record.final_bias == result.bias
        assert record.confidence == result.confidence
        assert record.ict_bias is not None

    def test_orchestrator_analyze_bar(self) -> None:
        ctx = _synthetic_context()
        orch = AgentOrchestrator()
        result = orch.analyze_bar(ctx, len(ctx) - 1, ml_probability=0.6)
        assert "agent_ict_bias" in result
        assert "agent_wyckoff_bias" in result
        assert "agent_structure_bias" in result
        assert "agent_decision_bias" in result
        assert "agent_decision_confidence" in result
        assert "agent_decision_reasons" in result
        assert "agent_wyckoff_spring" in result
        assert "agent_wyckoff_upthrust" in result
        assert "agent_wyckoff_sos" in result
        assert "agent_wyckoff_sow" in result
        assert "agent_wyckoff_effort_divergence" in result

    def test_orchestrator_analyze_context(self) -> None:
        ctx = _synthetic_context()
        orch = AgentOrchestrator()
        result = orch.analyze_context(ctx)
        assert isinstance(result, pd.DataFrame)
        assert "agent_ict_bias" in result.columns
        assert "agent_wyckoff_phase" in result.columns
        assert "agent_decision_confidence" in result.columns
        assert len(result) == len(ctx)
        dec_conf = result["agent_decision_confidence"].dropna()
        assert len(dec_conf) > 0
        assert all(0.0 <= v <= 1.0 for v in dec_conf)

    def test_decision_with_conflict(self) -> None:
        ctx = _synthetic_context()
        decision = DecisionAgent()
        ict = ICTAgent().analyze(ctx, 99)
        wyckoff = WyckoffAgent().analyze(ctx, 99)
        wyckoff.bias = "BEARISH"
        wyckoff.confidence = 0.7
        ict.bias = "BULLISH"
        ict.confidence = 0.7
        result, record = decision.decide(ict=ict, wyckoff=wyckoff, ml_probability=0.3)
        assert result.confidence < 0.7
        assert "conflict" in str(result.evidence.get("conflicts", []))
        assert record.conflict_penalty_applied > 0.0
        assert record.ml_probability == 0.3

    def test_orchestrator_with_ml_probability(self) -> None:
        ctx = _synthetic_context()
        orch = AgentOrchestrator()
        result = orch.analyze_bar(ctx, len(ctx) - 1, ml_probability=0.8)
        assert result["agent_decision_confidence"] > 0.0
        assert "ML" in str(result.get("agent_decision_reasons", ""))


class TestDetectorColumns:
    def test_fvg_size_column_exists(self) -> None:
        ctx = _synthetic_context()
        assert "fvg_size" in ctx.columns

    def test_ob_distance_column_exists(self) -> None:
        ctx = _synthetic_context()
        assert "ob_distance" in ctx.columns


class TestIntegration:
    def test_displacement_columns_present_after_detection(self) -> None:
        df = generate_synthetic_ohlcv(n_bars=100, seed=42, trend=0.0002)
        df["time"] = pd.date_range("2025-01-01", periods=100, freq="15min", tz="UTC")
        df = detect_displacement(df)
        assert "displacement_bullish" in df.columns
        assert "displacement_bearish" in df.columns
        assert "displacement_magnitude" in df.columns

    def test_zones_columns_present_after_compute(self) -> None:
        df = generate_synthetic_ohlcv(n_bars=100, seed=42, trend=0.0002)
        df["time"] = pd.date_range("2025-01-01", periods=100, freq="15min", tz="UTC")
        df = compute_zones(df)
        assert "premium_discount_zone" in df.columns
        assert "premium_distance" in df.columns
        assert "ote_long_min" in df.columns
        assert "ote_short_min" in df.columns
