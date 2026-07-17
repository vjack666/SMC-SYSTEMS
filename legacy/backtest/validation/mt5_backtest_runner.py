from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# Tipos del canal MT5 (integration.mt5_bridge) eliminados: se definen aquí
# locales mínimos para que el harness de backtest siga funcionando sin el
# canal de envío real. No envían ordenes; solo modelan la señal.
class SignalAction(Enum):
    BUY = "BUY"
    SELL = "SELL"
    CLOSE_BUY = "CLOSE_BUY"
    CLOSE_SELL = "CLOSE_SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


@dataclass
class SignalMessage:
    signal_id: str
    symbol: str
    action: SignalAction
    volume: float = 0.01
    order_type: OrderType = OrderType.MARKET
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    comment: str = ""
    magic_number: int = 0


@dataclass
class TradeResult:
    code: "TradeResultCode"
    message: str = ""


class TradeResultCode(Enum):
    OK = "OK"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Simulated trade record — matches what the EA would produce
# ---------------------------------------------------------------------------


@dataclass
class SimulatedTradeResult:
    """Result of simulating a signal through the Bridge + EA pipeline."""

    signal_id: str
    symbol: str
    action: SignalAction
    volume: float
    entry_price: float
    exit_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    commission: float = 0.0
    swap: float = 0.0
    gross_profit: float = 0.0
    net_profit: float = 0.0
    pips: float = 0.0
    exit_reason: str = "signal"
    slippage: float = 0.0
    executed_at: str = ""
    duration_min: int = 0


# ---------------------------------------------------------------------------
# Slippage model
# ---------------------------------------------------------------------------


@dataclass
class SlippageConfig:
    """Configuration for simulated slippage during backtest."""

    mode: str = "fixed"          # "fixed" | "percent" | "none"
    fixed_pips: float = 0.5
    percent_spread: float = 0.5  # fraction of spread if mode=percent
    spread_pips: float = 1.5     # assumed spread in pips
    commission_per_lot: float = 3.5  # USD per standard lot round-turn


# ---------------------------------------------------------------------------
# Backtest Runner
# ---------------------------------------------------------------------------


class MT5BacktestRunner:
    """Simulates the Bridge → EA pipeline for historical signals.

    Loads a list of SignalMessage objects, simulates execution as the EA
    would, and returns SimulatedTradeResult objects for comparison against
    the Python backtest engine's output.
    """

    def __init__(self, slippage_config: SlippageConfig | None = None) -> None:
        self.config = slippage_config or SlippageConfig()
        self.results: list[SimulatedTradeResult] = []

    # ------------------------------------------------------------------
    # Load signals from a file or list
    # ------------------------------------------------------------------

    def load_signals_from_file(self, path: str | Path) -> list[SignalMessage]:
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return [self._dict_to_signal(item) for item in data]

    def load_signals_from_engine(self, engine_output: list[dict[str, Any]]) -> list[SignalMessage]:
        return [self._dict_to_signal(item) for item in engine_output]

    # ------------------------------------------------------------------
    # Run simulation
    # ------------------------------------------------------------------

    def run(self, signals: list[SignalMessage], price_data: dict[str, Any] | None = None) -> list[SimulatedTradeResult]:
        """Simulate the EA's execution for each signal.

        Parameters
        ----------
        signals : list[SignalMessage]
            Signals to simulate.
        price_data : dict or None
            Optional OHLC price data keyed by symbol+timestamp for fill price lookup.

        Returns
        -------
        list[SimulatedTradeResult]
        """
        self.results.clear()
        for sig in signals:
            result = self._execute_signal(sig, price_data)
            self.results.append(result)
        return self.results

    # ------------------------------------------------------------------
    # Internal execution simulation
    # ------------------------------------------------------------------

    def _execute_signal(self, signal: SignalMessage, price_data: Any) -> SimulatedTradeResult:
        action = signal.action
        volume = signal.volume or 0.01
        sl = signal.stop_loss
        tp = signal.take_profit

        entry = self._simulate_fill_price(signal, price_data)
        slippage = self._compute_slippage(entry)

        # For MARKET orders, slippage affects entry price
        if signal.order_type.name == "MARKET":
            if action == SignalAction.BUY:
                entry += slippage
            elif action == SignalAction.SELL:
                entry -= slippage

        duration = 0
        exit_price = None
        exit_reason = "open"
        gross = 0.0

        # If SL/TP are set, determine which would be hit first (simplified)
        if action == SignalAction.BUY and sl is not None and tp is not None:
            # Assume TP hit for simplicity (real backtest would use OHLC data)
            exit_price = tp
            gross = (exit_price - entry) * volume * 100_000
            pips = (exit_price - entry) * 10_000
            exit_reason = "take_profit"
        elif action == SignalAction.SELL and sl is not None and tp is not None:
            exit_price = tp
            gross = (entry - exit_price) * volume * 100_000
            pips = (entry - exit_price) * 10_000
            exit_reason = "take_profit"
        elif action in (SignalAction.CLOSE_BUY, SignalAction.CLOSE_SELL):
            exit_price = entry
            gross = 0.0
            pips = 0.0
            exit_reason = "close_signal"

        commission = self._compute_commission(volume)
        net = gross - commission

        return SimulatedTradeResult(
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            action=signal.action,
            volume=volume,
            entry_price=round(entry, 5),
            exit_price=round(exit_price, 5) if exit_price else None,
            stop_loss=sl,
            take_profit=tp,
            commission=round(commission, 2),
            gross_profit=round(gross, 2),
            net_profit=round(net, 2),
            pips=round(pips, 1),
            exit_reason=exit_reason,
            slippage=round(slippage, 5),
            duration_min=duration,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _simulate_fill_price(self, signal: SignalMessage, price_data: Any) -> float:
        if signal.price is not None and signal.price > 0:
            return signal.price
        if price_data:
            symbol = signal.symbol
            if symbol in price_data:
                px = price_data[symbol].get("ask" if signal.action == SignalAction.BUY else "bid")
                if px:
                    return px
        # Default: use a synthetic price if none available
        return 1.1000 if signal.action in (SignalAction.BUY, SignalAction.CLOSE_SELL) else 1.0990

    def _compute_slippage(self, price: float) -> float:
        if self.config.mode == "none":
            return 0.0
        if self.config.mode == "fixed":
            return self.config.fixed_pips * 0.0001
        if self.config.mode == "percent":
            spread = self.config.spread_pips * 0.0001
            return spread * self.config.percent_spread
        return 0.0

    def _compute_commission(self, volume: float) -> float:
        return volume * self.config.commission_per_lot

    def _dict_to_signal(self, item: dict[str, Any]) -> SignalMessage:
        return SignalMessage(
            signal_id=item.get("signal_id", ""),
            symbol=item.get("symbol", ""),
            action=SignalAction(item.get("action", "BUY")),
            order_type=OrderType(item.get("order_type", "MARKET")),
            volume=item.get("volume"),
            price=item.get("price"),
            stop_loss=item.get("stop_loss"),
            take_profit=item.get("take_profit"),
            comment=item.get("comment", ""),
            magic_number=item.get("magic_number", 0),
        )


