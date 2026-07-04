from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ControlPanel(QWidget):
    start_requested = Signal()
    stop_requested = Signal()
    emergency_stop_requested = Signal()
    config_changed = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("Start")
        self._start_btn.setStyleSheet(
            "background-color: #27ae60; color: white; font-weight: bold;"
        )
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setStyleSheet(
            "background-color: #f39c12; color: white; font-weight: bold;"
        )
        self._stop_btn.setEnabled(False)
        self._emergency_btn = QPushButton("Emergency Stop")
        self._emergency_btn.setStyleSheet(
            "background-color: #e74c3c; color: white; font-weight: bold;"
        )
        self._emergency_btn.setEnabled(False)
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addWidget(self._emergency_btn)
        layout.addLayout(btn_row)

        label_row = QHBoxLayout()
        self._mode_label = QLabel("Mode: PAPER")
        self._status_label = QLabel("Status: STOPPED")
        self._governor_label = QLabel("Governor: --")
        label_row.addWidget(self._mode_label)
        label_row.addWidget(self._status_label)
        label_row.addWidget(self._governor_label)
        layout.addLayout(label_row)

        spin_row = QHBoxLayout()
        spin_row.addWidget(QLabel("Risk %:"))
        self._risk_spin = QDoubleSpinBox()
        self._risk_spin.setRange(0.1, 10.0)
        self._risk_spin.setSingleStep(0.1)
        self._risk_spin.setDecimals(1)
        self._risk_spin.setValue(1.0)
        spin_row.addWidget(self._risk_spin)
        spin_row.addWidget(QLabel("Min Conf:"))
        self._confidence_spin = QDoubleSpinBox()
        self._confidence_spin.setRange(0.1, 0.99)
        self._confidence_spin.setSingleStep(0.05)
        self._confidence_spin.setDecimals(2)
        self._confidence_spin.setValue(0.65)
        spin_row.addWidget(self._confidence_spin)
        layout.addLayout(spin_row)

        sym_row = QHBoxLayout()
        sym_row.addWidget(QLabel("Symbols:"))
        self._symbols_input = QLineEdit("EURUSD, GBPUSD, USDJPY, USDCHF")
        sym_row.addWidget(self._symbols_input)
        layout.addLayout(sym_row)

        self._start_btn.clicked.connect(self._on_start)
        self._stop_btn.clicked.connect(self._on_stop)
        self._emergency_btn.clicked.connect(self._on_emergency)
        self._risk_spin.valueChanged.connect(self._emit_config)
        self._confidence_spin.valueChanged.connect(self._emit_config)
        self._symbols_input.editingFinished.connect(self._emit_config)

    def _on_start(self) -> None:
        self.start_requested.emit()

    def _on_stop(self) -> None:
        self.stop_requested.emit()

    def _on_emergency(self) -> None:
        self.emergency_stop_requested.emit()

    def _emit_config(self) -> None:
        self.config_changed.emit(self._read_config())

    def _read_config(self) -> dict:
        return {
            "risk_percent": self._risk_spin.value(),
            "min_confidence": self._confidence_spin.value(),
            "symbols": [
                s.strip()
                for s in self._symbols_input.text().split(",")
                if s.strip()
            ],
        }

    def connect_worker(self, signals: object) -> None:
        signals.status_changed.connect(self._on_status_changed)
        signals.governor_updated.connect(self._on_governor_updated)


    def _on_status_changed(self, status: str) -> None:
        self._status_label.setText(f"Status: {status}")
        if status == "RUNNING":
            self._start_btn.setEnabled(False)
            self._stop_btn.setEnabled(True)
            self._emergency_btn.setEnabled(True)
        else:
            self._start_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)
            self._emergency_btn.setEnabled(False)

    def _on_governor_updated(self, mode: str, consecutive_losses: int, dd_pct: float) -> None:
        self._governor_label.setText(
            f"Governor: {mode} (losses={consecutive_losses}, dd={dd_pct:.1f}%)"
        )
        colors = {
            "NORMAL": "#27ae60",
            "CAUTION": "#f39c12",
            "DEFENSIVE": "#e67e22",
            "LOCKDOWN": "#e74c3c",
        }
        color = colors.get(mode.upper(), "#95a5a6")
        self._governor_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def set_mode(self, mode: str) -> None:
        self._mode_label.setText(f"Mode: {mode}")

    def load_config(self, config: dict) -> None:
        if "risk_percent" in config:
            self._risk_spin.setValue(config["risk_percent"])
        if "min_confidence" in config:
            self._confidence_spin.setValue(config["min_confidence"])
        if "symbols" in config:
            self._symbols_input.setText(", ".join(config["symbols"]))
        if "mode" in config:
            self.set_mode(config["mode"])
