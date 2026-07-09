"""Mapa ICT embebido: muestra el PNG que genera el engine (save_tf_png).

El PNG ya tiene Order Blocks, FVG, Liquidez, Killzones y zonas pintadas por
mapa_precio.py con datos reales. Este widget lo carga y lo muestra escalado,
conservando la relación de aspecto. Sin mock: si el PNG no existe, lo dice.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox

from app_observador.config import MAPS_DIR, SYMBOL, TIMEFRAMES


class MapaWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        self.title = QLabel("MAPA ICT (datos reales MT5)")
        self.title.setStyleSheet("color: #aaa; font-weight: bold;")
        layout.addWidget(self.title)

        self.selector = QComboBox()
        self.selector.addItems(TIMEFRAMES)
        self.selector.currentTextChanged.connect(self._on_select)
        layout.addWidget(self.selector)

        self.img = QLabel("Cargando mapa...")
        self.img.setAlignment(Qt.AlignCenter)
        self.img.setStyleSheet("background-color: #000; border: 1px solid #333;")
        self.img.setMinimumHeight(280)
        layout.addWidget(self.img, 1)

        self._tf = TIMEFRAMES[-1]  # M15 por defecto
        self._show(self._tf)

    def _path(self, tf: str) -> Path:
        return MAPS_DIR / f"{SYMBOL}_{tf}.png"

    def _on_select(self, tf: str) -> None:
        self._tf = tf
        self._show(tf)

    def _show(self, tf: str) -> None:
        p = self._path(tf)
        if not p.exists():
            self.img.setText(f"Sin mapa {tf} todavía (ejecutá un ciclo)")
            return
        pix = QPixmap(str(p))
        if pix.isNull():
            self.img.setText(f"No se pudo cargar {p.name}")
            return
        scaled = pix.scaled(
            self.img.width() or 600, self.img.height() or 320,
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
        )
        self.img.setPixmap(scaled)

    def refresh(self) -> None:
        """El engine regeneró los PNG; recarga el actual."""
        self._show(self._tf)
