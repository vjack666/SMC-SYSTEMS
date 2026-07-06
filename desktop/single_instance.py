"""Prevent multiple desktop UI instances."""
from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "smc-trading-system-desktop"


class SingleInstanceGuard(QObject):
    def __init__(self, server_name: str = SERVER_NAME) -> None:
        super().__init__()
        self._server_name = server_name
        self._server: QLocalServer | None = None

    def try_acquire(self) -> bool:
        probe = QLocalSocket()
        probe.connectToServer(self._server_name)
        if probe.waitForConnected(500):
            probe.close()
            return False

        self._server = QLocalServer()
        if self._server.listen(self._server_name):
            return True

        QLocalServer.removeServer(self._server_name)
        return self._server.listen(self._server_name)

    def release(self) -> None:
        if self._server is None:
            return
        self._server.close()
        QLocalServer.removeServer(self._server_name)
        self._server = None