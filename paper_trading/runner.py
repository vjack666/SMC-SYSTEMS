from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from data.mt5.connector import ConnectionConfig, MT5Connector, _mt5_timeframe
from paper_trading.models import PaperPosition, PositionSide, PositionStatus, TradeMode, TradeRecord
from paper_trading.persistence import (
    load_governor_state,
    load_positions,
    save_governor_state,
    save_positions,
    save_trade_log,
)
from agents.orchestrator import AgentOrchestrator
from ml.inference import QualityFilter, QualityFilterConfig
from regime import detect_regimes
from risk.governor import GovernorConfig, GovernorState, next_state
from risk.sizer import close_position, compute_lot, send_market_order
from signals.pipeline import ScalpingConfig, build_scalping_context

POLL_INTERVAL = 5


class PaperTradingRunner:
    def __init__(
        self,
        symbols: list[str],
        timeframe: str = "M15",
        connector_config: ConnectionConfig | None = None,
        data_dir: Path = Path("data/raw"),
        state_dir: Path = Path("data/paper_trading"),
        min_confidence: float = 0.65,
        max_hold_bars: int = 16,
        scalping_config: ScalpingConfig | None = None,
        governor_config: GovernorConfig | None = None,
        risk_percent: float = 1.0,
        commission_per_lot: float = 0.0,
        bars_for_pipeline: int = 500,
        mode: TradeMode = TradeMode.PAPER,
        magic: int = 20260701,
        deviation: int = 10,
        kill_switch_path: Path = Path("data/KILL_SWITCH"),
        drift_check_enabled: bool = False,
        drift_baseline_path: Path = Path("ml/models/quality_filter.drift_baseline.json"),
        drift_threshold: float = 0.2,
        drift_check_every: int = 60,
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
        self.mode = mode
        self.magic = magic
        self.deviation = deviation
        self.kill_switch_path = kill_switch_path
        self.connector_config = connector_config or ConnectionConfig()

        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = state_dir / "positions.json"
        self.governor_path = state_dir / "governor.json"
        self.trades_path = state_dir / "trades.json"
        self.trades_csv_path = state_dir / "trades.csv"
        self.log_path = state_dir / "runner.log"

        # Optional production monitoring: live drift check (PSI) vs the
        # training baseline. When drift exceeds the threshold the governor is
        # forced into LOCKDOWN so no new entries are taken on a shifted regime.
        self.drift_check_enabled = drift_check_enabled
        self.drift_baseline_path = drift_baseline_path
        self.drift_threshold = drift_threshold
        self.drift_check_every = max(1, drift_check_every)
        self._drift_detector = None
        self._drift_baseline: dict[str, list[float]] | None = None
        if self.drift_check_enabled:
            try:
                from monitoring.drift_detector import DriftDetector

                self._drift_detector = DriftDetector(threshold=self.drift_threshold)
                with open(self.drift_baseline_path, "r", encoding="utf-8") as f:
                    self._drift_baseline = json.load(f)
                self._log(
                    f"Drift check ENABLED (threshold={self.drift_threshold}, "
                    f"every {self.drift_check_every} cycles, "
                    f"baseline={self.drift_baseline_path.name})"
                )
            except Exception as e:
                self._drift_detector = None
                self._drift_baseline = None
                self._log(f"Drift check DISABLED (could not init: {e})")
        self._drift_cycle = 0
        self._last_context: dict[str, Any] = {}

        self.connector: MT5Connector | None = None
        self.positions: dict[str, PaperPosition] = {}
        self.last_completed: dict[str, int] = {}
        self.governor = GovernorState()
        self.trade_log: list[dict[str, Any]] = []
        self.running = False
        self.live_positions_tickets: dict[str, int] = {}

        self._orchestrator: AgentOrchestrator | None = None
        self._quality_filter: QualityFilter | None = None
        if self.scalping_config.use_ml_quality_filter:
            self._orchestrator = AgentOrchestrator()
            self._quality_filter = QualityFilter(
                QualityFilterConfig(
                    enabled=True,
                    model_path=Path(self.scalping_config.ml_model_path),
                    max_hold_bars=max_hold_bars,
                )
            )
            if not self._quality_filter.is_active:
                self._log(
                    f"ML filter enabled but model missing at {self.scalping_config.ml_model_path}"
                )

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

    def _check_kill_switch(self) -> bool:
        if self.kill_switch_path.exists():
            self._log("KILL SWITCH triggered — shutting down")
            if self.mode == TradeMode.LIVE:
                self._close_all_live_positions()
            self.running = False
            try:
                self.kill_switch_path.unlink()
            except Exception:
                pass
            return True
        return False

    def _close_all_live_positions(self) -> None:
        import MetaTrader5 as mt5

        positions = mt5.positions_get(magic=self.magic)
        if positions:
            for pos in positions:
                close_result = close_position(
                    ticket=pos.ticket,
                    symbol=pos.symbol,
                    volume=pos.volume,
                    position_type=pos.type,
                    magic=self.magic,
                )
                self._log(f"KILL SWITCH closed {pos.symbol}: {close_result}")

    def _reconnect_if_needed(self) -> None:
        import MetaTrader5 as mt5

        if mt5.terminal_info() is not None:
            return

        self._log("MT5 disconnected — reconnecting...")
        for attempt in range(1, 4):
            try:
                self.connector.reconnect()
                if mt5.terminal_info() is not None:
                    self._log("Reconnected successfully")
                    return
            except Exception as e:
                self._log(f"Reconnect attempt {attempt}/3 failed: {e}")
            time.sleep(3)
        self._log("WARNING: Could not reconnect to MT5 — data may stall")

    def _validate_margin(self, symbol: str, volume: float, price: float) -> bool:
        import MetaTrader5 as mt5

        account = mt5.account_info()
        if account is None:
            return False
        margin = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, volume, price)
        if margin is None:
            return False
        free_margin = account.margin_free
        return margin <= free_margin * 0.8

    def _sync_live_position(self, symbol: str) -> None:
        import MetaTrader5 as mt5

        positions = mt5.positions_get(symbol=symbol, magic=self.magic)
        if positions is None or len(positions) == 0:
            paper = self.positions.get(symbol)
            if paper and paper.status == PositionStatus.OPEN:
                self._log(f"{symbol} position closed externally — recording")
                paper.status = PositionStatus.CLOSED_MANUAL
                tick = mt5.symbol_info_tick(symbol)
                paper.close_price = tick.bid if paper.side == PositionSide.LONG else tick.ask
                paper.close_time = datetime.now(timezone.utc)
                paper.reason = "closed externally"
                direction = 1 if paper.side == PositionSide.LONG else -1
                paper.pips = (paper.close_price - paper.entry_price) * direction
                paper.pnl = paper.pips * paper.volume * 100000
                self._log(f"{symbol} {paper.side.value} CLOSED (externally) entry={paper.entry_price:.5f} exit={paper.close_price:.5f} pnl={paper.pnl:.2f}")
                self.trade_log.append({
                    "symbol": paper.symbol,
                    "side": paper.side.value,
                    "entry_price": paper.entry_price,
                    "exit_price": paper.close_price,
                    "stop_loss": paper.stop_loss,
                    "take_profit": paper.take_profit,
                    "volume": paper.volume,
                    "open_time": paper.open_time.isoformat(),
                    "close_time": paper.close_time.isoformat(),
                    "status": paper.status.value,
                    "pnl": paper.pnl,
                    "pips": paper.pips,
                    "signal_confidence": paper.signal_confidence,
                    "reason": "closed externally",
                })
                if paper.pnl < 0:
                    self.governor.consecutive_losses += 1
                    dd_pct = abs(paper.pnl) / (paper.entry_price * paper.volume * 100000) * 100
                    self.governor.day_drawdown_pct += dd_pct
                else:
                    self.governor.consecutive_losses = 0
                self.governor = next_state(self.governor, self.governor_config)
                save_positions(self.positions, self.state_path)
                save_trade_log(self.trade_log, self.trades_path)
                self._append_trade_csv(paper)
                del self.positions[symbol]
                self.live_positions_tickets.pop(symbol, None)
            return

        mt5_pos = positions[0]
        paper = self.positions.get(symbol)
        if paper:
            paper.ticket = mt5_pos.ticket
            self.live_positions_tickets[symbol] = mt5_pos.ticket
            if mt5_pos.comment in ("sl", "tp") or mt5_pos.volume <= 0:
                paper.status = PositionStatus.CLOSED_SL if mt5_pos.comment == "sl" else PositionStatus.CLOSED_TP
                paper.close_price = float(mt5_pos.price_current)
                paper.close_time = datetime.now(timezone.utc)
                paper.pnl = float(mt5_pos.profit)
                direction = 1 if paper.side == PositionSide.LONG else -1
                paper.pips = (paper.close_price - paper.entry_price) * direction
                paper.reason = mt5_pos.comment if mt5_pos.comment in ("sl", "tp") else "closed live"
                self._log(f"{symbol} {paper.side.value} CLOSED ({paper.reason}) entry={paper.entry_price:.5f} exit={paper.close_price:.5f} pnl={paper.pnl:.2f}")
                self.trade_log.append({
                    "symbol": paper.symbol,
                    "side": paper.side.value,
                    "entry_price": paper.entry_price,
                    "exit_price": paper.close_price,
                    "stop_loss": paper.stop_loss,
                    "take_profit": paper.take_profit,
                    "volume": paper.volume,
                    "open_time": paper.open_time.isoformat(),
                    "close_time": paper.close_time.isoformat(),
                    "status": paper.status.value,
                    "pnl": paper.pnl,
                    "pips": paper.pips,
                    "signal_confidence": paper.signal_confidence,
                    "reason": paper.reason,
                })
                if paper.pnl < 0:
                    self.governor.consecutive_losses += 1
                    dd_pct = abs(paper.pnl) / (paper.entry_price * paper.volume * 100000) * 100
                    self.governor.day_drawdown_pct += dd_pct
                else:
                    self.governor.consecutive_losses = 0
                self.governor = next_state(self.governor, self.governor_config)
                save_positions(self.positions, self.state_path)
                save_trade_log(self.trade_log, self.trades_path)
                self._append_trade_csv(paper)
                del self.positions[symbol]
                self.live_positions_tickets.pop(symbol, None)

    def _open_live_position(self, symbol: str, direction: int, confidence: float, entry: float, sl: float, tp: float) -> None:
        if self.governor.mode == "LOCKDOWN":
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

        if not self._validate_margin(symbol, volume, entry):
            self._log(f"{symbol} INSUFFICIENT MARGIN — skip")
            return

        action = "BUY" if direction == 1 else "SELL"
        result = send_market_order(
            symbol=symbol,
            action=action,
            volume=volume,
            stop_loss=sl,
            take_profit=tp,
            comment="SMC_LIVE",
            magic=self.magic,
            deviation=self.deviation,
        )

        if result["retcode"] == 10009:
            ticket = result["ticket"]
            side = PositionSide.LONG if direction == 1 else PositionSide.SHORT
            pos = PaperPosition(
                symbol=symbol,
                side=side,
                entry_price=result["price"],
                stop_loss=sl,
                take_profit=tp,
                volume=volume,
                open_time=datetime.now(timezone.utc),
                signal_confidence=confidence,
                ticket=ticket,
            )
            self.positions[symbol] = pos
            self.live_positions_tickets[symbol] = ticket
            self._log(f"{symbol} {side.value} LIVE OPEN ticket={ticket} entry={result['price']:.5f} vol={volume:.2f}")
        else:
            self._log(f"{symbol} ORDER FAILED: retcode={result['retcode']} {result['comment']}")

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

        if self.mode == TradeMode.LIVE:
            self._open_live_position(symbol, direction, confidence, entry, sl, tp)
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
        self._reconnect_if_needed()

        if self.mode == TradeMode.LIVE:
            self._sync_live_position(symbol)

        if not self._detect_new_candle(symbol):
            self._check_position(symbol)
            return

        self._log(f"{symbol} new {self.timeframe} candle")

        self._last_context[symbol] = None

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
                orchestrator=self._orchestrator,
            )
            self._last_context[symbol] = context
            if self.scalping_config.use_ml_quality_filter:
                context = detect_regimes(context)
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

        structural_sl = latest.get("structural_sl")
        if structural_sl is not None and np.isfinite(float(structural_sl)):
            sl = float(structural_sl)
        else:
            sl = entry - atr if direction == 1 else entry + atr
        tp = entry + (2.0 * atr) if direction == 1 else entry - (2.0 * atr)

        if self._quality_filter is not None and self._quality_filter.is_active:
            bar_idx = int(latest.name)
            timestamp = str(latest.get("time", ""))
            allow, ml_prob, ml_threshold = self._quality_filter.evaluate_signal(
                context=context,
                bar_idx=bar_idx,
                timestamp=timestamp,
                entry=entry,
                stop_loss=sl,
                take_profit=tp,
                signal_confidence=confidence,
                governor_mode=self.governor.mode,
            )
            if not allow:
                self._log(
                    f"{symbol} SKIP — ML filter ({ml_prob:.2f} < {ml_threshold:.2f})"
                )
                self._check_position(symbol)
                return

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
        save_governor_state(self.governor, self.governor_path)

    def _ensure_mt5_running(self) -> bool:
        import MetaTrader5 as mt5

        self._log("Connecting to MetaTrader 5...")
        cfg = self.connector_config
        init_kwargs: dict[str, Any] = {"timeout": cfg.timeout}
        if cfg.path:
            init_kwargs["path"] = cfg.path
            self._log(f"Terminal path: {cfg.path}")

        for attempt in range(1, 5):
            if mt5.initialize(**init_kwargs):
                info = mt5.terminal_info()
                if info is not None:
                    terminal = info._asdict() if hasattr(info, '_asdict') else {}
                    name = terminal.get('name', 'unknown')
                    self._log(f"MT5 initialized: {name}")
                    return True
            code, desc = mt5.last_error()
            self._log(f"MT5 init attempt {attempt}/4 failed: [{code}] {desc}")
            if attempt < 4:
                self._log("Retrying in 3s...")
                time.sleep(3)

        self._log("ERROR: Could not connect to MetaTrader 5.")
        self._log("Make sure your Funded Next terminal is open and logged in.")
        self._log("If the terminal path is custom, pass --mt5-path <path> to the script.")
        self._log("Common paths:")
        self._log("  C:\\Program Files\\Funded Next\\terminal64.exe")
        self._log("  C:\\Program Files\\FundedNext MT5 Terminal\\terminal64.exe")
        return False

    def _check_drift(self) -> bool:
        """Return True if drift forced a LOCKDOWN this cycle.

        Compares the most recent feature distributions of the live context
        against the training baseline using Population Stability Index.
        Safe to call when drift check is disabled or baseline unavailable —
        returns False and does nothing in those cases.
        """
        if not self.drift_check_enabled or self._drift_detector is None or self._drift_baseline is None:
            return False

        self._drift_cycle += 1
        if self._drift_cycle % self.drift_check_every != 0:
            return False

        try:
            recent: dict[str, list[float]] = {}
            for symbol in self.symbols:
                ctx = self._last_context.get(symbol) if hasattr(self, "_last_context") else None
                if ctx is None or len(ctx) == 0:
                    continue
                for col, ref in self._drift_baseline.items():
                    if col in ctx.columns:
                        series = ctx[col].dropna().astype(float).tolist()
                        if series:
                            recent.setdefault(col, []).extend(series)
            if not recent:
                return False

            psi = self._drift_detector.check(recent, self._drift_baseline)
            max_psi = max(psi.values()) if psi else 0.0
            self._log(f"Drift check: max PSI={max_psi:.4f} (threshold={self.drift_threshold})")
            if self._drift_detector.is_drift(psi):
                self._log("DRIFT detected — forcing governor LOCKDOWN")
                self.governor.mode = "LOCKDOWN"
                return True
        except Exception as e:
            self._log(f"Drift check error (skipped): {e}")
        return False

    def run(self) -> None:
        self.running = True
        mode_label = self.mode.value
        self._log(f"PaperTradingRunner started — symbols={self.symbols} timeframe={self.timeframe} mode={mode_label}")
        self._log(f"Polling MT5 every {POLL_INTERVAL}s, checking for new {self.timeframe} candles")
        self._log(f"State dir: {self.state_dir.resolve()}")
        if self.mode == TradeMode.LIVE:
            self._log(f"LIVE mode active — magic={self.magic} deviation={self.deviation} kill_switch={self.kill_switch_path}")

        if not self._ensure_mt5_running():
            self.running = False
            return

        with MT5Connector(self.connector_config) as connector:
            self.connector = connector

            info = connector.terminal_info()
            self._log(f"Connected: {info.get('name', 'unknown')}")

            self.positions = load_positions(self.state_path)
            if self.positions:
                self._log(f"Restored {len(self.positions)} open positions")

            persisted_governor = load_governor_state(self.governor_path)
            if persisted_governor:
                self.governor = persisted_governor
                self._log(f"Restored governor state: {self.governor.mode}")

            for symbol in self.symbols:
                self._log(f"Initializing {symbol}...")
                try:
                    self._refresh_data(symbol)
                    self._log(f"  {symbol} data ready")
                except Exception as e:
                    self._log(f"  {symbol} init error: {e}")

            try:
                while self.running:
                    if self._check_kill_switch():
                        break
                    self._check_drift()
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
