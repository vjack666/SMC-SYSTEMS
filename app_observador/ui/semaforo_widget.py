"""Semáforo FundedNext grande y claro (VERDE / AMARILLO / ROJO + motivo)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame

_COLORS = {
    "VERDE": ("#1f9d55", "🟢 VERDE"),
    "AMARILLO": ("#c9a227", "🟡 AMARILLO"),
    "ROJO": ("#c0392b", "🔴 ROJO"),
}
_DEFAULT = ("#555555", "⚪ SIN DATOS")


class SemaforoWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        self.title = QLabel("SEMÁFORO FUNDEDNEXT")
        self.title.setStyleSheet("color: #aaa; font-weight: bold;")
        layout.addWidget(self.title)

        self.light = QLabel("⚪ SIN DATOS")
        self.light.setAlignment(Qt.AlignCenter)
        self.light.setStyleSheet(
            "background-color: #555555; color: white; font-size: 28px; "
            "font-weight: bold; padding: 14px; border-radius: 8px;"
        )
        layout.addWidget(self.light)

        self.reasons = QLabel("")
        self.reasons.setWordWrap(True)
        self.reasons.setStyleSheet("color: #ccc; font-size: 12px;")
        layout.addWidget(self.reasons)
        layout.addStretch()

    def update_state(self, color: str, reasons: list[str]) -> None:
        bg, text = _COLORS.get(color, _DEFAULT)
        self.light.setStyleSheet(
            f"background-color: {bg}; color: white; font-size: 28px; "
            f"font-weight: bold; padding: 14px; border-radius: 8px;"
        )
        self.light.setText(text)
        self.reasons.setText("\n".join(reasons))
