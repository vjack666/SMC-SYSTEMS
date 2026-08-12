"""signals/po3.py — SHIM.

La implementación canónica PO3/AMD (A/M/D, build_po3_state, evaluate_po3,
compute_session_open, PO3State) vive en ``engine.po3`` (capa permanente del
motor). Este módulo solo reexporta para no romper imports de la UI del
observador y de los tests. NO es lógica de decisión propia del backtest.
"""

from engine.po3 import (  # noqa: F401
    PO3State,
    build_po3_state,
    compute_session_open,
    evaluate_po3,
)

__all__ = ["PO3State", "build_po3_state", "compute_session_open", "evaluate_po3"]
