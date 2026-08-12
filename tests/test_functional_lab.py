"""Test de la bateria de auditoria funcional del motor (HYP-002, FASE 0-10).

No mide WR/PF/edge. Solo comportamiento temporal/operacional del motor real
via research/hypotheses/HYP-002/functional_replay (consumidor puro de engine.*).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPLAY = Path(__file__).resolve().parent.parent / "research" / "hypotheses" / "HYP-002" / "functional_replay"
if str(_REPLAY) not in sys.path:
    sys.path.insert(0, str(_REPLAY))
import functional_replay_battery as fl

ART = Path(__file__).resolve().parent.parent / "research" / "hypotheses" / "HYP-002" / "artifacts"


@pytest.mark.parametrize("n", [12, 250])
def test_fase8_ob_sin_lookahead(n):
    """El OB no debe depender de la vela k+1 (fuga shift(-1) cerrada)."""
    r = fl.audit_ob_causal()
    assert r["pass"] is True, r


def test_fase7_hostile_no_falsa_senal():
    df = fl._make_ltf(250, 40, 44, 46, 50, 80)
    r = fl.audit_hostile(df)
    assert r["pass"] is True, r


def test_fase2_batch_eq_stream_sintetico():
    """Batch == stream en el dataset sintetico (sin leak latente activo)."""
    df = fl._make_ltf(250, 40, 44, 46, 50, 80)
    r = fl.audit_batch_vs_stream(df)
    assert r["feature_leaks"] == 0, r
    # event_divergences puede ser 0 en este dataset; si no, se documenta.
    assert r["event_divergences"] == 0, r


def test_reporte_existe_y_completo():
    rep = json.loads((ART / "lab_report.json").read_text())
    for k in ("FASE2_batch_vs_stream", "FASE3_determinism", "FASE4_temporal_cut",
              "FASE5_future_mutation", "FASE6_restart", "FASE7_hostile",
              "FASE8_intrabar", "FASE9_shadow", "FASE10_crossval"):
        assert k in rep, f"falta {k} en reporte"
