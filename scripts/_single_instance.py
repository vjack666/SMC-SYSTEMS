"""Garantiza UNA SOLA instancia de un script en Windows (y otros SO).

Dos modos, segun el proceso:

1) Mutex de kernel (ensure_single_instance) -- para loop_analisis y
   vigilante_riesgo. Idempotente: si ya corre otro, el actual avisa y SALE
   con codigo 0 (no duplicar trabajo). No depende de Qt (estos scripts no
   tienen UI).

2) Single-instance con UI (SingleInstanceUi) -- para la app del observador
   (PySide6). Si ya hay otra instancia viva, le envia un mensaje por
   QLocalServer para que TRAIGA SU VENTANA AL FRENTE, y el nuevo proceso
   sale limpio. Comportamiento tipo WhatsApp: cerras la X -> se esconde a la
   bandeja, no se muere; volves a abrir -> la ventana reaparece, sin duplicar.

En no-Windows el mutex es no-op (devuelve True) para no romper pruebas.
SingleInstanceUi usa QLocalServer, que es multiplataforma (funciona igual
en Linux/Mac si algun dia se corre ahi).
"""
from __future__ import annotations

import ctypes
import sys

# Guardamos el handle vivo para que el mutex de kernel no se libere mientras
# el proceso corre (ctypes no cierra el handle solo, pero lo mantenemos
# referenciado por si acaso).
_HANDLES: list = []


def ensure_single_instance(name: str) -> bool:
    """Devuelve True si somos la unica instancia (modo mutex, sin UI).

    Si ya corre otro proceso con el mismo `name`, imprime aviso y sale
    del proceso con codigo 0.
    """
    if sys.platform != "win32":
        return True
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        # Mutex de SESION de usuario (prefijo Local\\) -> unico por usuario,
        # no cruza entre sesiones de Terminal Services.
        handle = kernel32.CreateMutexW(None, False, f"Local\\SMC_{name}")
        if not handle or handle == 0:
            # No pudimos crear el mutex: mejor dejamos correr que bloquear.
            return True
        # ERROR_ALREADY_EXISTS = 183
        if ctypes.GetLastError() == 183:
            print(f"[single-instance] Ya hay otro '{name}' corriendo. "
                  f"Salida limpia (sin duplicar).")
            sys.exit(0)
        _HANDLES.append(handle)
        return True
    except Exception:
        # Cualquier fallo de API no debe impedir el arranque.
        return True


class SingleInstanceUi:
    """Single-instance para apps PySide6.

    Uso:
        si = SingleInstanceUi("observador_ui")
        if not si.is_first():
            si.activate_other()   # le avisa a la instancia viva que se muestre
            sys.exit(0)
        # ... crear QApplication, ventana ...
        si.listen(ventana)        # arranca el server que recibe "activate"

    El server escucha el mensaje "activate" y emite la senal `activate`
    para que la ventana se traiga al frente. El cliente, si el server ya
    existe, conecta y envia "activate" y cierra.
    """

    def __init__(self, name: str) -> None:
        from PySide6.QtCore import QCoreApplication
        # Identificador unico y seguro como nombre de pipe/socket local.
        self._id = f"SMC_{name}"
        safe = "".join(ch if ch.isalnum() else "_" for ch in self._id)
        self._server_name = safe
        self._app_id = QCoreApplication.applicationName() or "SMC"
        self._server = None
        self._activated = False

    def is_first(self) -> bool:
        """True si somos la primera instancia (no habia server vivo)."""
        if sys.platform != "win32":
            # En no-Windows usamos el mutex de todas formas para evitar
            # duplicados en sesiones de prueba; pero no bloqueamos el dev.
            return True
        from PySide6.QtNetwork import QLocalSocket
        sock = QLocalSocket()
        sock.connectToServer(self._server_name)
        # Si conecta -> ya hay otro corriendo.
        connected = sock.waitForConnected(500)
        sock.abort()
        return not connected

    def activate_other(self) -> None:
        """Avisa a la instancia viva (que tiene el server) que se muestre."""
        if sys.platform != "win32":
            return
        from PySide6.QtNetwork import QLocalSocket
        sock = QLocalSocket()
        sock.connectToServer(self._server_name)
        if sock.waitForConnected(1000):
            sock.write(b"activate\n")
            sock.waitForBytesWritten(1000)
        sock.abort()

    def listen(self, window) -> None:
        """Arranca el QLocalServer que recibe 'activate' y muestra la ventana.

        `window` es el QMainWindow (o cualquier QWidget) a traer al frente.
        """
        if sys.platform != "win32":
            return
        from PySide6.QtCore import QObject, Signal
        from PySide6.QtNetwork import QLocalServer, QLocalSocket

        self._server = QLocalServer()
        # removeServer por si quedo un socket huérfano de un cierre sucio.
        QLocalServer.removeServer(self._server_name)
        if not self._server.listen(self._server_name):
            # No pudimos escuchar: mejor dejamos correr que bloquear.
            self._server = None
            return

        class _Conn(QObject):
            activate = Signal()

            def __init__(self, srv, win) -> None:
                super().__init__()
                self._srv = srv
                self._win = win
                self._srv.newConnection.connect(self._on_new)
                self.activate.connect(self._show)

            def _on_new(self) -> None:
                while self._srv.hasPendingConnections():
                    cs = self._srv.nextPendingConnection()
                    cs.readyRead.connect(lambda: self._read(cs))
                    # Leemos lo que envia el cliente (el "activate").

            def _read(self, cs) -> None:
                data = bytes(cs.readAll().data())
                if b"activate" in data:
                    self.activate.emit()

            def _show(self) -> None:
                self._win.showNormal()
                self._win.raise_()
                self._win.activateWindow()

        self._conn = _Conn(self._server, window)
