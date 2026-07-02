from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import zmq

from smc_successor.integration.mt5_bridge.config import MT5BridgeConfig
from smc_successor.integration.mt5_bridge.schema import SignalMessage, TradeResult, TradeResultCode
from smc_successor.integration.mt5_bridge.zeromq_transport import ZeroMQTransport

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
        self._transport: ZeroMQTransport | None = None

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
        if self.config.protocol == "zeromq" and self._transport:
            self._transport.close_push_socket()
            self._transport.close_context()
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
    # Protocol implementations
    # ------------------------------------------------------------------

    def _start_zeromq(self) -> None:
        self._transport = ZeroMQTransport(self.config)
        self._transport.create_push_socket()
        self._socket = self._transport._push_socket
        self._context = self._transport._context

    def _start_file(self) -> None:
        Path(self.config.signal_log_path).mkdir(parents=True, exist_ok=True)

    def _start_direct(self) -> None:
        pass

    def _send_zeromq(self, signal: SignalMessage) -> TradeResult:
        if self._transport is None:
            self._start_zeromq()
        try:
            data = signal.to_dict()
            self._transport.push(self.config.push_address, data)
            return TradeResult(
                signal_id=signal.signal_id,
                ticket=None,
                message="Signal pushed via ZeroMQ",
            )
        except zmq.ZMQError as exc:
            logger.error("ZeroMQ push failed: %s", exc)
            return TradeResult(
                signal_id=signal.signal_id,
                ticket=None,
                code=TradeResultCode.ERROR,
                message=f"ZeroMQ error: {exc}",
            )
        except json.JSONDecodeError as exc:
            logger.error("JSON serialization error: %s", exc)
            return TradeResult(
                signal_id=signal.signal_id,
                ticket=None,
                code=TradeResultCode.ERROR,
                message=f"JSON error: {exc}",
            )

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
