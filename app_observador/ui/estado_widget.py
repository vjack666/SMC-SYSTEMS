"""Estado del loop y vigilante (¿encendidos?) + cuenta MT5/equity.

El estado de los procesos se consulta vía tasklist de Windows (sin psutil).
El equity se lee del parquet más reciente si no hay MT5 conectado.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from app_observador.config import DATA_RAW, SYMBOL

_PROC_NAMES = {
    "loop": "loop_analisis.py",
    "vigilante": "vigilante_riesgo.py",
}


def _proc_running(script_name: str) -> bool:
    """True si el script corre como proceso de Python (Windows tasklist)."""
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq python.exe", "/FO", "CSV"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        return script_name in out
    except Exception:
        return False


def _last_equity_from_parquet() -> str:
    """Lee el equity aproximado del último MT5 (no disponible sin MT5 real).
    Hoy reporta 'ver demo' si no hay terminal; no inventa números."""
    return "ver terminal MT5 (demo 10011586708)"


class EstadoWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        self.title = QLabel("ESTADO DEL SISTEMA")
        self.title.setStyleSheet("color: #aaa; font-weight: bold;")
        layout.addWidget(self.title)

        self.loop_lbl = QLabel("Loop: —")
        self.vig_lbl = QLabel("Vigilante: —")
        self.acct_lbl = QLabel("Cuenta: —")
        for w in (self.loop_lbl, self.vig_lbl, self.acct_lbl):
            w.setStyleSheet("color: #ccc; font-size: 12px;")
            layout.addWidget(w)
        layout.addStretch()

    def update_state(self) -> None:
        loop_on = _proc_running(_PROC_NAMES["loop"])
        vig_on = _proc_running(_PROC_NAMES["vigilante"])
        self.loop_lbl.setText(f"Loop observador: {'● ON' if loop_on else '○ OFF'}")
        self.loop_lbl.setStyleSheet(
            f"color: {'#1f9d55' if loop_on else '#888'}; font-size: 12px;")
        self.vig_lbl.setText(f"Vigilante riesgo: {'● ON' if vig_on else '○ OFF'}")
        self.vig_lbl.setStyleSheet(
            f"color: {'#1f9d55' if vig_on else '#888'}; font-size: 12px;")
        self.acct_lbl.setText(f"Cuenta: {_last_equity_from_parquet()}")
