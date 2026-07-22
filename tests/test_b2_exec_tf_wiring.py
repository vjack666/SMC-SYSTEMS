"""Fase B2 (libro 18) — wiring de exec_tf por el pipeline de backtest.

No es un test de unidad del recalculo (eso ya lo cubre test_b2_exec_tf.py).
Aqui se verifica que el parametro exec_tf NAZCA en run_backtest.py
(CLI / wrapper run) y LLEGA a canonical.evaluate_signals, propagandose
hasta el momento en que entry/SL/TP se reanclan al TF de ejecucion.

Principio (Ruben): un dispatch tras un return, o un parametro que se
pierde en el camino, queda MUERTO aunque el test de la funcion aislada
siga verde. Por eso se prueba el CALL-SITE REAL del pipeline.
"""

import pandas as pd
import pytest

from ict_backtest import run_backtest
from ict_backtest import canonical as canonical_mod


# ---------------------------------------------------------------------------
# Fixture: doble de evaluate_signals que CAPTURA el exec_tf recibido, y
# double de load_frames que EVITA la I/O real de datos (devuelve frames
# minimos con las columnas que detect_market_structure exige). Asi el
# runner no se cuelga cargando parquet y llega rapido al call-site.
# ---------------------------------------------------------------------------
@pytest.fixture
def capture_exec_tf(monkeypatch):
    captured = {}

    def fake_evaluate(symbol, htf, ltf, *args, exec_tf=None, **kwargs):
        captured["exec_tf"] = exec_tf
        return []  # sin senales => backtest termina limpio

    monkeypatch.setattr(run_backtest, "evaluate_signals", fake_evaluate)

    def fake_load_frames(symbol, tf_chain, **kwargs):
        cols = ["time", "open", "high", "low", "close"]
        empty = pd.DataFrame(columns=cols)
        empty["time"] = pd.to_datetime([])
        return {tf: empty.copy() for tf in tf_chain}

    monkeypatch.setattr(run_backtest, "load_frames", fake_load_frames)
    return captured


def test_run_sequence_backtest_propagates_exec_tf(capture_exec_tf):
    """run_sequence_backtest debe pasar exec_tf a evaluate_signals."""
    run_backtest.run_sequence_backtest(
        "EURUSD", "D1", "M15", max_hold=16,
        exec_tf="M5",  # TF de ejecucion fino
    )
    assert capture_exec_tf["exec_tf"] == "M5"


def test_run_sequence_backtest_default_exec_tf_none(capture_exec_tf):
    """Sin exec_tf, el valor por defecto (None) debe llegar intacto."""
    run_backtest.run_sequence_backtest(
        "EURUSD", "D1", "M15", max_hold=16,
    )
    assert capture_exec_tf["exec_tf"] is None


def test_generate_sequence_signals_propagates_exec_tf(capture_exec_tf):
    """El thin-wrapper generate_sequence_signals debe propagar exec_tf."""
    run_backtest.generate_sequence_signals(
        "EURUSD", "D1", "M15", exec_tf="M1",
    )
    assert capture_exec_tf["exec_tf"] == "M1"


def test_run_wrapper_propagates_exec_tf(capture_exec_tf):
    """El wrapper run() (camino por defecto) debe propagar exec_tf."""
    run_backtest.run(
        "EURUSD", "D1", "M15", "intradia", 16, exec_tf="M5",
    )
    assert capture_exec_tf["exec_tf"] == "M5"
