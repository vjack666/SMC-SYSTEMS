from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop.models import LogListModel


class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.model = LogListModel()
        self.list_view = QListView()
        self.list_view.setModel(self.model)
        self.list_view.setAlternatingRowColors(True)
        self.list_view.setWordWrap(False)
        self.list_view.setSelectionMode(QAbstractItemView.NoSelection)
        self.list_view.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)

        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.Monospace)
        self.list_view.setFont(font)

        self.auto_scroll_cb = QCheckBox("Auto-scroll")
        self.auto_scroll_cb.setChecked(True)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.model.clear)

        title = QLabel("<b>Event Log</b>")
        layout.addWidget(title)
        layout.addWidget(self.list_view)

        bottom = QHBoxLayout()
        bottom.addWidget(self.auto_scroll_cb)
        bottom.addStretch()
        bottom.addWidget(clear_btn)
        layout.addLayout(bottom)

    def connect_worker(self, worker_signals) -> None:
        worker_signals.log_message.connect(self._on_log)

    def _on_log(self, msg: str) -> None:
        self.model.append_log(msg)
        if self.auto_scroll_cb.isChecked():
            self.list_view.scrollToTop()
