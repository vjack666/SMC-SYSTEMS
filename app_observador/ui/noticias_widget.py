"""Noticias rojas del día (news_report real)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget


class NoticiasWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        self.title = QLabel("NOTICIAS ROJAS HOY")
        self.title.setStyleSheet("color: #aaa; font-weight: bold;")
        layout.addWidget(self.title)

        self.fuente = QLabel("")
        self.fuente.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.fuente)

        self.list = QListWidget()
        self.list.setStyleSheet("background-color: #1e1e1e; color: #eee;")
        layout.addWidget(self.list)

    def update_state(self, events: list[dict], fuente: str = "") -> None:
        self.list.clear()
        self.fuente.setText(f"Fuente: {fuente}")
        if not events:
            self.list.addItem("Sin noticias rojas en ventana")
            return
        for e in events:
            txt = f"{e.get('currency','')} {e.get('event','')} {e.get('time_utc','')} UTC"
            self.list.addItem(txt)
