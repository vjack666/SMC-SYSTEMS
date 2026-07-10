"""Estado del loop, vigilante y cuenta MT5 real (sin inventar numeros).

El estado de los procesos se consulta via tasklist de Windows (sin psutil).
La cuenta se lee de MT5 real via app_observador.core.mt5_status. Si MT5 no
esta conectado, lo dice claramente (no muestra numeros falsos).
"""
from __future__ import annotations

import subprocess
import sys

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from app_observador.config import SYMBOL
from app_observador.core.mt5_status import account_snapshot

_PROC_NAMES = {
    "loop": "loop_analisis.py",
    "vigilante": "vigilante_riesgo.py",
}

# En Windows evita que subprocess abra una consola negra al llamar tasklist.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _proc_running(script_name: str) -> bool:
    """True si el script corre como proceso de Python (Windows tasklist)."""
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq python.exe", "/FO", "CSV"],
            capture_output=True, timeout=5, creationflags=_NO_WINDOW,
        ).stdout.decode("cp1252", errors="replace")
        return script_name in out
    except Exception:
        return False


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
        self.risk_lbl = QLabel("Riesgo día: —")
        for w in (self.loop_lbl, self.vig_lbl, self.acct_lbl, self.risk_lbl):
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

        snap = account_snapshot()
        if snap["conectado"]:
            self.acct_lbl.setText(
                f"Cuenta {snap['login']} | {SYMBOL} | bal {snap['balance']:.2f}")
            self.acct_lbl.setStyleSheet("color: #1f9d55; font-size: 12px;")
            riesgo = snap["riesgo_dia_pct"] or 0.0
            color = "#c0392b" if riesgo >= 2.0 else ("#c9a227" if riesgo >= 1.0 else "#1f9d55")
            self.risk_lbl.setText(f"Riesgo día: {riesgo:.2f}% (DLL 4%)")
            self.risk_lbl.setStyleSheet(f"color: {color}; font-size: 12px;")
        else:
            self.acct_lbl.setText("Cuenta MT5: DESCONECTADA (abrí el terminal)")
            self.acct_lbl.setStyleSheet("color: #888; font-size: 12px;")
            self.risk_lbl.setText("Riesgo día: —")
            self.risk_lbl.setStyleSheet("color: #888; font-size: 12px;")
