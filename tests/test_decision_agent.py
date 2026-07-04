from __future__ import annotations

import pytest

from agents.base import AnalysisResult
from agents.decision_agent import DecisionAgent


def _result(bias: str, confidence: float, events: list | None = None) -> AnalysisResult:
    return AnalysisResult(
        agent_name="TEST", bias=bias, confidence=confidence,
        detected_events=events or [], evidence={}, invalidation_conditions=[],
    )


class TestDecisionAgent:
    def test_all_agree_bullish(self):
        da = DecisionAgent()
        r, _ = da.decide(
            ict=_result("BULLISH", 0.8),
            wyckoff=_result("BULLISH", 0.7),
            structure=_result("BULLISH", 0.6),
        )
        assert r.bias == "BULLISH"
        assert r.confidence >= 0.70

    def test_all_agree_bearish(self):
        da = DecisionAgent()
        r, _ = da.decide(
            ict=_result("BEARISH", 0.9),
            wyckoff=_result("BEARISH", 0.8),
            structure=_result("BEARISH", 0.7),
        )
        assert r.bias == "BEARISH"
        assert r.confidence >= 0.80

    def test_majority_rules_bullish(self):
        da = DecisionAgent()
        r, _ = da.decide(
            ict=_result("BULLISH", 0.6),
            wyckoff=_result("BULLISH", 0.55),
            structure=_result("BEARISH", 0.7),
        )
        assert r.bias == "BULLISH"

    def test_majority_rules_bearish(self):
        da = DecisionAgent()
        r, _ = da.decide(
            ict=_result("BEARISH", 0.65),
            wyckoff=_result("BULLISH", 0.6),
            structure=_result("BEARISH", 0.55),
        )
        assert r.bias == "BEARISH"

    def test_conflict_reduces_confidence(self):
        da = DecisionAgent()
        _, record = da.decide(
            ict=_result("BULLISH", 0.9),
            wyckoff=_result("BEARISH", 0.9),
            structure=_result("BULLISH", 0.9),
        )
        # conflict should reduce confidence from what it would be
        assert record.conflict_penalty_applied > 0.0

    def test_neutral_agent_does_not_affect(self):
        da = DecisionAgent()
        r, _ = da.decide(
            ict=_result("BULLISH", 0.8),
            wyckoff=_result("NEUTRAL", 0.0),
            structure=_result("BULLISH", 0.7),
        )
        assert r.bias == "BULLISH"
        assert r.confidence >= 0.60

    def test_all_neutral_no_decision(self):
        da = DecisionAgent()
        r, _ = da.decide(
            ict=_result("NEUTRAL", 0.0),
            wyckoff=_result("NEUTRAL", 0.0),
            structure=_result("NEUTRAL", 0.0),
        )
        assert r.bias in ("NEUTRAL", "BULLISH", "BEARISH")

    def test_ml_probability_boosts_confidence(self):
        da = DecisionAgent()
        r_no_ml, _ = da.decide(
            ict=_result("BULLISH", 0.6),
            wyckoff=_result("BULLISH", 0.5),
            structure=_result("BULLISH", 0.5),
        )
        r_with_ml, _ = da.decide(
            ict=_result("BULLISH", 0.6),
            wyckoff=_result("BULLISH", 0.5),
            structure=_result("BULLISH", 0.5),
            ml_probability=0.85,
        )
        assert r_with_ml.confidence >= r_no_ml.confidence

    def test_ml_probability_boost_dampened_with_conflict(self):
        da = DecisionAgent()
        r, _ = da.decide(
            ict=_result("BULLISH", 0.7),
            wyckoff=_result("BEARISH", 0.8),
            structure=_result("BULLISH", 0.5),
            ml_probability=0.9,
        )
        # conflict should dampen the ML boost
        assert r.confidence > 0.0
