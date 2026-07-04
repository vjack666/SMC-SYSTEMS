from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Trading Settings")
        self.setMinimumWidth(500)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_general_tab(), "General")
        self._tabs.addTab(self._build_risk_tab(), "Risk")
        self._tabs.addTab(self._build_pipeline_tab(), "Pipeline")
        self._tabs.addTab(self._build_data_tab(), "Data")
        layout.addWidget(self._tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_general_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        self._timeframe_combo = QComboBox()
        self._timeframe_combo.addItems(["M1", "M5", "M15", "M30", "H1", "H4"])
        form.addRow("Timeframe:", self._timeframe_combo)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["PAPER", "LIVE"])
        form.addRow("Mode:", self._mode_combo)

        self._symbols_list = QListWidget()
        self._symbols_list.addItems(["EURUSD", "GBPUSD", "USDJPY", "USDCHF"])
        form.addRow("Symbols:", self._symbols_list)

        return widget

    def _build_risk_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        self._risk_spin = QDoubleSpinBox()
        self._risk_spin.setRange(0.1, 10.0)
        self._risk_spin.setSingleStep(0.1)
        self._risk_spin.setDecimals(1)
        self._risk_spin.setValue(1.0)
        form.addRow("Risk %:", self._risk_spin)

        self._confidence_spin = QDoubleSpinBox()
        self._confidence_spin.setRange(0.1, 0.99)
        self._confidence_spin.setSingleStep(0.05)
        self._confidence_spin.setDecimals(2)
        self._confidence_spin.setValue(0.65)
        form.addRow("Min Confidence:", self._confidence_spin)

        self._commission_spin = QDoubleSpinBox()
        self._commission_spin.setRange(0.0, 100.0)
        self._commission_spin.setSingleStep(0.1)
        self._commission_spin.setDecimals(2)
        self._commission_spin.setValue(0.0)
        form.addRow("Commission / Lot:", self._commission_spin)

        return widget

    def _build_pipeline_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        self._trend_spin = QDoubleSpinBox()
        self._trend_spin.setRange(0.0, 100.0)
        self._trend_spin.setSingleStep(1.0)
        self._trend_spin.setDecimals(1)
        self._trend_spin.setValue(25.0)
        form.addRow("Trend Threshold:", self._trend_spin)

        self._confluence_spin = QSpinBox()
        self._confluence_spin.setRange(1, 10)
        self._confluence_spin.setValue(2)
        form.addRow("Min Confluence:", self._confluence_spin)

        self._atr_ratio_spin = QDoubleSpinBox()
        self._atr_ratio_spin.setRange(0.1, 5.0)
        self._atr_ratio_spin.setSingleStep(0.1)
        self._atr_ratio_spin.setDecimals(1)
        self._atr_ratio_spin.setValue(0.8)
        form.addRow("Min ATR Ratio:", self._atr_ratio_spin)

        self._ob_proximity_spin = QDoubleSpinBox()
        self._ob_proximity_spin.setRange(0.0, 100.0)
        self._ob_proximity_spin.setSingleStep(1.0)
        self._ob_proximity_spin.setDecimals(1)
        self._ob_proximity_spin.setValue(10.0)
        form.addRow("OB/FVG Proximity:", self._ob_proximity_spin)

        self._relaxed_bos = QCheckBox("Relaxed BOS")
        form.addRow("", self._relaxed_bos)

        return widget

    def _build_data_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        self._bars_spin = QSpinBox()
        self._bars_spin.setRange(100, 10000)
        self._bars_spin.setSingleStep(100)
        self._bars_spin.setValue(1000)
        form.addRow("Bars for Pipeline:", self._bars_spin)

        data_dir_layout = QHBoxLayout()
        self._data_dir_input = QLineEdit("data/raw")
        browse_data = QPushButton("...")
        browse_data.clicked.connect(self._browse_data_dir)
        data_dir_layout.addWidget(self._data_dir_input)
        data_dir_layout.addWidget(browse_data)
        form.addRow("Data Dir:", data_dir_layout)

        state_dir_layout = QHBoxLayout()
        self._state_dir_input = QLineEdit("data/state")
        browse_state = QPushButton("...")
        browse_state.clicked.connect(self._browse_state_dir)
        state_dir_layout.addWidget(self._state_dir_input)
        state_dir_layout.addWidget(browse_state)
        form.addRow("State Dir:", state_dir_layout)

        return widget

    def _browse_data_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "Select Data Directory", self._data_dir_input.text()
        )
        if d:
            self._data_dir_input.setText(d)

    def _browse_state_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "Select State Directory", self._state_dir_input.text()
        )
        if d:
            self._state_dir_input.setText(d)

    def get_config(self) -> dict:
        symbols = [self._symbols_list.item(i).text() for i in range(self._symbols_list.count())]
        return {
            "timeframe": self._timeframe_combo.currentText(),
            "mode": self._mode_combo.currentText(),
            "symbols": symbols,
            "risk_percent": self._risk_spin.value(),
            "min_confidence": self._confidence_spin.value(),
            "commission_per_lot": self._commission_spin.value(),
            "trend_threshold": self._trend_spin.value(),
            "min_confluence": self._confluence_spin.value(),
            "min_atr_ratio": self._atr_ratio_spin.value(),
            "ob_fvg_proximity": self._ob_proximity_spin.value(),
            "relaxed_bos": self._relaxed_bos.isChecked(),
            "bars_for_pipeline": self._bars_spin.value(),
            "data_dir": self._data_dir_input.text(),
            "state_dir": self._state_dir_input.text(),
        }

    def load_config(self, config: dict) -> None:
        if "timeframe" in config:
            idx = self._timeframe_combo.findText(config["timeframe"])
            if idx >= 0:
                self._timeframe_combo.setCurrentIndex(idx)
        if "mode" in config:
            idx = self._mode_combo.findText(config["mode"])
            if idx >= 0:
                self._mode_combo.setCurrentIndex(idx)
        if "symbols" in config:
            self._symbols_list.clear()
            self._symbols_list.addItems(config["symbols"])
        if "risk_percent" in config:
            self._risk_spin.setValue(config["risk_percent"])
        if "min_confidence" in config:
            self._confidence_spin.setValue(config["min_confidence"])
        if "commission_per_lot" in config:
            self._commission_spin.setValue(config["commission_per_lot"])
        if "trend_threshold" in config:
            self._trend_spin.setValue(config["trend_threshold"])
        if "min_confluence" in config:
            self._confluence_spin.setValue(config["min_confluence"])
        if "min_atr_ratio" in config:
            self._atr_ratio_spin.setValue(config["min_atr_ratio"])
        if "ob_fvg_proximity" in config:
            self._ob_proximity_spin.setValue(config["ob_fvg_proximity"])
        if "relaxed_bos" in config:
            self._relaxed_bos.setChecked(config["relaxed_bos"])
        if "bars_for_pipeline" in config:
            self._bars_spin.setValue(config["bars_for_pipeline"])
        if "data_dir" in config:
            self._data_dir_input.setText(config["data_dir"])
        if "state_dir" in config:
            self._state_dir_input.setText(config["state_dir"])
