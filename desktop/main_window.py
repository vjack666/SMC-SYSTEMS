from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QMenu, QMenuBar,
    QStyle, QSystemTrayIcon, QMessageBox, QVBoxLayout, QWidget,
)

from desktop.chart_widget import ChartWidget
from desktop.control_panel import ControlPanel
from desktop.dashboard_panel import DashboardPanel
from desktop.log_panel import LogPanel
from desktop.position_panel import PositionPanel
from desktop.settings_dialog import SettingsDialog
from desktop.trade_log_panel import TradeLogPanel
from desktop.worker import DataStreamer, TradingWorker, TradingWorkerSignals


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SMC Trading System")
        self.setMinimumSize(1280, 800)
        self.resize(1400, 900)

        # Live data streamer (auto-starts)
        self.streamer = DataStreamer()

        # Trading worker (starts on user action)
        self.worker = TradingWorker()
        self._connect_signals()

        # Central widget with tabs
        self.tabs = QTabWidget()
        self.dashboard = DashboardPanel()
        self.chart_widget = ChartWidget()
        self.positions = PositionPanel()
        self.trades = TradeLogPanel()
        self.log_panel = LogPanel()
        self.control = ControlPanel()

        self.tabs.addTab(self.dashboard, "Dashboard")
        self.tabs.addTab(self.chart_widget, "Chart")
        self.tabs.addTab(self.positions, "Positions")
        self.tabs.addTab(self.trades, "Trade Log")
        self.tabs.addTab(self.log_panel, "Log")
        self.tabs.addTab(self.control, "Control")

        self.setCentralWidget(self.tabs)

        # Connect BOTH streamer and worker to panels
        streamer_signals = self.streamer.signals
        worker_signals = self.worker.signals
        self.dashboard.connect_worker(streamer_signals)
        self.chart_widget.connect_worker(streamer_signals)
        self.log_panel.connect_worker(streamer_signals)
        self.control.connect_worker(worker_signals)

        # Positions/trades only from the trading worker
        self.positions.connect_worker(worker_signals)
        self.trades.connect_worker(worker_signals)

        # Trading worker also updates dashboard when running
        worker_signals.account_updated.connect(self.dashboard._on_account)
        worker_signals.tick_updated.connect(self.dashboard._on_tick)
        worker_signals.status_changed.connect(self.dashboard._on_status)
        worker_signals.governor_updated.connect(self.dashboard._on_governor)
        worker_signals.chart_data_updated.connect(self.chart_widget._on_chart_data)

        # Control panel signals -> worker
        self.control.start_requested.connect(self.worker.start)
        self.control.stop_requested.connect(self.worker.stop)
        self.control.emergency_stop_requested.connect(self.worker.emergency_stop)
        self.control.config_changed.connect(self.worker.update_config)

        # System tray
        self._setup_tray()

        # Menu bar
        self._setup_menu()

        # Auto-start live data streamer
        self.streamer.start()

    def _connect_signals(self) -> None:
        s = self.worker.signals
        s.error_occurred.connect(lambda msg: self._show_error(msg))
        s.status_changed.connect(lambda st: self._update_tray_tooltip(st))

    def _setup_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.tray_icon.setToolTip("SMC Trading System")

        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show/Hide")
        show_action.triggered.connect(self._toggle_visibility)
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.instance().quit)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(lambda reason: self._toggle_visibility() if reason == QSystemTrayIcon.DoubleClick else None)
        self.tray_icon.show()

    def _setup_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        settings_action = file_menu.addAction("Settings")
        settings_action.triggered.connect(self._open_settings)
        file_menu.addSeparator()
        quit_action = file_menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.instance().quit)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.worker.update_config(dialog.get_config())

    def _toggle_visibility(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()
            self.raise_()

    def _update_tray_tooltip(self, status: str) -> None:
        self.tray_icon.setToolTip(f"SMC Trading System — {status}")

    def _show_error(self, msg: str) -> None:
        self.tray_icon.showMessage("SMC Error", msg, QSystemTrayIcon.Critical, 5000)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.streamer.stop()
        self.worker.stop()
        if self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            event.accept()
