from __future__ import annotations

import csv
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from data.mt5.connector import MT5Connector, _mt5_timeframe
from paper_trading.models import PaperPosition, PositionSide, PositionStatus, TradeRecord
from paper_trading.persistence import load_positions, save_positions, save_trade_log
from risk.governor import GovernorConfig, GovernorState, next_state
from risk.sizer import compute_lot
from signals.pipeline import ScalpingConfig, build_scalping_context

POLL_INTERVAL = 5


class PaperTradingRunner:
    def __init__(
        self,
        symbols: list[str],
        timeframe: str = "M15",
        data_dir: Path = Path("data/raw"),
        state_dir: Path = Path("data/paper_trading"),
        min_confidence: float = 0.65,
        max_hold_bars: int = 16,
        scalping_config: ScalpingConfig | None = None,
        governor_config: GovernorConfig | None = None,
        risk_percent: float = 1.0,
        commission_per_lot: float = 0.0,
        bars_for_pipeline: int = 500,
    ):
        self.symbols = symbols
        self.timeframe = timeframe
        self.data_dir = data_dir
        self.state_dir = state_dir
        self.min_confidence = min_confidence
        self.max_hold_bars = max_hold_bars
        self.scalping_config = scalping_config or ScalpingConfig()
        self.governor_config = governor_config or GovernorConfig()
        self.risk_percent = risk_percent
        self.commission_per_lot = commission_per_lot
        self.bars_for_pipeline = bars_for_pipeline

        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = state_dir / "positions.json"
        self.trades_path = state_dir / "trades.json"
        self.trades_csv_path = state_dir / "trades.csv"
        self.log_path = state_dir / "runner.log"

        self.connector: MT5Connector | None = None
        self.positions: dict[str, PaperPosition] = {}
        self.last_completed: dict[str, int] = {}
        self.governor = GovernorState()
        self.trade_log: list[dict[str, Any]] = []
        self.running = False

    def _log(self, msg: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _get_mt5_tf(self) -> int:
        return _mt5_timeframe(self.timeframe)

    def _candle_seconds(self) -> int:
        mt5_val = self._get_mt5_tf()
        if mt5_val >= 16000:
            mapping = {16385: 3600, 16388: 14400, 16408: 86400}
            return mapping.get(mt5_val, 3600)
        return mt5_val * 60

    def _detect_new_candle(self, symbol: str) -> bool:
        import MetaTrader5 as mt5

        rates = mt5.copy_rates_from_pos(symbol, self._get_mt5_tf(), 0, 2)
        if rates is None or len(rates) < 2:
            return False

        completed_time = int(rates[1]["time"])
        if symbol in self.last_completed and self.last_completed[symbol] == completed_time:
            return False

        self.last_completed[symbol] = completed_time
        return True

    def _refresh_data(self, symbol: str) -> None:
        df = self.connector.download_rates(symbol, self.timeframe, self.bars_for_pipeline)
        if df.empty:
            raise RuntimeError(f"No data returned for {symbol}")
        self.connector.save_parquet(df, symbol, self.timeframe, self.data_dir)

    def _check_position(self, symbol: str) -> None:
        pos = self.positions.get(symbol)
        if pos is None or pos.status != PositionStatus.OPEN:
            return

        import MetaTrader5 as mt5

        rates = mt5.copy_rates_from_pos(symbol, self._get_mt5_tf(), 0, 2)
        if rates is None or len(rates) < 2:
            return

        last_candle = rates[1]
        high = float(last_candle["high"])
        low = float(last_candle["low"])
        close = float(last_candle["close"])
        bar_time = datetime.fromtimestamp(last_candle["time"], tz=timezone.utc)

        pos.open_bar_index += 1
        hit_price = None
        status = None
        reason = ""

        if pos.side == PositionSide.LONG:
            if low <= pos.stop_loss:
                status = PositionStatus.CLOSED_SL
                hit_price = pos.stop_loss
                reason = "SL hit"
            elif high >= pos.take_profit:
                status = PositionStatus.CLOSED_TP
                hit_price = pos.take_profit
                reason = "TP hit"
            elif pos.open_bar_index >= self.max_hold_bars:
                status = PositionStatus.CLOSED_EXPIRY
                hit_price = close
                reason = "max hold expired"
        else:
            if high >= pos.stop_loss:
                status = PositionStatus.CLOSED_SL
                hit_price = pos.stop_loss
                reason = "SL hit"
            elif low <= pos.take_profit:
                status = PositionStatus.CLOSED_TP
                hit_price = pos.take_profit
                reason = "TP hit"
            elif pos.open_bar_index >= self.max_hold_bars:
                status = PositionStatus.CLOSED_EXPIRY
                hit_price = close
                reason = "max hold expired"

        if status is not None:
            pos.status = status
            pos.close_price = hit_price
            pos.close_time = bar_time
            pos.reason = reason

            direction = 1 if pos.side == PositionSide.LONG else -1
            pos.pips = (pos.close_price - pos.entry_price) * direction
            pos.pnl = pos.pips * pos.volume * 100000

            self._log(f"{symbol} {pos.side.value} CLOSED ({reason}) entry={pos.entry_price:.5f} exit={pos.close_price:.5f} pnl={pos.pnl:.2f}")

            self.trade_log.append({
                "symbol": pos.symbol,
                "side": pos.side.value,
                "entry_price": pos.entry_price,
                "exit_price": pos.close_price,
                "stop_loss": pos.stop_loss,
                "take_profit": pos.take_profit,
                "volume": pos.volume,
                "open_time": pos.open_time.isoformat(),
                "close_time": pos.close_time.isoformat(),
                "status": pos.status.value,
                "pnl": pos.pnl,
                "pips": pos.pips,
                "signal_confidence": pos.signal_confidence,
                "reason": reason,
            })

            if status in (PositionStatus.CLOSED_SL, PositionStatus.CLOSED_EXPIRY):
                self.governor.consecutive_losses += 1
            else:
                self.governor.consecutive_losses = 0

            if pos.pnl < 0:
                dd_pct = abs(pos.pnl) / (pos.entry_price * pos.volume * 100000) * 100
                self.governor.day_drawdown_pct += dd_pct

            self.governor = next_state(self.governor, self.governor_config)
            if self.governor.mode != "NORMAL":
                self._log(f"Governor state: {self.governor.mode} (losses={self.governor.consecutive_losses}, dd={self.governor.day_drawdown_pct:.2f}%)")
                save_positions(self.positions, self.state_path)
                save_trade_log(self.trade_log, self.trades_path)
                self._append_trade_csv(pos)

            del self.positions[symbol]

    def _open_position(self, symbol: str, direction: int, confidence: float, entry: float, sl: float, tp: float) -> None:
        if direction == 0:
            return
        if symbol in self.positions:
            return
        if self.governor.mode == "LOCKDOWN":
            self._log(f"{symbol} SKIP — governor LOCKDOWN")
            return

        try:
            sizing = compute_lot(
                symbol=symbol,
                entry=entry,
                stop_loss=sl,
                risk_percent=self.risk_percent,
                commission_per_lot=self.commission_per_lot,
            )
        except Exception as e:
            self._log(f"{symbol} sizing failed: {e}")
            sizing = None

        volume = sizing.lot if sizing else 0.01

        side = PositionSide.LONG if direction == 1 else PositionSide.SHORT
        pos = PaperPosition(
            symbol=symbol,
            side=side,
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            volume=volume,
            open_time=datetime.now(timezone.utc),
            signal_confidence=confidence,
        )
        self.positions[symbol] = pos
        self._log(f"{symbol} {side.value} OPEN entry={entry:.5f} sl={sl:.5f} tp={tp:.5f} vol={volume:.2f} conf={confidence:.2f}")

    def _process_symbol(self, symbol: str) -> None:
        if not self._detect_new_candle(symbol):
            self._check_position(symbol)
            return

        self._log(f"{symbol} new {self.timeframe} candle")

        governor_mode = self.governor.mode
        if governor_mode == "LOCKDOWN":
            self._log(f"{symbol} SKIP pipeline — governor LOCKDOWN")
            self._check_position(symbol)
            return

        self._refresh_data(symbol)

        try:
            context = build_scalping_context(
                symbol=symbol,
                timeframe=self.timeframe,
                data_dir=self.data_dir,
                config=self.scalping_config,
            )
        except Exception as e:
            self._log(f"{symbol} pipeline error: {e}")
            self._check_position(symbol)
            return

        valid = context[
            (context["signal_direction"] != 0)
            & (context["signal_confidence"] >= self.min_confidence)
        ]

        if valid.empty:
            self._log(f"{symbol} no signal")
            self._check_position(symbol)
            return

        latest = valid.iloc[-1]
        atr = float(latest["atr"])
        if not np.isfinite(atr) or atr <= 0.0:
            self._check_position(symbol)
            return

        direction = int(latest["signal_direction"])
        entry = float(latest["close"])
        confidence = float(latest["signal_confidence"])

        sl = entry - atr if direction == 1 else entry + atr
        tp = entry + (2.0 * atr) if direction == 1 else entry - (2.0 * atr)

        self._open_position(symbol, direction, confidence, entry, sl, tp)
        self._check_position(symbol)

    def _append_trade_csv(self, pos: PaperPosition) -> None:
        header = ["symbol", "side", "entry", "exit", "sl", "tp", "volume", "open_time", "close_time", "status", "pnl", "pips", "confidence", "reason"]
        file_exists = self.trades_csv_path.exists()
        with open(self.trades_csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(header)
            writer.writerow([
                pos.symbol,
                pos.side.value,
                f"{pos.entry_price:.5f}",
                f"{pos.close_price:.5f}" if pos.close_price else "",
                f"{pos.stop_loss:.5f}",
                f"{pos.take_profit:.5f}",
                pos.volume,
                pos.open_time.isoformat(),
                pos.close_time.isoformat() if pos.close_time else "",
                pos.status.value,
                f"{pos.pnl:.2f}",
                f"{pos.pips:.1f}",
                f"{pos.signal_confidence:.2f}",
                pos.reason,
            ])

    def _save_state(self) -> None:
        save_positions(self.positions, self.state_path)
        save_trade_log(self.trade_log, self.trades_path)

    def run(self) -> None:
        self.running = True
        self._log(f"PaperTradingRunner started — symbols={self.symbols} timeframe={self.timeframe}")
        self._log(f"Polling MT5 every {POLL_INTERVAL}s, checking for new {self.timeframe} candles")
        self._log(f"State dir: {self.state_dir.resolve()}")

        with MT5Connector() as connector:
            self.connector = connector

            info = connector.terminal_info()
            self._log(f"Connected: {info.get('name', 'unknown')}")

            self.positions = load_positions(self.state_path)
            if self.positions:
                self._log(f"Restored {len(self.positions)} open positions")

            for symbol in self.symbols:
                self._log(f"Initializing {symbol}...")
                try:
                    self._refresh_data(symbol)
                    self._log(f"  {symbol} data ready")
                except Exception as e:
                    self._log(f"  {symbol} init error: {e}")

            try:
                while self.running:
                    for symbol in self.symbols:
                        try:
                            self._process_symbol(symbol)
                        except Exception as e:
                            self._log(f"{symbol} error: {e}")
                    self._save_state()
                    time.sleep(POLL_INTERVAL)
            except KeyboardInterrupt:
                self._log("Shutting down...")
            finally:
                self._save_state()
                self._log(f"Positions saved. Total trades: {len(self.trade_log)}")
