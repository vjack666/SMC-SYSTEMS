"""tests/test_r10c_semantic_vs_legacy.py — Integration test: semantic vs legacy engine.

Verifies that run_semantic (via adapt_semantic_to_legacy) produces valid
ICTSignal objects when wired through canonical.evaluate_signals.

This is the integration gate: if these tests pass, the semantic engine
is a working replacement for run_sequence in the backtest pipeline.
"""
from __future__ import annotations

import warnings

import pytest


@pytest.fixture(scope="module")
def both_engines():
    """Run both engines on the same XAUUSD H4 data and return results."""
    warnings.filterwarnings("ignore")
    from ict_backtest.canonical import evaluate_signals

    # Legacy engine (run_sequence)
    legacy = evaluate_signals(
        "XAUUSD", "D1", "H4",
        use_semantic=False,
        enable_pd_index=False,
    )

    # Semantic engine (run_semantic + adaptador)
    semantic = evaluate_signals(
        "XAUUSD", "D1", "H4",
        use_semantic=True,
        enable_pd_index=False,
    )

    return legacy, semantic


class TestSemanticEngineIntegration:
    """Verify semantic engine produces valid signals through canonical pipeline."""

    def test_semantic_produces_signals(self, both_engines):
        """Semantic engine should produce at least some signals."""
        _, semantic = both_engines
        assert len(semantic) > 0, "Semantic engine produced 0 signals"

    def test_semantic_signals_are_ict_signal(self, both_engines):
        """Each semantic signal should be a valid ICTSignal dataclass."""
        from ict_backtest.engine import ICTSignal
        _, semantic = both_engines
        for sig in semantic:
            assert isinstance(sig, ICTSignal), f"Not an ICTSignal: {type(sig)}"

    def test_semantic_signals_have_valid_entry(self, both_engines):
        """Entry price should be positive and finite."""
        _, semantic = both_engines
        for sig in semantic:
            assert sig.entry > 0, f"Invalid entry: {sig.entry}"
            assert sig.direction in (1, -1), f"Invalid direction: {sig.direction}"

    def test_semantic_signals_have_sl_and_tp(self, both_engines):
        """SL and TP should be set and logically ordered."""
        _, semantic = both_engines
        for sig in semantic:
            assert sig.stop_loss > 0, f"Invalid SL: {sig.stop_loss}"
            assert sig.take_profit > 0, f"Invalid TP: {sig.take_profit}"
            if sig.direction == 1:
                assert sig.stop_loss < sig.entry < sig.take_profit, (
                    f"Long SL/entry/TP not ordered: {sig.stop_loss}/{sig.entry}/{sig.take_profit}"
                )
            else:
                assert sig.stop_loss > sig.entry > sig.take_profit, (
                    f"Short SL/entry/TP not ordered: {sig.stop_loss}/{sig.entry}/{sig.take_profit}"
                )

    def test_semantic_signals_have_model(self, both_engines):
        """Model should be set to 'sequence' (or future semantic identifier)."""
        _, semantic = both_engines
        for sig in semantic:
            assert sig.model, f"Empty model on signal"

    def test_semantic_vs_legacy_count(self, both_engines):
        """Semantic should produce a comparable number of signals (not 0 vs 100)."""
        legacy, semantic = both_engines
        # Semantic may produce fewer signals (it's stricter on causality)
        # but should not be 0 when legacy has signals
        if len(legacy) > 0:
            assert len(semantic) > 0, (
                f"Legacy produced {len(legacy)} signals but semantic produced 0"
            )

    def test_semantic_legacy_overlap_on_bos_identity(self, both_engines):
        """Legacy signals should be a subset of semantic by (direction, bos_at)."""
        legacy, semantic = both_engines
        if not legacy or not semantic:
            pytest.skip("Not enough signals for overlap test")

        # Build identity keys
        legacy_keys = set()
        for s in legacy:
            legacy_keys.add((s.direction, s.bos_at))

        semantic_keys = set()
        for s in semantic:
            semantic_keys.add((s.direction, s.bos_at))

        # Legacy should be contained in semantic (proven in INFORME_EQUIVALENCIA)
        missing = legacy_keys - semantic_keys
        assert not missing, (
            f"Legacy signals NOT found in semantic: {missing}"
        )
