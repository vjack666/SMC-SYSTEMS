"""R7 T3.2B — Eliminacion MECANICA de codigo muerto (isla engine).

Aprobado 2026-07-15: T3.2B es SOLO borrado mecanico de build_signals_from_frames
y su consumidor de test asociado. NO introduce cambios conceptuales (R7 congelado).
bos_gap queda registrado como primer candidato R10 (no se toca aqui).

RED -> GREEN:
  RED : hoy engine.build_signals_from_frames EXISTE -> estos asserts fallan.
  GREEN: tras eliminar la isla, los asserts pasan.
"""

import os
import subprocess
import sys

import ict_backtest.engine as engine
import ict_backtest.run_backtest as rb


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _real_calls_in_productive_py():
    """Cuenta llamadas reales build_signals_from_frames( en .py productivo.

    Excluye: definicion (def ...), imports, tests/, docs/.
    Equivalente grep de Windows usado en T3.2A, ahora debe dar 0.
    """
    hits = []
    for root, _dirs, files in os.walk(REPO_ROOT):
        # excluir tests y cualquier dir de documentacion
        rel = os.path.relpath(root, REPO_ROOT)
        parts = rel.split(os.sep)
        if "tests" in parts or "docs" in parts:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            with open(path, encoding="utf-8", errors="ignore") as fh:
                for i, line in enumerate(fh, 1):
                    if "build_signals_from_frames(" in line:
                        # la definicion usa "def build_signals_from_frames("
                        if line.strip().startswith("def "):
                            continue
                        hits.append(f"{path}:{i}: {line.strip()}")
    return hits


def test_build_signals_from_frames_no_existe():
    """La isla engine fue eliminada: el simbolo ya no existe en el modulo."""
    assert not hasattr(engine, "build_signals_from_frames"), (
        "build_signals_from_frames debe haberse ELIMINADO de engine.py (T3.2B)."
    )


def test_cero_consumidores_reales_en_productivo():
    """grep-equivalente: 0 llamadas reales en codigo productivo vivo."""
    hits = _real_calls_in_productive_py()
    assert hits == [], (
        f"Aun hay consumidores VIVOS de build_signals_from_frames en codigo "
        f"productivo:\n" + "\n".join(hits)
    )


def test_api_publica_run_intacta():
    """El contrato de run() (T3.1) sigue siendo la unica fuente; no se rompio."""
    import inspect
    sig = inspect.signature(rb.run)
    params = list(sig.parameters)
    assert params[:3] == ["symbol", "htf", "ltf"], (
        f"Firma run() alterada: {params}"
    )
    # sigue delegando en el motor canonico
    assert hasattr(rb, "run_sequence_backtest"), (
        "run_sequence_backtest (motor canonico) debe seguir existiendo."
    )


def test_isla_no_reexportada_en_init():
    """El __init__ no expone la isla eliminada."""
    import ict_backtest
    assert not hasattr(ict_backtest, "build_signals_from_frames"), (
        "ict_backtest no debe reexportar build_signals_from_frames."
    )
