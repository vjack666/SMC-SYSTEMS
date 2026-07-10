"""Launcher de la app del observador SMC-SYSTEMS.

Setea el sys.path a la raiz del proyecto (no depende del PYTHONPATH del
shell) y arranca la UI con pythonw (sin ventana de consola negra).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Instancia unica de la UI: si ya hay un observador abierto (p.ej. por un
# segundo arranque de sesion / doble login), no duplicamos la ventana.
from scripts._single_instance import ensure_single_instance
ensure_single_instance("observador_ui")

from app_observador.ui.main_window import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
