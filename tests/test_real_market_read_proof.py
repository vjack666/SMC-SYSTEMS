"""Tests de la PRUEBA DE LECTURA REAL (FASES 1/4/5 rapidas; FASE 2 skip).

Valida la infraestructura de evidencia sobre EURUSD real SIN barrer masivamente
(el barrido grande corre como script en background: profile_replay_scaling /
real_market_read_proof con N grande). Aqui solo medimos lo que termina en <30s.

Importa run() en el mismo proceso (sin subprocess) para evitar el doble
import de engine bajo pytest.
"""

from __future__ import annotations

import json
import importlib

import pytest

SYMBOL = "EURUSD"


def _rep(n, start=0):
    mod = importlib.import_module("scripts.real_market_read_proof")
    return mod.run(SYMBOL, n, start)


def test_fase1_rendimiento_real():
    """Sobre 60 velas reales: engine batch y market_replay terminan y son baratos."""
    rep = _rep(60)
    f1 = rep["FASE1_RENDIMIENTO"]
    assert f1["market_replay_steps"] == 59
    # el motor es incremental: seg/vela debe ser pequeno (no ~3s).
    assert f1["seg_per_vela_replay_s"] < 0.5, f"demasiado lento: {f1}"


def test_fase4_no_futuro():
    """El estado en t no incluye velas posteriores (closed-only)."""
    rep = _rep(60)
    assert rep["FASE4_NO_FUTURO"]["ok"] is True


def test_fase5_replay_determinista():
    """Dos corridas independientes dan la misma identidad logica de readouts."""
    rep = _rep(60)
    assert rep["FASE5_REPLAY"]["identidad_logica_igual"] is True


def test_fase2_busqueda_setup_es_skip_sin_barrido_masivo():
    """El barrido masivo (>1000 velas) corre en background, no en el test.

    Razon (FASE 1 real): el ADAPTADOR market_replay (TemporalAvailability ->
    closed_row_at_time) es O(n^2) al rescanear HTF por vela. 3000 velas > 15min.
    El motor SMC es O(1) por vela; el cuello es del adaptador, no de la logica
    de decision. Se deja como script + background. NO se convierte en PASS
    forzando un tramo pequeno.
    """
    pytest.skip(
        "Barrido masivo de EURUSD real corre como script en background "
        "(profile_replay_scaling / real_market_read_proof --n-velas grande). "
        "FASE 2 (lectura real con setup) se demuestra ahi, no en test unitario."
    )
