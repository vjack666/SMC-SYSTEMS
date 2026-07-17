"""Launcher de la app del observador SMC-SYSTEMS.

Setea el sys.path a la raiz del proyecto (no depende del PYTHONPATH del
shell) y arranca la UI con pythonw (sin ventana de consola negra).

Single-instance tipo WhatsApp: si ya hay otro observador abierto, le avisa
que se traiga al frente y este nuevo proceso sale limpio (sin duplicar).
El chequeo se hace DENTRO de main(), despues de crear QApplication, porque
SingleInstanceUi usa QLocalServer (necesita el event loop de Qt vivo).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app_observador.ui.main_window import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
