"""Sesgo del día + alineación Wyckoff D1/H4/M15 (datos reales de la rutina)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QFrame

_BIAS_COLOR = {
    "LONG": "#1f9d55", "SHORT": "#c0392b", "NEUTRAL": "#c9a227",
}


class SesgoWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        self.title = QLabel("SESGO DEL DÍA + ALINEACIÓN WYCKOFF")
        self.title.setStyleSheet("color: #aaa; font-weight: bold;")
        layout.addWidget(self.title)

        self.bias = QLabel("—")
        self.bias.setStyleSheet("font-size: 18px; font-weight: bold; color: #ccc;")
        layout.addWidget(self.bias)

        self.align = QLabel("")
        self.align.setWordWrap(True)
        self.align.setStyleSheet("color: #ccc; font-size: 12px;")
        layout.addWidget(self.align)
        layout.addStretch()

    def update_state(self, bias: str, wyckoff_m15: dict | None = None) -> None:
        color = _BIAS_COLOR.get("LONG" if bias.startswith("LONG") else
                                 "SHORT" if bias.startswith("SHORT") else "NEUTRAL", "#ccc")
        self.bias.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color};")
        self.bias.setText(f"Sesgo: {bias}")

        if wyckoff_m15:
            fase = wyckoff_m15.get("phase_es", "INDEFINIDA")
            sesgo = wyckoff_m15.get("bias", "—")
            self.align.setText(f"Wyckoff M15: {fase} (sesgo {sesgo})")
        else:
            self.align.setText("Wyckoff M15: —")
