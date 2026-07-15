"""tests/test_r7_t32a_consumers.py — T3.2A (R7 Fase 3, TDD), vigente post-T3.2B.

Evidencia automatica de redireccion de consumidores (exigencia del usuario
para T3.2B): en el codigo productivo VIVO NO debe quedar NINGUNA llamada real
a `build_signals_from_frames`. Tras T3.2A se redirigieron los consumidores al
motor canonico; tras T3.2B la funcion fue ELIMINADA de engine.py y este test
debe seguir dando 0 consumidores (la isla ya no existe).

Equivalente Windows al grep pedido:
    findstr /R /S "build_signals_from_frames"  (y revisar que no haya llamadas)

Criterio: se cuentan SOLO llamadas reales  build_signals_from_frames( ...
Se IGNORAN:
  - los imports (build_signals_from_frames,  sin abrir parentesis de llamada)
  - el reexport en __all__ (string, sin parentesis)
  - tests/ y docs/ (no son productivo vivo)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Carpetas excluidas del escaneo de "productivo vivo".
_EXCLUDE_DIRS = {"tests", "docs", ".git", "__pycache__", ".venv", "venv"}


def _is_call(line: str) -> bool:
    s = line.strip()
    if s.startswith("#"):
        return False
    if s.startswith("def build_signals_from_frames"):  # definicion
        return False
    # llamada real: build_signals_from_frames(  (el import es "...," sin abrir)
    return "build_signals_from_frames(" in line


def _consumer_files():
    hits = []
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        if set(Path(rel).parts) & _EXCLUDE_DIRS:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        calls = [i + 1 for i, ln in enumerate(text.splitlines()) if _is_call(ln)]
        if calls:
            hits.append((rel, calls))
    return hits


def test_no_live_consumers_in_productive_code():
    """RED: hoy _smoke.py y plot_trade_structsl.py llaman build_signals_from_frames.
    Tras T3.2A (redirigir al motor canonico) debe quedar en 0.
    """
    hits = _consumer_files()
    assert not hits, (
        "Aun hay consumidores VIVOS de build_signals_from_frames en codigo "
        f"productivo: {hits}. Redirigir a run_sequence (motor canonico) en T3.2A "
        "antes de poder eliminar la funcion en T3.2B."
    )
