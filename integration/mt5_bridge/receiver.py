from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import zmq

from integration.mt5_bridge.config import MT5BridgeConfig
from integration.mt5_bridge.schema import AccountStatus, Heartbeat, TradeResult, TradeResultCode
from integration.mt5_bridge.zeromq_transport import ZeroMQTransport

logger = logging.getLogger(__name__)


class MT5Receiver:
    """Receives data from MT5 back to Python.

    Supports the same transport modes as SignalExporter:
    - zeromq  : pull results/status from MT5 via ZeroMQ PULL socket.
    - file    : poll JSON files written by MT5 EA.
    - direct  : read directly via MetaTrader5 Python package.
    """

    def __init__(self, config: MT5BridgeConfig) -> None:
        self.config = config
        self._context: Any = None
        self._socket: Any = None
        self._transport: ZeroMQTransport | None = None
        self._inbox: list[TradeResult | AccountStatus | Heartbeat] = []

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
        logger.info("MT5Receiver started (protocol=%s)", protocol)

    def stop(self) -> None:
        if self.config.protocol == "zeromq" and self._transport:
            self._transport.close_pull_socket()
            self._transport.close_context()
        logger.info("MT5Receiver stopped")

    # ------------------------------------------------------------------
    # Poll / drain
    # ------------------------------------------------------------------

    def poll(self) -> list[TradeResult | AccountStatus | Heartbeat]:
        if self.config.protocol == "zeromq":
            return self._poll_zeromq()
        elif self.config.protocol == "file":
            return self._poll_file()
        elif self.config.protocol == "direct":
            return self._poll_direct()
        raise ValueError(f"Unknown protocol: {self.config.protocol}")

    def drain(self) -> list[TradeResult | AccountStatus | Heartbeat]:
        items = list(self._inbox)
        self._inbox.clear()
        return items

    # ------------------------------------------------------------------
    # Protocol implementations
    # ------------------------------------------------------------------

    def _start_zeromq(self) -> None:
        self._transport = ZeroMQTransport(self.config)
        self._transport.create_pull_socket()
        self._socket = self._transport._pull_socket
        self._context = self._transport._context

    def _start_file(self) -> None:
        Path(self.config.signal_log_path).mkdir(parents=True, exist_ok=True)

    def _start_direct(self) -> None:
        pass

    def _poll_zeromq(self) -> list[TradeResult | AccountStatus | Heartbeat]:
        if self._transport is None:
            self._start_zeromq()
        items: list[TradeResult | AccountStatus | Heartbeat] = []
        try:
            for _ in range(100):
                data = self._transport.pull(
                    self.config.pull_address,
                    timeout_ms=self.config.command_timeout_ms,
                )
                if data is None:
                    break
                msg_type = data.get("_type", "TradeResult")
                if msg_type == "TradeResult":
                    items.append(TradeResult(**data))
                elif msg_type == "AccountStatus":
                    items.append(AccountStatus(**data))
                elif msg_type == "Heartbeat":
                    items.append(Heartbeat(**data))
        except zmq.ZMQError as exc:
            logger.warning("ZeroMQ poll error: %s", exc)
        return items

    def _poll_file(self) -> list[TradeResult | AccountStatus | Heartbeat]:
        result_dir = Path(self.config.signal_log_path)
        items: list[TradeResult | AccountStatus | Heartbeat] = []
        for f in sorted(result_dir.glob("result_*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            items.append(TradeResult(**data))
            f.unlink(missing_ok=True)
        return items

    def _poll_direct(self) -> list[TradeResult | AccountStatus | Heartbeat]:
        raise NotImplementedError("Direct MT5 receiver not yet implemented")
