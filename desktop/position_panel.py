from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QLabel, QTableView, QVBoxLayout, QWidget

from desktop.models import PositionTableModel


class PositionPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.model = PositionTableModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().hide()

        self.summary_label = QLabel("Total P&L: $0.00  Open: 0")

        title = QLabel("<b>Open Positions</b>")
        layout.addWidget(title)
        layout.addWidget(self.table)

        bottom = QHBoxLayout()
        bottom.addWidget(self.summary_label)
        bottom.addStretch()
        layout.addLayout(bottom)

    def connect_worker(self, worker_signals) -> None:
        worker_signals.positions_updated.connect(self._on_positions)

    def _on_positions(self, positions: dict) -> None:
        self.model.update_positions(positions)
        total_pnl = sum(p.get("pnl", 0) for p in positions.values())
        self.summary_label.setText(f"Total P&L: ${total_pnl:.2f}  Open: {len(positions)}")
