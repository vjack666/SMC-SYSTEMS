from __future__ import annotations

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QFormLayout, QLabel, QGridLayout


WATCHED_SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD", "USDCHF", "XAUUSD"]
STOCH_COLORS = {"oversold": "cyan", "neutral": "white", "overbought": "magenta"}


class _SymbolRow:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.bid = QLabel("---")
        self.bid.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.ask = QLabel("---")
        self.ask.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.spread = QLabel("---")
        self.spread.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.rsi = QLabel("--")
        self.rsi.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.stoch_status = QLabel("--")
        self.stoch_status.setAlignment(Qt.AlignCenter)
        self.rsi_value: float | None = None
        self.stoch_k: float | None = None

    def widgets(self) -> list[QLabel]:
        return [self.bid, self.ask, self.spread, self.rsi, self.stoch_status]

    def tick(self, bid: float, ask: float) -> None:
        self.bid.setText(f"{bid:.5f}")
        self.ask.setText(f"{ask:.5f}")
        spread_pts = (ask - bid) * (100 if "JPY" in self.symbol else 10000)
        self.spread.setText(f"{spread_pts:.1f}")

    def update_rsi(self, rsi: float) -> None:
        self.rsi_value = rsi
        self.rsi.setText(f"{rsi:.1f}")
        if rsi >= 70:
            self.rsi.setStyleSheet("color: magenta; font-weight: bold;")
        elif rsi <= 30:
            self.rsi.setStyleSheet("color: cyan; font-weight: bold;")
        else:
            self.rsi.setStyleSheet("color: white;")

    def update_stoch(self, k: float, d: float) -> None:
        self.stoch_k = k
        status = "oversold" if k < 20 and d < 20 else "overbought" if k > 80 and d > 80 else "neutral"
        color = STOCH_COLORS[status]
        self.stoch_status.setText(status)
        self.stoch_status.setStyleSheet(f"color: {color}; font-weight: bold;")


class DashboardPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self._trades_today = 0
        self._wins = 0
        self._losses = 0

        self._symbol_rows: dict[str, _SymbolRow] = {}

        self._build_account_group(layout)
        self._build_prices_group(layout)
        self._build_status_group(layout)
        layout.addStretch()

    def _build_account_group(self, parent: QVBoxLayout) -> None:
        group = QGroupBox("Account")
        fl = QFormLayout(group)
        self.balance_label = QLabel("$0.00")
        self.equity_label = QLabel("$0.00")
        self.margin_label = QLabel("$0.00")
        margin_free_label = QLabel("$0.00")
        self.leverage_label = QLabel("1:0")
        self.currency_label = QLabel("---")
        self.server_label = QLabel("---")
        self.login_label = QLabel("---")

        fl.addRow("Balance:", self.balance_label)
        fl.addRow("Equity:", self.equity_label)
        fl.addRow("Margin:", self.margin_label)
        fl.addRow("Free Margin:", margin_free_label)
        fl.addRow("Leverage:", self.leverage_label)
        fl.addRow("Currency:", self.currency_label)
        fl.addRow("Server:", self.server_label)
        fl.addRow("Login:", self.login_label)

        self._margin_free_label = margin_free_label
        parent.addWidget(group)

    def _build_prices_group(self, parent: QVBoxLayout) -> None:
        group = QGroupBox("Live Prices")
        grid = QGridLayout(group)
        headers = ["Symbol", "Bid", "Ask", "Spread", "RSI", "Stoch"]
        for col, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setStyleSheet("font-weight: bold; color: #aaa;")
            grid.addWidget(lbl, 0, col)

        for row_idx, sym in enumerate(WATCHED_SYMBOLS, start=1):
            sym_lbl = QLabel(sym)
            sym_lbl.setStyleSheet("font-weight: bold;")
            grid.addWidget(sym_lbl, row_idx, 0)
            sr = _SymbolRow(sym)
            for col_idx, w in enumerate(sr.widgets(), start=1):
                grid.addWidget(w, row_idx, col_idx)
            self._symbol_rows[sym] = sr

        grid.setColumnStretch(0, 0)
        for c in range(1, 6):
            grid.setColumnStretch(c, 1)
        parent.addWidget(group)

    def _build_status_group(self, parent: QVBoxLayout) -> None:
        group = QGroupBox("System Status")
        fl = QFormLayout(group)

        self.status_label = QLabel("STOPPED")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")

        self.governor_label = QLabel("NORMAL")
        self.governor_label.setStyleSheet("color: green; font-weight: bold;")

        self.trades_label = QLabel("0")
        self.winrate_label = QLabel("0.0%")

        fl.addRow("Status:", self.status_label)
        fl.addRow("Governor:", self.governor_label)
        fl.addRow("Trades Today:", self.trades_label)
        fl.addRow("Win Rate:", self.winrate_label)

        parent.addWidget(group)

    def connect_worker(self, worker_signals) -> None:
        worker_signals.account_updated.connect(self._on_account)
        worker_signals.tick_updated.connect(self._on_tick)
        worker_signals.status_changed.connect(self._on_status)
        worker_signals.governor_updated.connect(self._on_governor)
        worker_signals.chart_data_updated.connect(self._on_chart_data)
        worker_signals.signal_detected.connect(self._on_signal)

    def _on_account(self, info: dict) -> None:
        self.balance_label.setText(f"${info.get('balance', 0):.2f}")
        self.equity_label.setText(f"${info.get('equity', 0):.2f}")
        self.margin_label.setText(f"${info.get('margin', 0):.2f}")
        self._margin_free_label.setText(f"${info.get('margin_free', 0):.2f}")
        self.leverage_label.setText(f"1:{info.get('leverage', 0)}")
        self.currency_label.setText(info.get('currency', '---'))
        self.server_label.setText(info.get('server', '---'))
        self.login_label.setText(str(info.get('login', '---')))

    def _on_tick(self, symbol: str, bid: float, ask: float) -> None:
        row = self._symbol_rows.get(symbol)
        if row:
            row.tick(bid, ask)

    def _on_status(self, status: str) -> None:
        self.status_label.setText(status)
        color_map = {"RUNNING": "green", "STOPPED": "gray", "ERROR": "red"}
        color = color_map.get(status, "gray")
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _on_governor(self, mode: str, losses: int, dd: float) -> None:
        text = f"{mode} (losses={losses}, dd={dd:.2f}%)"
        self.governor_label.setText(text)
        color_map = {"NORMAL": "green", "CAUTION": "gold", "DEFENSIVE": "orange", "LOCKDOWN": "red"}
        color = color_map.get(mode, "white")
        self.governor_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _on_chart_data(self, df) -> None:
        last = df.tail(1)
        if last.empty:
            return
        row = last.iloc[0]
        sym = row.get("symbol", "")
        sr = self._symbol_rows.get(sym)
        if sr is None:
            return
        rsi_col = next((c for c in df.columns if c.lower().startswith("rsi")), None)
        if rsi_col and not pd.isna(row[rsi_col]):
            sr.update_rsi(float(row[rsi_col]))
        if "stoch_k" in df.columns and "stoch_d" in df.columns:
            k = float(row.get("stoch_k", 50))
            d = float(row.get("stoch_d", 50))
            sr.update_stoch(k, d)

    def _on_signal(self, symbol: str, direction: int, confidence: float) -> None:
        self._trades_today += 1
        self._update_trade_stats()

    def record_trade_result(self, won: bool) -> None:
        if won:
            self._wins += 1
        else:
            self._losses += 1
        self._update_trade_stats()

    def _update_trade_stats(self) -> None:
        self.trades_label.setText(str(self._trades_today))
        total = self._wins + self._losses
        rate = (self._wins / total * 100) if total > 0 else 0.0
        self.winrate_label.setText(f"{rate:.1f}%")
