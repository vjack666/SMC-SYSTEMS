from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from PySide6.QtCore import QObject, QThread, Signal, Slot

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.mt5.connector import MT5Connector
from paper_trading.models import PaperPosition, PositionSide, PositionStatus, TradeMode
from paper_trading.persistence import load_positions, save_positions, save_trade_log
from paper_trading.runner import PaperTradingRunner
from risk.governor import GovernorConfig, GovernorState, next_state
from signals.pipeline import ScalpingConfig


class TradingWorkerSignals(QObject):
    log_message = Signal(str)
    positions_updated = Signal(dict)
    trades_updated = Signal(list)
    account_updated = Signal(dict)
    governor_updated = Signal(str, int, float)
    tick_updated = Signal(str, float, float)
    status_changed = Signal(str)
    signal_detected = Signal(str, int, float)
    error_occurred = Signal(str)
    chart_data_updated = Signal(object)


class DataStreamer(QObject):
    """Lightweight worker that streams live market data without running the trading pipeline.
    Starts automatically with the app — shows prices, account info, and chart data immediately."""

    def __init__(
        self,
        symbols: list[str] | None = None,
        timeframe: str = "M15",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.signals = TradingWorkerSignals(self)
        self.symbols = symbols or ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
        self.timeframe = timeframe
        self._thread: QThread | None = None
        self._running = False
        self._mt5_ok = False
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.started.connect(self._run)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)

    def _run(self) -> None:
        import MetaTrader5 as mt5
        if not mt5.terminal_info():
            if not mt5.initialize():
                self.signals.log_message.emit("ERROR: MT5 not running — no live data")
                self.signals.status_changed.emit("MT5 DISCONNECTED")
                self._running = False
                return

        info = mt5.account_info()
        if info:
            self._mt5_ok = True
            self.signals.account_updated.emit({
                "login": info.login, "balance": info.balance, "equity": info.equity,
                "margin_free": info.margin_free, "margin_level": info.margin_level,
                "leverage": info.leverage, "currency": info.currency,
                "name": info.name, "server": info.server,
            })
            self.signals.log_message.emit(f"Connected: {info.server} ({info.login})")
        else:
            self.signals.log_message.emit("MT5 connected but no account info")

        self.signals.status_changed.emit("LIVE DATA")
        self.signals.log_message.emit(f"Streaming {len(self.symbols)} symbols on {self.timeframe}")

        while self._running:
            for symbol in self.symbols:
                try:
                    tick = mt5.symbol_info_tick(symbol)
                    if tick:
                        self.signals.tick_updated.emit(symbol, float(tick.bid), float(tick.ask))
                except Exception:
                    pass
            time.sleep(5)


class TradingWorker(QObject):
    def __init__(
        self,
        symbols: list[str] | None = None,
        timeframe: str = "M15",
        mode: TradeMode = TradeMode.PAPER,
        risk_percent: float = 1.0,
        min_confidence: float = 0.65,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.signals = TradingWorkerSignals(self)
        self.symbols = symbols or ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
        self.timeframe = timeframe
        self.mode = mode
        self.risk_percent = risk_percent
        self.min_confidence = min_confidence
        self._runner: PaperTradingRunner | None = None
        self._thread: QThread | None = None
        self._running = False
        self._paused = False

    @Slot()
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.started.connect(self._run_loop)
        self._thread.start()
        self.signals.status_changed.emit("RUNNING")

    @Slot()
    def stop(self) -> None:
        self._running = False
        if self._runner:
            self._runner.running = False
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)
        self.signals.status_changed.emit("STOPPED")

    @Slot()
    def emergency_stop(self) -> None:
        if self.mode == TradeMode.LIVE and self._runner:
            self._runner._close_all_live_positions()
        self.stop()
        self.signals.log_message.emit("EMERGENCY STOP — all live positions closed")

    @Slot(dict)
    def update_config(self, config: dict) -> None:
        if "symbols" in config:
            self.symbols = config["symbols"]
        if "timeframe" in config:
            self.timeframe = config["timeframe"]
        if "risk_percent" in config:
            self.risk_percent = config["risk_percent"]
        if "min_confidence" in config:
            self.min_confidence = config["min_confidence"]

    def _run_loop(self) -> None:
        import MetaTrader5 as mt5

        config = ScalpingConfig(
            min_confluence_score=2,
            min_atr_ratio=0.8,
            use_ml_quality_filter=False,
        )
        governor_cfg = GovernorConfig()

        self._runner = PaperTradingRunner(
            symbols=self.symbols,
            timeframe=self.timeframe,
            min_confidence=self.min_confidence,
            risk_percent=self.risk_percent,
            scalping_config=config,
            governor_config=governor_cfg,
            mode=self.mode,
        )
        self._runner._log = self._proxy_log

        if not mt5.terminal_info():
            self.signals.log_message.emit("MT5 not available — trading worker cannot start")
            self._running = False
            return

        connector = MT5Connector()
        connector._initialized = True
        self._runner.connector = connector
        self._emit_account_info()
        self._runner._log("Desktop UI worker started")

        while self._running:
            for symbol in self.symbols:
                try:
                    self._emit_tick(symbol)
                    self._runner._process_symbol(symbol)
                    self._emit_positions()
                    self._emit_governor()
                    self._emit_chart_data()
                except Exception as e:
                    self.signals.log_message.emit(f"{symbol} loop error: {e}")

            self._runner._save_state()
            self._emit_trades()
            self.signals.log_message.emit("State saved, sleeping 5s")
            time.sleep(5)

    def _proxy_log(self, msg: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.signals.log_message.emit(f"[{ts}] {msg}")

    def _emit_account_info(self) -> None:
        import MetaTrader5 as mt5

        try:
            info = mt5.account_info()
            if info:
                self.signals.account_updated.emit({
                    "login": info.login,
                    "balance": info.balance,
                    "equity": info.equity,
                    "margin_free": info.margin_free,
                    "margin_level": info.margin_level,
                    "leverage": info.leverage,
                    "currency": info.currency,
                    "name": info.name,
                    "server": info.server,
                })
        except Exception:
            pass

    def _emit_tick(self, symbol: str) -> None:
        import MetaTrader5 as mt5

        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick:
                self.signals.tick_updated.emit(symbol, float(tick.bid), float(tick.ask))
        except Exception:
            pass

    def _emit_positions(self) -> None:
        if not self._runner:
            return
        pos_dict = {}
        for sym, pos in self._runner.positions.items():
            pos_dict[sym] = {
                "symbol": pos.symbol,
                "side": pos.side.value,
                "volume": pos.volume,
                "entry_price": pos.entry_price,
                "stop_loss": pos.stop_loss,
                "take_profit": pos.take_profit,
                "pnl": pos.pnl,
                "pips": pos.pips,
                "open_time": pos.open_time.isoformat() if pos.open_time else "",
                "status": pos.status.value,
                "signal_confidence": pos.signal_confidence,
            }
        self.signals.positions_updated.emit(pos_dict)

    def _emit_trades(self) -> None:
        if not self._runner:
            return
        self.signals.trades_updated.emit(list(self._runner.trade_log))

    def _emit_governor(self) -> None:
        if not self._runner:
            return
        g = self._runner.governor
        self.signals.governor_updated.emit(g.mode, g.consecutive_losses, g.day_drawdown_pct)

    def _emit_chart_data(self) -> None:
        if not self._runner or not self.symbols:
            return
        try:
            from data import load_frame

            df = load_frame(Path("data/raw"), self.symbols[0], self.timeframe)
            if df is not None and not df.empty:
                self.signals.chart_data_updated.emit(df)
        except Exception:
            pass
