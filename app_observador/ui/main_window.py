"""Ventana principal del observador.

Ensambla los widgets y corre el motor (engine.run_cycle) en un hilo separado para
no bloquear la UI durante los ~25s que tarda el análisis real (Wyckoff + mapas).
Refresca cada REFRESH_SECONDS (5 min) y al pulsar 'Actualizar'.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QTabWidget,
)

from app_observador.config import REFRESH_SECONDS, SYMBOL
from app_observador.core.blackbox import log_event, log_error
from app_observador.core.data_retention import run_retention
from app_observador.core.mt5_status import shutdown as mt5_shutdown
from app_observador.core.engine import load_cached
from app_observador.ui.semaforo_widget import SemaforoWidget
from app_observador.ui.sesgo_widget import SesgoWidget
from app_observador.ui.mapa_widget import MapaWidget
from app_observador.ui.noticias_widget import NoticiasWidget
from app_observador.ui.resumen_widget import ResumenWidget
from app_observador.ui.estado_widget import EstadoWidget
from app_observador.ui.crono_widget import CronoWidget

# alertas.py vive en scripts/ (popup + beep de Windows)
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from alertas import alertar  # noqa: E402


class _Worker(QThread):
    finished = Signal(dict)

    def __init__(self, force_fetch: bool = False) -> None:
        super().__init__()
        self._force = force_fetch

    def run(self) -> None:
        try:
            from app_observador.core import engine
            result = engine.run_cycle(force_fetch=self._force)
            self.finished.emit(result)
        except Exception as e:
            log_error("main_window", "worker_crash", e)
            self.finished.emit({"errores": [f"worker: {e}"]})


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"SMC OBSERVADOR — {SYMBOL}")
        self.setMinimumSize(1100, 720)
        self.resize(1280, 820)

        # Widgets
        self.semaforo = SemaforoWidget()
        self.sesgo = SesgoWidget()
        self.mapa = MapaWidget()
        self.noticias = NoticiasWidget()
        self.resumen = ResumenWidget()
        self.estado = EstadoWidget()
        self.crono = CronoWidget()

        self._build_layout()

        # Timer de refresco
        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_SECONDS * 1000)
        self._timer.timeout.connect(self._run_cycle)
        self._timer.start()

        # Retención al arrancar (borra >90 días)
        try:
            run_retention()
        except Exception as e:
            log_error("main_window", "retention_arranque", e)

        self._last_color = None  # para alertar solo en cambios

        # Abrir rapido: pinta el ultimo ciclo cacheado (<1s) sin alerta
        cached = load_cached()
        if cached:
            self._apply_result(cached, alert=False)
            if cached.get("semaforo", {}).get("color"):
                self._last_color = cached["semaforo"]["color"]

        # Primer ciclo real (en background, refresca cache + mapas)
        self._run_cycle()

    def _build_layout(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        # Barra superior: título + botón actualizar
        top = QHBoxLayout()
        title = QLabel("SMC OBSERVADOR — análisis ICT/Wyckoff (sin bot)")
        title.setStyleSheet("color: #ddd; font-size: 14px; font-weight: bold;")
        top.addWidget(title)
        top.addStretch()
        self.btn = QPushButton("Actualizar ahora")
        self.btn.clicked.connect(lambda: self._run_cycle(force_fetch=True))
        top.addWidget(self.btn)
        root.addLayout(top)

        # Fila 1: semáforo + sesgo + estado
        row1 = QHBoxLayout()
        row1.addWidget(self.semaforo, 1)
        row1.addWidget(self.sesgo, 2)
        row1.addWidget(self.estado, 1)
        root.addLayout(row1)

        # Fila 2: pestañas (1=Principal/resumen | 2=Noticias | 3=Mapa ICT)
        tabs = QTabWidget()
        tab_principal = QWidget()
        tp_layout = QVBoxLayout(tab_principal)
        tp_layout.addWidget(self.resumen, 1)
        tabs.addTab(tab_principal, "Principal")

        tab_noticias = QWidget()
        tn_layout = QVBoxLayout(tab_noticias)
        tn_layout.addWidget(self.noticias, 1)
        tabs.addTab(tab_noticias, "Noticias")

        tab_mapa = QWidget()
        tm_layout = QVBoxLayout(tab_mapa)
        tm_layout.addWidget(self.mapa, 1)
        tabs.addTab(tab_mapa, "Mapa ICT")
        root.addWidget(tabs, 1)
        root.addWidget(self.crono)  # franja de cronologia del semaforo (siempre visible)

        self.setCentralWidget(central)

    def _run_cycle(self, force_fetch: bool = False) -> None:
        self.btn.setEnabled(False)
        self.btn.setText("Analizando... (~25s)")
        self._worker = _Worker(force_fetch=force_fetch)
        self._worker.finished.connect(self._on_result)
        self._worker.start()

    def closeEvent(self, event) -> None:
        try:
            mt5_shutdown()
        except Exception:
            pass
        super().closeEvent(event)

    def _apply_result(self, result: dict, alert: bool = True) -> None:
        self.semaforo.update_state(
            result.get("semaforo", {}).get("color", "DESCCONOCIDO"),
            result.get("semaforo", {}).get("reasons", []),
        )
        self.sesgo.update_state(result.get("bias", "—"), result.get("wyckoff", {}).get("M15"))
        self.noticias.update_state(result.get("noticias", []), result.get("fuente_noticias", ""))
        verd = result.get("veredicto", {}) or {}
        self.resumen.update_state(
            result.get("estructura"),
            result.get("bias", ""),
            verd.get("votes"),
            extra={"wyckoff_m15": result.get("wyckoff", {}).get("M15", {})},
        )
        self.mapa.refresh()
        self.estado.update_state()
        self.crono.update_state()

        color = result.get("semaforo", {}).get("color", "DESCCONOCIDO")
        if alert and self._last_color is not None and color != self._last_color:
            if color == "ROJO" or (color == "AMARILLO" and self._last_color == "VERDE"):
                razones = "\n".join(result.get("semaforo", {}).get("reasons", [])[:3])
                alertar(color, f"{SYMBOL}: semaforo {color}\n{razones}")
                log_event("main_window", "alerta_disparada", symbol=SYMBOL,
                          data={"de": self._last_color, "a": color})
        self._last_color = color

        if result.get("errores"):
            log_error("main_window", "ciclo_con_errores", Exception("; ".join(result["errores"])))

    def _on_result(self, result: dict) -> None:
        self.btn.setEnabled(True)
        self.btn.setText("Actualizar ahora")
        self._apply_result(result, alert=True)


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
