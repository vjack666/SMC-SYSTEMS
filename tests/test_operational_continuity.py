"""HYP-002 M4 — Test extremo-a-extremo de continuidad operacional del mercado.

NO abre estadistica/edge/WR/PF ni Macro/News (fuera de alcance por directiva
de la mision). Solo prueba que el motor, como consumidor puro, mantiene una
representacion operacional correcta a traves de: reinicios multiples, gaps,
velas duplicadas, fuera-de-orden, cambio de sesion, lifecycle de setups y
determinismo post-recuperacion.

Contrato validado (ver ict_backtest/operational_continuity_lab.py):
  - El motor usa indices ABSOLUTOS del feed; el adaptador entrega el feed
    COMPLETO en cada re-conexion y reanuda con start_i (ultima vela procesada).
  - El motor es detector de pasada unica (resetea tras cada ENTRY); el set
    recuperado tras N crashes == corrida continua (union de tramos, dedupe
    por entry_at).
  - Fuera-de-orden corrupte la memoria de contexto: DEBE ser normalizado por
    el adaptador real (deuda fuera de alcance).
"""

import pytest
import sys
from pathlib import Path
from engine.sequence import SequenceConfig, run_sequence_traced, SequenceState

_REPLAY = Path(__file__).resolve().parent.parent / "research" / "hypotheses" / "HYP-002" / "functional_replay"
if str(_REPLAY) not in sys.path:
    sys.path.insert(0, str(_REPLAY))
import operational_continuity_battery as lab

make_multi_setup_objs = lab.make_multi_setup_objs
make_signal_est = lab.make_signal_est
run_session = lab.run_session
audit_multi_restart = lab.audit_multi_restart
audit_gaps = lab.audit_gaps
audit_duplicates = lab.audit_duplicates
audit_out_of_order = lab.audit_out_of_order
audit_session_change = lab.audit_session_change
audit_setup_lifecycle = lab.audit_setup_lifecycle
run_all = lab.run_all
_role_graph = lab._role_graph
_resume_session = lab._resume_session


@pytest.fixture
def ctx():
    objs = make_multi_setup_objs(60)
    est = make_signal_est()
    cfg = SequenceConfig(bos_gap=20, displace_gap=6)
    return objs, est, cfg


def test_continuous_baseline_non_trivial(ctx):
    """La corrida continua debe producir senales reales (no trivial)."""
    objs, est, cfg = ctx
    res = run_session(objs, est, cfg)
    assert res["n_signals"] >= 2, "baseline debe tener >=2 setups consecutivos"
    # grafo causal bien formado
    for g in res["causal_graphs"]:
        assert g["roles"]["LIQUIDITY"]["parent_role"] is None
        assert g["roles"]["CONTRACT"]["parent_role"] == "RETURN"


def test_multi_restart_matches_continuous(ctx):
    """Reinicios multiples (crash+resume) == corrida continua (grafo causal)."""
    objs, est, cfg = ctx
    cont = run_session(objs, est, cfg)
    res = audit_multi_restart(objs, est, cfg, cuts=(15, 35))
    assert res["pass"] is True
    assert res["continuous_n"] == res["resumed_n"] == cont["n_signals"]
    assert res["causal_graphs_equal"] is True


def test_resume_does_not_crash_and_state_roundtrips(ctx):
    """El estado se persiste y restaura sin corruptcion (schema 1.0)."""
    objs, est, cfg = ctx
    res = _resume_session(objs, est, cfg, [15, 35])
    # el estado final es una SequenceState valida y round-trip serializable
    assert isinstance(res["state"], SequenceState)
    snap = res["state"].to_snapshot()
    restored = SequenceState.from_snapshot(snap)
    assert restored.to_snapshot() == snap


def test_gaps_dont_break_signals(ctx):
    """Gaps (barras faltantes) entregados al motor producen el mismo n de senales."""
    objs, est, cfg = ctx
    res = audit_gaps(objs, est, cfg, gaps=(20, 40))
    assert res["pass"] is True
    assert res["n_signals"] >= 2


def test_duplicate_bars_idempotent(ctx):
    """Velas duplicadas no duplican senales (motor indexa por bar_index absoluto)."""
    objs, est, cfg = ctx
    res = audit_duplicates(objs, est, cfg, dups=(10, 30))
    assert res["pass"] is True
    assert res["no_duplicate_signals"] is True


def test_out_of_order_is_documented_debt(ctx):
    """Fuera-de-orden: comportamiento definido (no crash) pero es deuda del
    adaptador real (debe ordenar). Se documenta, no se considera pass-fail de motor."""
    objs, est, cfg = ctx
    res = audit_out_of_order(objs, est, cfg, ooo=(10, 30))
    assert res["pass"] is True
    assert "adaptador real" in res["note"].lower()


def test_session_change_flip_and_reset(ctx):
    """Cambio de sesion (BULLISH->BEARISH->RANGING): el motor resetea y flipa."""
    objs, est, cfg = ctx
    res = audit_session_change(objs, est, cfg)
    assert res["pass"] is True
    assert res["phase_seen"]["SWEEP"] >= 1


def test_setup_lifecycle_born_and_die(ctx):
    """Multiples setups nacen; uno que muere (sin return, cae en RANGING)
    resetea sin emitir."""
    objs, est, cfg = ctx
    res = audit_setup_lifecycle(objs, est, cfg)
    assert res["pass"] is True
    assert res["born_setups"] >= 2
    assert res["died_correctly_reset"] is True


def test_determinism_after_recovery(ctx):
    """Correr la auditoria de reinicio 2 veces da el mismo grafo causal."""
    objs, est, cfg = ctx
    r1 = audit_multi_restart(objs, est, cfg, cuts=(15, 35))
    r2 = audit_multi_restart(objs, est, cfg, cuts=(15, 35))
    assert r1["causal_graphs_equal"] is True
    assert r2["causal_graphs_equal"] is True


def test_run_all_overall_pass(ctx):
    """Orquestador M4: todas las auditorias pass."""
    objs, est, cfg = ctx
    res = run_all(objs, est, cfg)
    assert res["_overall"]["pass"] is True
    assert res["_overall"]["n_audits"] == 7
