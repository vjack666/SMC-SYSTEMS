"""tests/test_r10c_adapter.py — Semantic adapter: format compat + backward compat.

Validates that:
1. adapt_semantic_to_legacy produces dicts with all keys canonical.py expects
2. No information loss (all semantic fields preserved or mapped)
3. Backward compatibility (existing run_semantic tests unaffected)
4. Output is compatible with canonical.evaluate_signals iteration
5. Causal chain tracing (SWEEP root, BOS parent) works correctly
"""
from __future__ import annotations

import pytest

from ict_backtest.market_object import MarketObject, ObjectType, ObjectState, Role
from ict_backtest.semantic_adapter import adapt_semantic_to_legacy


# ---------------------------------------------------------------------------
# Fixtures: synthetic MarketObjects mimicking a real causal chain
# ---------------------------------------------------------------------------

def _make_obj(obj_type: ObjectType, bar_index: int, direction: int = 1,
              zone_high: float = 1.1000, zone_low: float = 1.0950,
              state: ObjectState = ObjectState.ACTIVE,
              parent_id: str | None = None, obj_id: str | None = None,
              meta: dict | None = None) -> MarketObject:
    """Create a synthetic MarketObject for testing."""
    o = MarketObject(
        id=obj_id or f"{obj_type.value}-{bar_index}",
        type=obj_type,
        origin_tf="M15",
        role=Role.REFINEMENT,
        direction=direction,
        zone_high=zone_high,
        zone_low=zone_low,
        state=state,
        bar_index=bar_index,
        meta=meta or {},
    )
    if parent_id:
        o.parent_object = parent_id
    return o


@pytest.fixture
def causal_chain():
    """SWEEP -> BOS -> OB chain (bullish)."""
    sweep = _make_obj(ObjectType.SWEEP, 100, direction=1,
                      zone_high=1.0900, zone_low=1.0850,
                      obj_id="sweep-100")
    bos = _make_obj(ObjectType.BOS, 120, direction=1,
                    zone_high=1.0950, zone_low=1.0900,
                    parent_id="sweep-100", obj_id="bos-120",
                    meta={"breaker_active": True, "breaker_type": "bearish"})
    ob = _make_obj(ObjectType.ORDER_BLOCK, 150, direction=1,
                   zone_high=1.1000, zone_low=1.0950,
                   parent_id="bos-120", obj_id="ob-150")
    return sweep, bos, ob


@pytest.fixture
def semantic_signals(causal_chain):
    """Semantic signal dicts as produced by run_semantic."""
    _, bos, ob = causal_chain
    return [
        {
            "id": "ob-150",
            "root_id": "sweep-100",
            "type": "ORDER_BLOCK",
            "direction": 1,
            "bar_index": 150,
            "entry_at": 155,
            "time": "2025-01-15T10:00:00Z",
            "zone_high": 1.1000,
            "zone_low": 1.0950,
            "narrative_active": True,
            "state": "ACTIVE",
        },
        {
            "id": "bos-120",
            "root_id": "sweep-100",
            "type": "BOS",
            "direction": 1,
            "bar_index": 120,
            "entry_at": 125,
            "time": "2025-01-15T08:00:00Z",
            "zone_high": 1.0950,
            "zone_low": 1.0900,
            "narrative_active": True,
            "state": "ACTIVE",
        },
    ]


# ---------------------------------------------------------------------------
# PARTE 1: Format compatibility — all expected keys present
# ---------------------------------------------------------------------------

class TestFormatCompatibility:
    """Verify that adapt_semantic_to_legacy produces dicts with all keys
    canonical.py expects (direction, entry_at, sweep_at, bos_at, time,
    entry, zone_authority, poi_present, breaker_*, ote_*, smt_*)."""

    EXPECTED_KEYS = {
        "direction", "entry_at", "sweep_at", "bos_at", "time", "entry",
        "zone_authority", "poi_present",
        "breaker_active", "breaker_type", "mitigation_level", "breaker_strength",
        "ote_confirmed", "ote_zone",
        "smt_divergence_active", "smt_divergence_direction", "smt_divergence_strength",
        # backward compat
        "bar_index",
    }

    def test_keys_present(self, semantic_signals, causal_chain):
        _, _, ob = causal_chain
        result = adapt_semantic_to_legacy(semantic_signals, list(causal_chain))
        assert len(result) == 2
        for sig in result:
            missing = self.EXPECTED_KEYS - set(sig.keys())
            assert not missing, f"Missing keys: {missing}"

    def test_types_correct(self, semantic_signals, causal_chain):
        result = adapt_semantic_to_legacy(semantic_signals, list(causal_chain))
        for sig in result:
            assert isinstance(sig["direction"], int)
            assert isinstance(sig["entry_at"], int)
            assert isinstance(sig["time"], str)
            assert isinstance(sig["entry"], float)
            assert sig["sweep_at"] is None or isinstance(sig["sweep_at"], int)
            assert sig["bos_at"] is None or isinstance(sig["bos_at"], int)


# ---------------------------------------------------------------------------
# PARTE 2: Causal chain tracing
# ---------------------------------------------------------------------------

class TestCausalChainTracing:
    """Verify that the adapter correctly traces SWEEP root and BOS parent."""

    def test_ob_traces_to_bos_and_sweep(self, semantic_signals, causal_chain):
        sweep, bos, ob = causal_chain
        result = adapt_semantic_to_legacy(semantic_signals, list(causal_chain))
        ob_legacy = next(s for s in result if s["bar_index"] == 150)
        assert ob_legacy["sweep_at"] == 100, "Should trace root SWEEP"
        assert ob_legacy["bos_at"] == 120, "Should trace immediate BOS parent"

    def test_bos_signal_traces_to_sweep(self, semantic_signals, causal_chain):
        sweep, bos, ob = causal_chain
        result = adapt_semantic_to_legacy(semantic_signals, list(causal_chain))
        bos_legacy = next(s for s in result if s["bar_index"] == 120)
        assert bos_legacy["sweep_at"] == 100, "BOS should trace root SWEEP"
        assert bos_legacy["bos_at"] == 120, "BOS itself is the bos_at"

    def test_direction_preserved(self, semantic_signals, causal_chain):
        result = adapt_semantic_to_legacy(semantic_signals, list(causal_chain))
        for sig in result:
            assert sig["direction"] == 1

    def test_entry_at_from_semantic(self, semantic_signals, causal_chain):
        result = adapt_semantic_to_legacy(semantic_signals, list(causal_chain))
        ob_legacy = next(s for s in result if s["bar_index"] == 150)
        assert ob_legacy["entry_at"] == 155, "entry_at should come from semantic signal"


# ---------------------------------------------------------------------------
# PARTE 3: No information loss
# ---------------------------------------------------------------------------

class TestNoInformationLoss:
    """All semantic fields should be preserved or correctly mapped."""

    def test_bar_index_backward_compat(self, semantic_signals, causal_chain):
        result = adapt_semantic_to_legacy(semantic_signals, list(causal_chain))
        for sig in result:
            assert "bar_index" in sig, "bar_index must be preserved for backward compat"

    def test_semantic_id_preserved_via_bar_index(self, semantic_signals, causal_chain):
        result = adapt_semantic_to_legacy(semantic_signals, list(causal_chain))
        # bar_index preserves the original signal bar
        assert result[0]["bar_index"] == 150  # OB bar
        assert result[1]["bar_index"] == 120  # BOS bar

    def test_meta_propagation(self, semantic_signals, causal_chain):
        """breaker_active from BOS meta should propagate to the OB signal."""
        result = adapt_semantic_to_legacy(semantic_signals, list(causal_chain))
        ob_legacy = next(s for s in result if s["bar_index"] == 150)
        # OB's BOS parent has breaker_active=True in meta
        assert ob_legacy["breaker_active"] is True
        assert ob_legacy["breaker_type"] == "bearish"


# ---------------------------------------------------------------------------
# PARTE 4: Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """Existing run_semantic tests should not break."""

    def test_empty_input_returns_empty(self):
        result = adapt_semantic_to_legacy([], [])
        assert result == []

    def test_none_inputs_return_empty(self):
        result = adapt_semantic_to_legacy(None, None)
        assert result == []

    def test_no_match_skips_signal(self):
        """Signal whose id is not in objs list should be skipped."""
        objs = [_make_obj(ObjectType.SWEEP, 100, obj_id="sweep-100")]
        signals = [{"id": "nonexistent", "root_id": "sweep-100",
                    "type": "BOS", "direction": 1, "bar_index": 120,
                    "entry_at": 125, "time": "t", "zone_high": 1.0,
                    "zone_low": 0.9, "narrative_active": True,
                    "state": "ACTIVE"}]
        result = adapt_semantic_to_legacy(signals, objs)
        assert result == []

    def test_zone_authority_map_used(self, causal_chain):
        from ict_backtest.zone_authority import ZoneAuthority
        zone_auth = ZoneAuthority(
            has_htf_anchor=True, tier="T1", stacking_level=1,
            confidence_weight=0.8, level="PREMIUM",
        )
        signals = [{"id": "ob-150", "root_id": "sweep-100",
                    "type": "ORDER_BLOCK", "direction": 1, "bar_index": 150,
                    "entry_at": 155, "time": "t", "zone_high": 1.0,
                    "zone_low": 0.9, "narrative_active": True,
                    "state": "ACTIVE"}]
        result = adapt_semantic_to_legacy(
            signals, list(causal_chain),
            zone_authority_map={"ob-150": zone_auth},
        )
        assert result[0]["zone_authority"] is zone_auth

    def test_poi_map_used(self, causal_chain):
        signals = [{"id": "ob-150", "root_id": "sweep-100",
                    "type": "ORDER_BLOCK", "direction": 1, "bar_index": 150,
                    "entry_at": 155, "time": "t", "zone_high": 1.0,
                    "zone_low": 0.9, "narrative_active": True,
                    "state": "ACTIVE"}]
        result = adapt_semantic_to_legacy(
            signals, list(causal_chain),
            poi_map={"ob-150": True},
        )
        assert result[0]["poi_present"] is True


# ---------------------------------------------------------------------------
# PARTE 5: Canonical compatibility (integration-style)
# ---------------------------------------------------------------------------

class TestCanonicalCompatibility:
    """Verify that adapted signals are consumable by canonical.evaluate_signals
    iteration (reads direction, entry_at, sweep_at, bos_at, time, entry)."""

    def test_entry_is_float(self, semantic_signals, causal_chain):
        result = adapt_semantic_to_legacy(semantic_signals, list(causal_chain))
        for sig in result:
            assert isinstance(sig["entry"], float)

    def test_sweep_at_is_int_or_none(self, semantic_signals, causal_chain):
        result = adapt_semantic_to_legacy(semantic_signals, list(causal_chain))
        for sig in result:
            v = sig["sweep_at"]
            assert v is None or isinstance(v, int)

    def test_bos_at_is_int_or_none(self, semantic_signals, causal_chain):
        result = adapt_semantic_to_legacy(semantic_signals, list(causal_chain))
        for sig in result:
            v = sig["bos_at"]
            assert v is None or isinstance(v, int)

    def test_time_is_string(self, semantic_signals, causal_chain):
        result = adapt_semantic_to_legacy(semantic_signals, list(causal_chain))
        for sig in result:
            assert isinstance(sig["time"], str)


# ---------------------------------------------------------------------------
# PARTE 6: run_semantic entry_at field
# ---------------------------------------------------------------------------

class TestRunSemanticEntryAt:
    """Verify that run_semantic now includes entry_at in its output."""

    def test_run_semantic_has_entry_at(self):
        """run_semantic output should contain entry_at key."""
        from ict_backtest.event_engine import run_semantic
        from ict_backtest.sequence import SequenceConfig

        # Minimal test with synthetic objects (no DataFrame)
        sweep = _make_obj(ObjectType.SWEEP, 10, direction=1, obj_id="sw")
        bos = _make_obj(ObjectType.BOS, 20, direction=1,
                        parent_id="sw", obj_id="b")
        bos.state = ObjectState.ACTIVE
        sweep.state = ObjectState.ACTIVE

        def est_htf(i):
            return {"trend": "BULLISH"}

        result = run_semantic([sweep, bos], est_htf, SequenceConfig(), ltf_tf="M15")
        # Without ltf_df, entry_at should equal bar_index
        for sig in result:
            assert "entry_at" in sig, "entry_at must be in run_semantic output"
            assert sig["entry_at"] == sig["bar_index"], (
                "Without ltf_df, entry_at should default to bar_index"
            )

    def test_run_semantic_entry_at_with_df(self):
        """When ltf_df is provided, entry_at should reflect the return bar."""
        import pandas as pd
        from ict_backtest.event_engine import run_semantic
        from ict_backtest.sequence import SequenceConfig

        # Create a small DataFrame with price data
        n = 50
        data = {
            "time": pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC"),
            "open": [1.1000 + i * 0.0001 for i in range(n)],
            "high": [1.1010 + i * 0.0001 for i in range(n)],
            "low": [1.0990 + i * 0.0001 for i in range(n)],
            "close": [1.1005 + i * 0.0001 for i in range(n)],
        }
        df = pd.DataFrame(data)

        # Object at bar 10 with zone 1.1020-1.1015
        # Price touches zone around bar 20-25 (high > 1.1015)
        sweep = _make_obj(ObjectType.SWEEP, 5, direction=1, obj_id="sw",
                          zone_high=0, zone_low=0)
        bos = _make_obj(ObjectType.BOS, 10, direction=1, parent_id="sw",
                        obj_id="b", zone_high=1.1020, zone_low=1.1015)
        bos.state = ObjectState.ACTIVE
        sweep.state = ObjectState.ACTIVE

        def est_htf(i):
            return {"trend": "BULLISH"}

        result = run_semantic([sweep, bos], est_htf, SequenceConfig(),
                              ltf_tf="M15", ltf_df=df)
        for sig in result:
            assert "entry_at" in sig
            # entry_at should be >= bar_index (return comes after creation)
            if sig["zone_high"] > 0 and sig["zone_low"] > 0:
                assert sig["entry_at"] >= sig["bar_index"]
