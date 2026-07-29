"""Mapa ICT embebido: muestra el PNG que genera el engine (save_tf_png).

Performance: FastTransformation + cache de pixmap + refresh solo si visible.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton, QHBoxLayout

from app_observador.config import MAPS_DIR, SYMBOL, TIMEFRAMES


class MapaWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        self.title = QLabel("MAPA ICT (datos reales MT5)")
        self.title.setStyleSheet("color: #aaa; font-weight: bold;")
        layout.addWidget(self.title)

        top_row = QHBoxLayout()
        self.selector = QComboBox()
        self.selector.addItems(TIMEFRAMES)
        self.selector.currentTextChanged.connect(self._on_select)
        top_row.addWidget(self.selector, 1)
        self.btn_regenerate = QPushButton("🔄 Regenerar")
        self.btn_regenerate.setFixedWidth(110)
        self.btn_regenerate.setStyleSheet("background-color: #2a5a2a; color: #fff;")
        self.btn_regenerate.clicked.connect(self._on_regenerate)
        top_row.addWidget(self.btn_regenerate)
        layout.addLayout(top_row)

        self.img = QLabel("Cargando mapa...")
        self.img.setAlignment(Qt.AlignCenter)
        self.img.setStyleSheet("background-color: #000; border: 1px solid #333;")
        self.img.setMinimumHeight(280)
        layout.addWidget(self.img, 1)

        self._tf = TIMEFRAMES[-1]  # M15 por defecto
        self._dirty = True
        self._pix_cache: dict[str, QPixmap] = {}
        self._last_mtime: dict[str, float] = {}
        # Defer first load so tab construction stays light
        QTimer.singleShot(0, lambda: self._show(self._tf))

    def _path(self, tf: str) -> Path:
        return MAPS_DIR / f"{SYMBOL}_{tf}.png"

    def _on_regenerate(self) -> None:
        """Regenera los 4 PNGs bajo demanda y refresca el mapa actual."""
        self.img.setText("Generando mapa...")
        self.img.setPixmap(QPixmap())
        QTimer.singleShot(10, self._do_regenerate)

    def _do_regenerate(self) -> None:
        try:
            from app_observador.core.engine import regenerate_maps
            paths = regenerate_maps()
            if paths.get(self._tf):
                # Invalidar caché local
                self._last_mtime.pop(self._tf, None)
                self._pix_cache.pop(self._tf, None)
                self._show(self._tf)
            else:
                self.img.setText(f"Error generando mapa {self._tf}")
        except Exception as e:
            self.img.setText(f"Error: {e}")

    def _on_select(self, tf: str) -> None:
        self._tf = tf
        self._show(tf)

    def _load_pixmap(self, tf: str) -> QPixmap | None:
        p = self._path(tf)
        if not p.exists():
            return None
        try:
            mtime = p.stat().st_mtime
        except OSError:
            mtime = 0.0
        cached = self._pix_cache.get(tf)
        if cached is not None and self._last_mtime.get(tf) == mtime and not cached.isNull():
            return cached
        pix = QPixmap(str(p))
        if pix.isNull():
            return None
        self._pix_cache[tf] = pix
        self._last_mtime[tf] = mtime
        return pix

    def _show(self, tf: str) -> None:
        pix = self._load_pixmap(tf)
        if pix is None:
            self.img.setText(f"Sin mapa {tf} todavía (ejecutá un ciclo)")
            self.img.setPixmap(QPixmap())
            self._dirty = False
            return
        w = max(self.img.width(), 400)
        h = max(self.img.height(), 280)
        # FastTransformation: tab switches stay snappy (Smooth is CPU-heavy on large PNGs)
        scaled = pix.scaled(
            w,
            h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self.img.setPixmap(scaled)
        self._dirty = False

    def refresh(self) -> None:
        """Mark dirty; paint only if this widget is visible (active tab)."""
        self._dirty = True
        # Drop mtime so next show reloads from disk
        self._last_mtime.pop(self._tf, None)
        self._pix_cache.pop(self._tf, None)
        if self.isVisible():
            self._show(self._tf)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._dirty:
            # Defer one tick so tab animation doesn't jank
            QTimer.singleShot(0, lambda: self._show(self._tf))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        pm = self.img.pixmap()
        if self.isVisible() and pm is not None and not pm.isNull():
            # Cheap re-scale on resize (debounced)
            QTimer.singleShot(80, lambda: self._show(self._tf))
