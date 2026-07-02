from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from integration.mt5_bridge.config import MT5BridgeConfig
from integration.mt5_bridge.schema import SignalMessage, TradeResult, TradeResultCode

logger = logging.getLogger(__name__)


class SignalExporter:
    """Responsible for sending signals from Python to MT5.

    Currently supports three transport modes:
    - zeromq  : push signals to MT5 via ZeroMQ PUSH socket.
    - file    : write signals as JSON files polled by the MT5 EA.
    - direct  : execute via MetaTrader5 Python package (same process).
    """

    def __init__(self, config: MT5BridgeConfig) -> None:
        self.config = config
        self._context: Any = None
        self._socket: Any = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        protocol = self.config.protocol
        if protocol == "zeromq":
            self._start_zeromq()
        elif protocol == "file":
            self._start_file()
        elif protocol == "direct":
            self._start_direct()
        else:
            raise ValueError(f"Unknown protocol: {protocol}")
        logger.info("SignalExporter started (protocol=%s)", protocol)

    def stop(self) -> None:
        if protocol := self.config.protocol == "zeromq":
            if self._socket:
                self._socket.close()
            if self._context:
                self._context.term()
        logger.info("SignalExporter stopped")

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    def send(self, signal: SignalMessage) -> TradeResult:
        if self.config.protocol == "file":
            self._start_file()
        if self.config.protocol == "zeromq":
            return self._send_zeromq(signal)
        elif self.config.protocol == "file":
            return self._send_file(signal)
        elif self.config.protocol == "direct":
            return self._send_direct(signal)
        raise ValueError(f"Unknown protocol: {self.config.protocol}")

    # ------------------------------------------------------------------
    # Protocol implementations (stubs — real logic added in later phases)
    # ------------------------------------------------------------------

    def _start_zeromq(self) -> None:
        pass

    def _start_file(self) -> None:
        Path(self.config.signal_log_path).mkdir(parents=True, exist_ok=True)

    def _start_direct(self) -> None:
        pass

    def _send_zeromq(self, signal: SignalMessage) -> TradeResult:
        raise NotImplementedError("ZeroMQ transport not yet implemented")

    def _send_file(self, signal: SignalMessage) -> TradeResult:
        path = self.config.signal_log_path / f"signal_{signal.signal_id}.json"
        path.write_text(json.dumps(signal.to_dict(), indent=2), encoding="utf-8")
        return TradeResult(
            signal_id=signal.signal_id,
            ticket=None,
            message=f"Signal written to {path.name}",
        )

    def _send_direct(self, signal: SignalMessage) -> TradeResult:
        raise NotImplementedError("Direct MT5 transport not yet implemented")
