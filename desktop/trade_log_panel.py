from __future__ import annotations

from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from desktop.models import TradeLogTableModel


class TradeFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_text = ""

    def set_filter_text(self, text: str) -> None:
        self._filter_text = text
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        if not self._filter_text:
            return True
        source = self.sourceModel()
        idx = source.index(source_row, 0, source_parent)
        symbol = source.data(idx, Qt.DisplayRole)
        return self._filter_text.lower() in symbol.lower()


class TradeLogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.model = TradeLogTableModel()
        self.proxy = TradeFilterProxy()
        self.proxy.setSourceModel(self.model)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().hide()

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter by symbol...")
        self.filter_input.textChanged.connect(self.proxy.set_filter_text)

        clear_btn = QPushButton("Clear Filters")
        clear_btn.clicked.connect(self._clear_filters)

        title = QLabel("<b>Trade History</b>")
        layout.addWidget(title)

        filter_row = QHBoxLayout()
        filter_row.addWidget(self.filter_input)
        filter_row.addWidget(clear_btn)
        layout.addLayout(filter_row)
        layout.addWidget(self.table)

    def _clear_filters(self) -> None:
        self.filter_input.clear()

    def connect_worker(self, worker_signals) -> None:
        worker_signals.trades_updated.connect(self._on_trades)

    def _on_trades(self, trades: list) -> None:
        self.model.update_trades(trades)
