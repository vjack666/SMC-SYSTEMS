"""Pestaña ESCÁNER — ficha de precios a un botón (sin automatización).

Reusa el último ciclo del motor y/o fuerza un ciclo fresco.
La ficha es el mismo formato operativo: Entry/SL/TP, OTE, estructura, R:R honesto.
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QCheckBox, QMessageBox,
)

from app_observador.core.scanner_report import build_scanner_report
from app_observador.ui.theme import btn_primary, btn_ghost


class _ScanWorker(QThread):
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, force_fetch: bool = True) -> None:
        super().__init__()
        self._force = force_fetch

    def run(self) -> None:
        try:
            from app_observador.core import engine

            result = engine.run_cycle(force_fetch=self._force)
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class ScannerWidget(QWidget):
    """Tab: generate operator price card on demand."""

    # Emitted when a fresh cycle was requested from this tab (so main window can sync).
    cycle_refreshed = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._last_result: dict | None = None
        self._worker: _ScanWorker | None = None

        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(8, 8, 8, 8)

        title = QLabel("ESCÁNER DE SETUP — ficha de precios")
        title.setStyleSheet("color: #7fb3ff; font-weight: bold; font-size: 14px;")
        root.addWidget(title)

        hint = QLabel(
            "Generá la misma ficha que pedís en chat (Entry/SL/TP, zona OTE, estructura, R:R). "
            "No abre órdenes. Solo números del motor."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #9aa0a6; font-size: 11px;")
        root.addWidget(hint)

        bar = QHBoxLayout()
        self.chk_fresh = QCheckBox("Ciclo fresco (MT5/parquet, ~30–60s)")
        self.chk_fresh.setChecked(False)
        self.chk_fresh.setToolTip(
            "Si está apagado: usa el último ciclo ya cargado en la app (instantáneo).\n"
            "Si está prendido: corre run_cycle de nuevo antes de armar la ficha."
        )
        bar.addWidget(self.chk_fresh)

        self.btn_scan = QPushButton("Generar ficha de precios")
        self.btn_scan.setStyleSheet(btn_primary())
        self.btn_scan.setMinimumHeight(36)
        self.btn_scan.clicked.connect(self._on_scan)
        bar.addWidget(self.btn_scan)

        self.btn_copy = QPushButton("Copiar ficha")
        self.btn_copy.setStyleSheet(btn_ghost())
        self.btn_copy.clicked.connect(self._on_copy)
        bar.addWidget(self.btn_copy)
        bar.addStretch()
        root.addLayout(bar)

        self.status = QLabel("Listo. Pulsá el botón cuando quieras la ficha.")
        self.status.setStyleSheet("color: #9aa0a6; font-size: 11px;")
        root.addWidget(self.status)

        self.out = QPlainTextEdit()
        self.out.setReadOnly(True)
        self.out.setPlaceholderText(
            "Acá aparece la ficha: modelo ICT, Entry/SL/TP, OTE, sweeps, R:R honesto…"
        )
        self.out.setStyleSheet(
            "font-family: Consolas, 'Cascadia Mono', monospace; font-size: 12px;"
        )
        root.addWidget(self.out, 1)

    def update_state(self, result: dict | None) -> None:
        """Keep latest cycle from the main timer (no auto-regenerate)."""
        self._last_result = result

    def last_report_text(self) -> str:
        return self.out.toPlainText().strip()

    def _on_scan(self) -> None:
        if self.chk_fresh.isChecked():
            if self._worker and self._worker.isRunning():
                return
            self.btn_scan.setEnabled(False)
            self.btn_scan.setText("Escaneando…")
            self.status.setText("Corriendo ciclo fresco del motor…")
            self._worker = _ScanWorker(force_fetch=True)
            self._worker.finished.connect(self._on_fresh_done)
            self._worker.failed.connect(self._on_fresh_fail)
            self._worker.start()
            return

        if not self._last_result:
            self.status.setText("Todavía no hay ciclo en memoria. Marcá 'Ciclo fresco' o esperá Actualizar.")
            self.out.setPlainText(build_scanner_report(None))
            return
        text = build_scanner_report(self._last_result)
        self.out.setPlainText(text)
        self.status.setText("Ficha generada desde el último ciclo en memoria.")

    def _on_fresh_done(self, result: dict) -> None:
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("Generar ficha de precios")
        self._last_result = result
        self.out.setPlainText(build_scanner_report(result))
        self.status.setText("Ficha generada con ciclo fresco.")
        self.cycle_refreshed.emit(result)

    def _on_fresh_fail(self, err: str) -> None:
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("Generar ficha de precios")
        self.status.setText(f"Error en ciclo fresco: {err}")
        QMessageBox.warning(self, "Escáner", f"No se pudo correr el ciclo:\n{err}")

    def _on_copy(self) -> None:
        text = self.out.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Copiar", "No hay ficha todavía. Generala primero.")
            return
        QGuiApplication.clipboard().setText(text)
        self.status.setText("Ficha copiada al portapapeles.")
