from __future__ import annotations

import json
import logging
from typing import Any

import zmq

from integration.mt5_bridge.config import MT5BridgeConfig

logger = logging.getLogger(__name__)


class ZeroMQTransport:
    """Manages ZeroMQ sockets for bridge communication."""

    def __init__(self, config: MT5BridgeConfig) -> None:
        self.config = config
        self._context: zmq.Context | None = None
        self._push_socket: zmq.Socket | None = None
        self._pull_socket: zmq.Socket | None = None
        self._pub_socket: zmq.Socket | None = None

    # ------------------------------------------------------------------
    # Context lifecycle
    # ------------------------------------------------------------------

    @property
    def context(self) -> zmq.Context:
        if self._context is None or self._context.closed:
            self._context = zmq.Context()
        return self._context

    def close_context(self) -> None:
        if self._context and not self._context.closed:
            self._context.term()

    # ------------------------------------------------------------------
    # Socket helpers
    # ------------------------------------------------------------------

    def _make_socket(self, sock_type: int) -> zmq.Socket:
        sock = self.context.socket(sock_type)
        sock.setsockopt(zmq.LINGER, self.config.command_timeout_ms)
        return sock

    def create_push_socket(self) -> zmq.Socket:
        if self._push_socket is None:
            self._push_socket = self._make_socket(zmq.PUSH)
        return self._push_socket

    def create_pull_socket(self) -> zmq.Socket:
        if self._pull_socket is None:
            self._pull_socket = self._make_socket(zmq.PULL)
        return self._pull_socket

    def create_pub_socket(self) -> zmq.Socket:
        if self._pub_socket is None:
            self._pub_socket = self._make_socket(zmq.PUB)
        return self._pub_socket

    def close_push_socket(self) -> None:
        if self._push_socket:
            self._push_socket.close()
            self._push_socket = None

    def close_pull_socket(self) -> None:
        if self._pull_socket:
            self._pull_socket.close()
            self._pull_socket = None

    def close_pub_socket(self) -> None:
        if self._pub_socket:
            self._pub_socket.close()
            self._pub_socket = None

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def push(self, address: str, data: dict[str, Any]) -> None:
        sock = self.create_push_socket()
        sock.connect(address)
        payload = json.dumps(data)
        sock.send_string(payload)

    def pull(self, address: str, timeout_ms: int = 5000) -> dict[str, Any] | None:
        sock = self.create_pull_socket()
        sock.connect(address)
        try:
            msg = sock.recv_string(flags=zmq.NOBLOCK)
        except zmq.Again:
            return None
        return json.loads(msg)

    def publish(self, address: str, topic: str, data: dict[str, Any]) -> None:
        sock = self.create_pub_socket()
        sock.connect(address)
        payload = json.dumps(data)
        sock.send_string(f"{topic} {payload}")
