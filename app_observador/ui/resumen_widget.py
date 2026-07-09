"""Resumen de estructura del mercado (pestaña Principal).

Muestra en texto plano lo que hace el precio en D1/H4/M15 + Wyckoff M15,
generado desde result['estructura'] (datos reales del motor). Se actualiza
solo en cada ciclo (cuando el mercado cambia de verdad). No inventa nada.
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from app_observador.ui.noticias_widget import resumen_estructura


class ResumenWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        self.title = QLabel("ESTRUCTURA DEL MERCADO")
        self.title.setStyleSheet("color: #7fb3ff; font-weight: bold; font-size: 13px;")
        layout.addWidget(self.title)

        self.lbl = QLabel("calculando...")
        self.lbl.setStyleSheet("color: #ddd; font-size: 13px;")
        self.lbl.setWordWrap(True)
        layout.addWidget(self.lbl, 1)

    def update_state(self, estructura: dict | None = None) -> None:
        if estructura is None:
            self.lbl.setText("Sin datos de estructura (MT5 no disponible).")
            return
        self.lbl.setText(resumen_estructura(estructura))
