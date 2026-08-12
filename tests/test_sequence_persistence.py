"""HYP-002 M3 — Persistencia y continuidad del motor (SequenceState).

No mide WR/PF/edge. Solo: round-trip de serializacion y paridad de reinicio
(RUN CONTINUO == SAVE -> CRASH -> LOAD -> RESUME) a nivel de grafo causal.
"""
from __future__ import annotations

from pathlib import Path

from engine.market_object import MarketObject, ObjectType, Role, ObjectState
from engine.expediente import Expediente, PhaseEvent
from engine.sequence import SequenceState, run_sequence_traced, SequenceConfig

from ict_backtest.functional_lab import (
    _make_ltf, _make_htf, _est_htf_fn, audit_restart_parity,
)


def _make_state():
    st = SequenceState()
    st.phase = "BOS_DONE"
    st.direction = 1
    st.sweep_idx = 3
    st.displace_idx = 7
    st.bos_idx = 12
    st.bos_level = 1.2345
    st.zone_high = 1.24
    st.zone_low = 1.22
    st.zone_pd_type = "FVG"
    st.zone_pd_tier = "T2"
    st.htf_aligned = True
    st.htf_reason = "ok"
    st.poi_present = True
    st.invalidation_rules = []  # congeladas en runtime; aqui vacio es valido
    st.history = [("SWEEP", 3, ""), ("DISPLACE", 7, ""), ("BOS", 12, "")]
    st.liquidity_id = "L1"
    st.sweep_id = "S1"
    st.displace_id = "D1"
    st.bos_id = "B1"
    st.poi_id = "P1"
    st.refinement_id = "R1"
    st.entry_id = "E1"
    st.contract_id = "C1"
    st.event_objs = {
        "B1": MarketObject(
            id="B1", symbol="EURUSD", type=ObjectType.BOS, origin_tf="M15",
            role=Role.REFINEMENT, direction=1, zone_high=1.24, zone_low=1.22,
            state=ObjectState.ACTIVE, bar_index=12, bar_time="2026-01-01",
            meta={"phase": "BOS"}),
    }
    st.expediente = Expediente.open(
        symbol="EURUSD", tf="M15", direction=1, birth_idx=3,
        birth_time="2026-01-01", birth_condition="SWEEP_DOWN@LTF")
    st.expediente.advance("BOS", 12, "2026-01-01", event_id="B1", parent_event_id="D1")
    return st


def test_sequence_roundtrip_inmemory():
    st = _make_state()
    snap = st.to_snapshot()
    st2 = SequenceState.from_snapshot(snap)
    # Campos escalares
    assert st2.phase == st.phase
    assert st2.direction == st.direction
    assert st2.bos_level == st.bos_level
    assert st2.zone_pd_type == st.zone_pd_type
    assert st2.history == st.history
    assert st2.bos_id == st.bos_id
    # Objetos
    assert "B1" in st2.event_objs
    assert st2.event_objs["B1"].type == ObjectType.BOS
    assert st2.event_objs["B1"].bar_index == 12
    # Expediente
    assert st2.expediente is not None
    assert st2.expediente.id == st.expediente.id
    assert len(st2.expediente.phase_events) == len(st.expediente.phase_events)
    assert st2.expediente.phase_events[-1].phase == "BOS"
    # Snapshot re-serializado es estable
    assert st2.to_snapshot() == snap


def test_sequence_save_load_disk(tmp_path):
    st = _make_state()
    p = tmp_path / "seq.json"
    st.save(str(p))
    assert p.exists()
    st2 = SequenceState.load(str(p))
    assert st2.to_snapshot() == st.to_snapshot()


def test_restart_parity():
    r = audit_restart_parity(cut=6)
    assert r["pass"] is True, r
    assert r["non_trivial"] is True, r
    assert r["continuous_signals"] > 0, r
    assert r["roundtrip_ok"] is True, r
    assert r["causal_graphs_equal"] is True, r


def test_schema_version_present():
    assert SequenceState.SCHEMA_VERSION == "1.0"
    assert "schema_version" in _make_state().to_snapshot()
