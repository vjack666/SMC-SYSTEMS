from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractListModel, QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor


class PositionTableModel(QAbstractTableModel):
    COLUMNS = ["Symbol", "Side", "Vol", "Entry", "SL", "TP", "P&L", "Pips", "Status", "Bars"]

    _COLUMN_KEYS = {
        "Symbol": "symbol",
        "Side": "side",
        "Vol": "volume",
        "Entry": "entry_price",
        "SL": "stop_loss",
        "TP": "take_profit",
        "P&L": "pnl",
        "Pips": "pips",
        "Status": "status",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[dict[str, Any]] = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item = self._data[index.row()]
        col = index.column()
        col_name = self.COLUMNS[col]
        key = self._COLUMN_KEYS.get(col_name)
        val = item.get(key) if key else None

        if role == Qt.DisplayRole:
            if key is None or val is None:
                return "-"
            if col_name == "P&L":
                return f"${val:.2f}"
            if col_name in ("Entry", "SL", "TP"):
                return f"{val:.5f}"
            if col_name == "Vol":
                return f"{val:.2f}"
            if col_name == "Pips":
                return f"{val:.1f}"
            return str(val)

        if role == Qt.ForegroundRole:
            if col_name == "P&L":
                pnl = item.get("pnl", 0)
                if pnl > 0:
                    return QColor(0, 180, 0)
                if pnl < 0:
                    return QColor(220, 0, 0)
            if col_name == "Status":
                status = item.get("status", "")
                if "TP" in status or "TAKE_PROFIT" in status:
                    return QColor(0, 180, 0)
                if "SL" in status or "STOP_LOSS" in status:
                    return QColor(220, 0, 0)
                return QColor(128, 128, 128)

        return None

    def update_positions(self, positions: dict[str, dict]) -> None:
        self.beginResetModel()
        self._data = list(positions.values())
        self.endResetModel()


class TradeLogTableModel(QAbstractTableModel):
    COLUMNS = ["Symbol", "Side", "Entry", "Exit", "P&L", "Pips", "RR", "Reason", "Time"]

    _COLUMN_KEYS = {
        "Symbol": "symbol",
        "Side": "side",
        "Entry": "entry_price",
        "Exit": "exit_price",
        "P&L": "pnl",
        "Pips": "pips",
        "Reason": "reason",
        "Time": "close_time",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[dict[str, Any]] = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item = self._data[index.row()]
        col = index.column()
        col_name = self.COLUMNS[col]
        key = self._COLUMN_KEYS.get(col_name)
        val = item.get(key) if key else None

        if role == Qt.DisplayRole:
            if key is None or val is None:
                return "-"
            if col_name == "P&L":
                return f"${val:.2f}"
            if col_name in ("Entry", "Exit"):
                return f"{val:.5f}"
            if col_name == "Pips":
                return f"{val:.1f}"
            return str(val)

        if role == Qt.ForegroundRole:
            if col_name == "P&L":
                pnl = item.get("pnl", 0)
                if pnl > 0:
                    return QColor(0, 180, 0)
                if pnl < 0:
                    return QColor(220, 0, 0)

        return None

    def update_trades(self, trades: list[dict]) -> None:
        self.beginResetModel()
        self._data = list(trades)
        self.endResetModel()


class LogListModel(QAbstractListModel):
    MAX_LOG = 10000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[str] = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            return self._data[index.row()]
        return None

    def append_log(self, msg: str) -> None:
        self.beginInsertRows(QModelIndex(), 0, 0)
        self._data.insert(0, msg)
        self.endInsertRows()
        if len(self._data) > self.MAX_LOG:
            last = len(self._data) - 1
            self.beginRemoveRows(QModelIndex(), last, last)
            self._data.pop()
            self.endRemoveRows()

    def clear(self) -> None:
        self.beginResetModel()
        self._data.clear()
        self.endResetModel()
