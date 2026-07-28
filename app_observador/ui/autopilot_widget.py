"""Pestaña "Auto" — semi-automatización del grid DEMO.

Un solo botón maestro ON/OFF (default OFF) que enciende/apaga el proceso
scripts/run_demo_grid.py vía process_control (pythonw en background).
El bot se apaga SOLO al cumplir la meta (+$60 o -2% del saldo); un QTimer
de 1s detecta ese auto-apagado y vuelve el botón a OFF.

KISS: toggle + status label + explicación. Nada más.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from app_observador.core import process_control as pc

_BTN_ON = (
    "QPushButton { background-color: #1f6f3f; color: #e8ffe8; font-weight: 800; "
    "font-size: 18px; border: 2px solid #2ecc71; border-radius: 12px; padding: 24px 40px; }"
    "QPushButton:hover { background-color: #268a4d; }"
)
_BTN_OFF = (
    "QPushButton { background-color: #6f2a2a; color: #ffffff; font-weight: 800; "
    "font-size: 18px; border: 2px solid #e74c3c; border-radius: 12px; padding: 24px 40px; }"
    "QPushButton:hover { background-color: #7a3535; }"
)


class AutopilotWidget(QWidget):
    """Master toggle for the DEMO grid bot (run_demo_grid.py)."""

    def __init__(self) -> None:
        super().__init__()
        self._was_on = False

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(18)

        self.btn = QPushButton("OFF")
        self.btn.setStyleSheet(_BTN_OFF)
        self.btn.setMinimumWidth(260)
        self.btn.clicked.connect(self._toggle)
        lay.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignCenter)

        self.lbl_status = QLabel("BOT APAGADO")
        self.lbl_status.setStyleSheet("color: #c7ccd4; font-size: 14px; font-weight: 700;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.lbl_status)

        expl = QLabel("Encendés vos. Se apaga solo al cumplir +$60 o -2% del saldo.")
        expl.setStyleSheet("color: #8a919c; font-size: 12px;")
        expl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        expl.setWordWrap(True)
        lay.addWidget(expl)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(1000)

    # ── acciones ─────────────────────────────────────────────────────
    def _toggle(self) -> None:
        if self._was_on:
            res = pc.stop_script(pc.DEMO_GRID_SCRIPT)
            self._apply_state(res.running, "BOT APAGADO" if res.ok else res.message)
        else:
            res = pc.start_script(pc.DEMO_GRID_SCRIPT)
            self._apply_state(res.running, "BOT ENCENDIDO" if res.running else res.message)

    def _poll(self) -> None:
        running = pc.is_script_running(pc.DEMO_GRID_SCRIPT)
        if self._was_on and not running:
            # Self-shutdown on goal (+$60 / -2%): reflect it in the UI.
            self._apply_state(False, "Meta alcanzada — bot apagado")
        elif running and not self._was_on:
            self._apply_state(True, "BOT ENCENDIDO")

    def _apply_state(self, on: bool, status: str) -> None:
        self._was_on = on
        self.btn.setText("ON" if on else "OFF")
        self.btn.setStyleSheet(_BTN_ON if on else _BTN_OFF)
        self.lbl_status.setText(status)
