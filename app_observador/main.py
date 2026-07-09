"""Entry point de la app del observador.

Uso:
  python app_observador/main.py

Requiere PySide6 instalado y MT5 con datos en data/raw (o el loop corriendo).
"""
from __future__ import annotations

import sys

from app_observador.ui.main_window import main

if __name__ == "__main__":
    raise SystemExit(main())
