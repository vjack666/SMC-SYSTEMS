from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from smc_successor.integration.mt5_bridge.config import MT5BridgeConfig
from smc_successor.integration.mt5_bridge.exporter import SignalExporter
from smc_successor.integration.mt5_bridge.receiver import MT5Receiver
from smc_successor.integration.mt5_bridge.schema import (
    AccountStatus,
    Heartbeat,
    SignalAction,
    SignalMessage,
    TradeResult,
    TradeResultCode,
)

logger = logging.getLogger(__name__)


class MT5BridgeAdapter:
    """High-level orchestrator for the MT5 bridge.

    Manages the lifecycle of exporter + receiver, converts system signals
    into MT5-compatible messages, and reports status back to the Python engine.
    """

    def __init__(self, config: MT5BridgeConfig | None = None) -> None:
        self.config = config or MT5BridgeConfig()
        self.exporter = SignalExporter(self.config)
        self.receiver = MT5Receiver(self.config)
        self._running = False
        self._start_time: float = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self.exporter.start()
        self.receiver.start()
        self._running = True
        self._start_time = time.monotonic()
        logger.info("MT5BridgeAdapter started")

    def stop(self) -> None:
        self._running = False
        self.receiver.stop()
        self.exporter.stop()
        logger.info("MT5BridgeAdapter stopped")

    @property
    def uptime_sec(self) -> float:
        return time.monotonic() - self._start_time if self._start_time > 0 else 0.0

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def send_signal(self, signal: SignalMessage) -> TradeResult:
        return self.exporter.send(signal)

    def send_market_order(
        self, symbol: str, action: SignalAction, volume: float,
        sl: float | None = None, tp: float | None = None,
        comment: str = "",
    ) -> TradeResult:
        signal = SignalMessage(
            signal_id=_new_id(),
            symbol=symbol,
            action=action,
            volume=volume,
            stop_loss=sl,
            take_profit=tp,
            comment=comment,
        )
        return self.send_signal(signal)

    def poll_results(self) -> list[TradeResult | AccountStatus | Heartbeat]:
        return self.receiver.poll()

    def heartbeat(self) -> Heartbeat:
        return Heartbeat(
            source="python",
            status="ALIVE" if self._running else "DOWN",
            uptime_sec=self.uptime_sec,
        )


def _new_id() -> str:
    return uuid.uuid4().hex[:12]
