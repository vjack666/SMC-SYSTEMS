"""Ventana principal del observador.

Ensambla los widgets y corre el motor (engine.run_cycle) en un hilo separado para
no bloquear la UI durante los ~25s que tarda el análisis real (Wyckoff + mapas).
Refresca cada REFRESH_SECONDS (5 min) y al pulsar 'Actualizar'.

Layout UI:
  - Pestaña Principal: centro de mando (botones, plan/semáforo, sesgo, estado,
    resumen, crono).
  - Otras pestañas: full-bleed (solo su contenido; sin chrome de semáforo/botones).

Comportamiento tipo WhatsApp (single-instance + bandeja del sistema):
  - Solo puede haber UNA instancia de la ventana. Si ya corre y se abre de
    nuevo, la nueva avisa a la vieja para que se traiga al frente y se cierra.
  - La X de la ventana la ESCONDE a la bandeja (no la mata): el proceso sigue
    vivo y el loop/vigilante siguen corriendo atras.
  - Desde el icono de la bandeja (al lado del reloj) podes Mostrar / Actualizar
    / Salir. El boton 'Salir' de la UI SI cierra el proceso del todo.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal, QTimer, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QTabWidget, QSystemTrayIcon, QMenu,
)

from datetime import datetime, timezone

from app_observador.config import REFRESH_SECONDS, SYMBOL
from app_observador.core.blackbox import log_event, log_error
from app_observador.core.data_retention import run_retention
from app_observador.core.mt5_status import shutdown as mt5_shutdown
from app_observador.core.engine import load_cached
from app_observador.ui.mapa_widget import MapaWidget
from app_observador.ui.market_state_widget import MarketStateWidget
from app_observador.ui.noticias_widget import NoticiasWidget
from app_observador.ui.resumen_widget import ResumenWidget
from app_observador.ui.estado_widget import EstadoWidget
from app_observador.ui.crono_widget import CronoWidget
from app_observador.ui.lab_setup_widget import LabSetupWidget
from app_observador.ui.senal_widget import SenalWidget
from app_observador.ui.autopilot_widget import AutopilotWidget
from app_observador.ui.plan_strip_widget import PlanStripWidget
from app_observador.ui.scanner_widget import ScannerWidget
from app_observador.ui.chat_widget import ChatWidget
from app_observador.ui.contexto_multiactivo_widget import ContextoMultiactivoWidget
from app_observador.ui.contexto_multiactivo_widget import _SYMBOLS
from app_observador.ui.theme import app_stylesheet, btn_primary, btn_danger, btn_ghost

# Canal de envío de alertas (popup/beep) eliminado: se empieza de 0.
# La app ahora solo muestra el veredicto en la UI, sin disparar avisos externos.


class _Worker(QThread):
    finished = Signal(dict)

    def __init__(self, force_fetch: bool = False, symbol: str | None = None) -> None:
        super().__init__()
        self._force = force_fetch
        self._symbol = symbol

    def run(self) -> None:
        try:
            from app_observador.core import engine
            result = engine.run_cycle(force_fetch=self._force, symbol=self._symbol)
            self.finished.emit(result)
        except Exception as e:
            log_error("main_window", "worker_crash", e)
            self.finished.emit({"errores": [f"worker: {e}"], "symbol": self._symbol})


def _make_tray_icon() -> QIcon:
    """Icono de bandeja. Usa el recurso del proyecto si existe; si no, un
    icono por defecto de Qt para no romper en ausencia de asset."""
    asset = Path(__file__).resolve().parent.parent / "resources" / "icon.ico"
    if asset.exists():
        return QIcon(str(asset))
    # Fallback: icono generico de la app (una ventana) provisto por el estilo.
    return QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_ComputerIcon)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"SMC OBSERVADOR — {SYMBOL}")
        self.setMinimumSize(900, 600)
        self.resize(1366, 820)

        # Widgets — semáforo vive SOLO en plan_strip (chip compacto), no duplicado
        self.mapa = MapaWidget()
        self.noticias = NoticiasWidget()
        self.resumen = ResumenWidget()
        self.estado = EstadoWidget()
        self.crono = CronoWidget()
        self.lab = LabSetupWidget()
        self.senal = SenalWidget()
        self.autopilot = AutopilotWidget()
        self.plan_strip = PlanStripWidget()
        self.market_state = MarketStateWidget()
        self.scanner = ScannerWidget()
        self.chat = ChatWidget()
        self.contexto_multiactivo = ContextoMultiactivoWidget()
        self.chat.set_scanner_provider(self.scanner.last_report_text)
        self.chat.set_context_provider(self._chat_app_context)
        self.scanner.cycle_refreshed.connect(self._on_scanner_cycle)
        self._last_result: dict | None = None

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

        # Preload Contexto multiactivo: mostrar progreso y lanzar pares restantes
        # en background inmediatamente despues del primer ciclo principal.
        try:
            self.contexto_multiactivo.update_state(
                _build_contexto_state(
                    self._last_result or {
                        "symbol": SYMBOL,
                        "bias": "NEUTRAL",
                        "veredicto": {},
                        "estructura": {},
                        "wyckoff": {},
                    },
                    force_symbol=SYMBOL,
                )
            )
            self.contexto_multiactivo.set_preload_progress(1, len(_SYMBOLS), SYMBOL)
            self.contexto_multiactivo.mark_loading(SYMBOL, False)
            rest = [s for s in _SYMBOLS if s != SYMBOL]
            if rest:
                self._contexto_queue = rest[:]
                QTimer.singleShot(0, self._contexto_next)
        except Exception as e:
            log_error("main_window", "preload_contexto_init", e)

        # Loop observador siempre ON por defecto
        try:
            from app_observador.core.process_control import ensure_loop_running

            ensure_loop_running()
        except Exception as e:
            log_error("main_window", "ensure_loop_startup", e)

        # ---- BANDEJA (systray) tipo WhatsApp ----
        self._setup_tray()

    def _build_layout(self) -> None:
        """Layout: chrome (botones, semáforo, sesgo, estado, crono) SOLO en Principal.

        Otras pestañas usan casi toda la ventana — sin plan strip ni barra de acciones.
        """
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(0)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setObjectName("mainTabs")
        self.tabs = tabs

        # ── PRINCIPAL: centro de mando completo ──────────────────────────
        tab_principal = QWidget()
        tp = QVBoxLayout(tab_principal)
        tp.setContentsMargins(6, 8, 6, 6)
        tp.setSpacing(10)

        # Barra superior: identidad + acciones
        top = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title = QLabel(f"SMC OBSERVADOR  ·  {SYMBOL}")
        title.setStyleSheet("color: #e6e6e6; font-size: 15px; font-weight: 800;")
        title_col.addWidget(title)
        self.subtitle = QLabel("Motor sequence · demo LIMIT · sin bot automático")
        self.subtitle.setStyleSheet("color: #6b7280; font-size: 11px;")
        title_col.addWidget(self.subtitle)
        top.addLayout(title_col)
        top.addStretch()
        self.lbl_updated = QLabel("Última actualización: —")
        self.lbl_updated.setStyleSheet(
            "color: #9aa0a6; font-size: 11px; padding-right: 8px;"
        )
        top.addWidget(self.lbl_updated)
        self.btn_max = QPushButton("Pantalla completa")
        self.btn_max.setStyleSheet(btn_ghost())
        self.btn_max.clicked.connect(self._toggle_max)
        top.addWidget(self.btn_max)
        self.btn = QPushButton("Actualizar")
        self.btn.setToolTip(
            f"Fuerza un ciclo completo (~25s+). Auto cada {REFRESH_SECONDS // 60} min."
        )
        self.btn.clicked.connect(lambda: self._run_cycle(force_fetch=True))
        top.addWidget(self.btn)
        self.btn_ps = QPushButton("Colocar orden LIMIT")
        self.btn_ps.setToolTip(
            "Coloca LIMIT en MT5 demo con Entry/SL/TP del plan canónico (sequence)."
        )
        self.btn_ps.setStyleSheet(btn_primary())
        self.btn_ps.setEnabled(False)
        self.btn_ps.clicked.connect(self._send_to_position_sizer)
        top.addWidget(self.btn_ps)
        self.btn_exit = QPushButton("Salir")
        self.btn_exit.setStyleSheet(btn_danger())
        self.btn_exit.clicked.connect(self._real_exit)
        top.addWidget(self.btn_exit)
        tp.addLayout(top)

        # Semáforo + plan
        tp.addWidget(self.plan_strip)

        # FASE A: Panel MARKET STATE always-on (síntesis del pipeline)
        tp.addWidget(self.market_state)

        # Estado del loop/vigilante
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row1.addWidget(self.estado, 1)
        tp.addLayout(row1)

        # Resumen de estructura (detalle Principal)
        tp.addWidget(self.resumen, 1)
        tp.addWidget(self.crono)
        tabs.addTab(tab_principal, "Principal")

        # ── RESTO: full-bleed (solo contenido de la pestaña) ─────────────
        def _full_tab(widget: QWidget) -> QWidget:
            page = QWidget()
            lay = QVBoxLayout(page)
            lay.setContentsMargins(4, 6, 4, 4)
            lay.setSpacing(0)
            lay.addWidget(widget, 1)
            return page

        # SEGUNDA pestaña: SETUP DEL DIA (señal del sistema + macro). insertTab(1)
        # la deja inmediatamente despues de "Principal".
        tabs.insertTab(1, _full_tab(self.senal), "Señal")

        # TERCERA pestaña: AUTO (semi-automatización grid DEMO).
        tabs.insertTab(2, _full_tab(self.autopilot), "Auto")

        tabs.addTab(_full_tab(self.lab), "Lab Setup")
        tabs.addTab(_full_tab(self.contexto_multiactivo), "Contexto")
        tabs.addTab(_full_tab(self.noticias), "Noticias")
        tabs.addTab(_full_tab(self.scanner), "Escáner")
        tabs.addTab(_full_tab(self.chat), "Chat")
        tabs.addTab(_full_tab(self.mapa), "Mapa ICT")

        root.addWidget(tabs, 1)
        self.setCentralWidget(central)

        # Deferred heavy updates per tab (keeps tab switches snappy)
        self._pending_result: dict | None = None
        self._dirty_tabs: set[str] = set()
        tabs.currentChanged.connect(self._on_tab_changed)

    # ------------------------------------------------------------------ #
    # Bandeja del sistema (systray)
    # ------------------------------------------------------------------ #
    def _setup_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(_make_tray_icon())
        self.tray.setToolTip(f"SMC OBSERVADOR — {SYMBOL} (oculto)")

        menu = QMenu(self)
        act_mostrar = menu.addAction("Mostrar ventana")
        act_mostrar.triggered.connect(self._show_window)
        act_update = menu.addAction("Actualizar ahora")
        act_update.triggered.connect(lambda: self._run_cycle(force_fetch=True))
        menu.addSeparator()
        act_salir = menu.addAction("Salir (cerrar todo)")
        act_salir.triggered.connect(self._real_exit)

        self.tray.setContextMenu(menu)
        # Doble-clic en el icono de bandeja -> mostrar la ventana.
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason) -> None:
        # DoubleClick (2) o Trigger (1, clic en Windows) -> mostrar.
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick,
                      QSystemTrayIcon.ActivationReason.Trigger):
            self._show_window()

    def _show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _real_exit(self) -> None:
        """Cierre REAL: mata el proceso del todo (boton 'Salir' / menu bandeja)."""
        try:
            mt5_shutdown()
        except Exception:
            pass
        QApplication.quit()

    # ------------------------------------------------------------------ #
    # Cierre de la X: se esconde a la bandeja, NO se muere.
    # ------------------------------------------------------------------ #
    def closeEvent(self, event) -> None:
        # Si el usuario pidio salir de verdad (boton 'Salir'), _real_exit ya
        # llamo a QApplication.quit() y este evento no llega oculto.
        # La X por defecto => ocultar a la bandeja y seguir vivo.
        event.ignore()
        self.hide()
        if self.tray.isVisible():
            self.tray.showMessage(
                "SMC OBSERVADOR",
                "Seguí corriendo en segundo plano. Cerrá desde la bandeja (clic derecho → Salir).",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )

    def _run_cycle(self, force_fetch: bool = False, *, symbol: str | None = None) -> None:
        self.btn.setEnabled(False)
        self.btn.setText("Analizando…")
        self.lbl_updated.setText("Analizando… (puede tardar ~30–60s con sequence)")
        self.subtitle.setText("Motor sequence · calculando plan canónico…")
        self._worker = _Worker(force_fetch=force_fetch, symbol=symbol)
        self._worker.finished.connect(self._on_result)
        self._worker.start()

    def _toggle_max(self) -> None:
        """Alterna pantalla completa / ventana normal (ajustable)."""
        if self.isMaximized():
            self.showNormal()
            self.btn_max.setText("Pantalla completa")
        else:
            self.showMaximized()
            self.btn_max.setText("Restaurar")

    def _send_to_position_sizer(self) -> None:
        """Top-bar shortcut: same action as Lab Setup button."""
        if hasattr(self.lab, "_on_send_to_position_sizer"):
            self.lab._on_send_to_position_sizer()
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Position Sizer",
                "Lab Setup no tiene el envío disponible. Reiniciá la app.",
            )

    def _tab_name(self, index: int) -> str:
        if not hasattr(self, "tabs") or index < 0:
            return ""
        return self.tabs.tabText(index)

    def _on_tab_changed(self, index: int) -> None:
        """Apply deferred work only for the tab that became visible."""
        name = self._tab_name(index)
        if not name or not self._pending_result:
            # Still allow mapa dirty paint via showEvent
            return
        # Defer one event-loop tick so the tab widget paints first (feels instant)
        QTimer.singleShot(0, lambda n=name: self._flush_tab(n))

    def _flush_tab(self, name: str) -> None:
        result = self._pending_result or self._last_result
        if not result:
            return
        if name == "Principal":
            if "Principal" in self._dirty_tabs:
                self._update_principal(result)
                self._dirty_tabs.discard("Principal")
        elif name == "Señal":
            if "Señal" in self._dirty_tabs:
                self.senal.update_state(result)
                self._dirty_tabs.discard("Señal")
        elif name == "Lab Setup":
            if "Lab Setup" in self._dirty_tabs:
                self.lab.update_state(result)
                self._dirty_tabs.discard("Lab Setup")
        elif name == "Contexto":
            if "Contexto" in self._dirty_tabs:
                self.contexto_multiactivo.update_state(self._build_contexto_state(result))
                self._dirty_tabs.discard("Contexto")
        elif name == "Noticias":
            if "Noticias" in self._dirty_tabs:
                # Diario ICT: usa el result completo (estructura/bias/veredicto/
                # noticias) para armar el informe en columnas. Pinta cache al toque
                # o dispara generación async según la franja horaria.
                self.noticias.set_result(result)
                self._dirty_tabs.discard("Noticias")
        elif name == "Escáner":
            if "Escáner" in self._dirty_tabs:
                self.scanner.update_state(result)
                self._dirty_tabs.discard("Escáner")
        elif name == "Mapa ICT":
            if "Mapa ICT" in self._dirty_tabs:
                self.mapa.refresh()
                self._dirty_tabs.discard("Mapa ICT")
        # Chat: no heavy paint from cycle (uses context on send)

    def _update_principal(self, result: dict) -> None:
        """Heavy-ish principal chrome — only when Principal is (or becomes) visible."""
        self.plan_strip.update_state(result)
        self.market_state.update_state(result)
        verd = result.get("veredicto", {}) or {}
        self.resumen.update_state(
            result.get("estructura"),
            result.get("bias", ""),
            verd.get("votes"),
            extra={"wyckoff_m15": result.get("wyckoff", {}).get("M15", {})},
        )
        self.crono.update_state()
        # Levels for LIMIT button without full Lab HTML rebuild if possible
        try:
            from app_observador.core.position_sizer_bridge import extract_levels
            levels = extract_levels(result)
            self.btn_ps.setEnabled(levels is not None)
        except Exception:
            try:
                self.lab.update_state(result)
                levels_ok = bool(
                    getattr(self.lab, "btn_ps", None) and self.lab.btn_ps.isEnabled()
                )
                self.btn_ps.setEnabled(levels_ok)
            except Exception:
                pass

    def _build_contexto_state(self, result: dict) -> dict:
        """Build state dict for ContextoMultiactivoWidget from engine result."""
        symbol = result.get("symbol") or result.get("SYMBOL") or "EURUSD"
        estruct = result.get("estructura") or {}
        m15 = estruct.get("M15") or {}
        h4 = estruct.get("H4") or {}
        d1 = estruct.get("D1") or {}
        wyk = result.get("wyckoff") or {}
        wyk_m15 = wyk.get("M15") or {}

        bias = str(result.get("bias", "") or "NEUTRAL")
        bias_razon = "Alineación macro + intraday del motor." if bias not in ("NEUTRAL", "") else "Sin sesgo claro todavía."

        bos_dir = int(m15.get("bos_dir") or 0)
        choch_dir = int(m15.get("choch_dir") or 0)
        if bos_dir == 1 and choch_dir == 1:
            estructura_txt = "BOS alcista + CHOCH confirmado en M15."
        elif bos_dir == -1 and choch_dir == -1:
            estructura_txt = "BOS bajista + CHOCH confirmado en M15."
        elif bos_dir != 0:
            estructura_txt = f"BOS {'alcista' if bos_dir==1 else 'bajista'} en M15; CHOCH pendiente."
        elif h4.get("bos_dir"):
            estructura_txt = f"H4 muestra BOS {'alcista' if h4['bos_dir']==1 else 'bajista'}; M15 sin ruptura aún."
        else:
            estructura_txt = "Sin BOS/CHOCH claros todavía. Esperar ruptura o sweep."

        zonas = []
        if m15.get("fvg_state") and m15["fvg_state"] not in ("-", ""):
            zonas.append(f"FVG {m15.get('fvg_type','')} activo")
        if m15.get("ob_active"):
            zonas.append(f"OB {'comprador' if m15.get('ob_dir')=='LONG' else 'vendedor'} intacto")
        if not zonas:
            zonas.append("Sin zonas activas claras ahora")
        zonas_txt = "; ".join(zonas)

        ejec_tf = "M15"
        ejec_senal = "Sweep + retorno a OB / FVG respetado."
        if not m15.get("bos_dir"):
            ejec_tf = "H4 → M15"
            ejec_senal = "Primero buscar sweep/barrido; luego confirmar CHOCH."
        ejecucion_txt = f"Timeframe de ejecución: {ejec_tf}. Señal válida = {ejec_senal}"

        sesion_txt = "Killzone Londres + NY."
        sesion_parts = []
        try:
            from app_observador.core.timezone import killzone_activa_ahora
            if killzone_activa_ahora():
                sesion_parts.append("killzone activa ahora")
            else:
                sesion_parts.append("killzone fuera ahora")
        except Exception:
            sesion_parts.append("zona de sesión disponible")
        sesion_txt = "Killzone " + ", ".join(sesion_parts) + ". Operar con volumen cuando hay liquidez."

        recomendacion = "En construcción: "
        recomendacion += ", ".join([
            x for x in [
                "sweep limpio en M15" if not m15.get("sweep_up") and not m15.get("sweep_down") else "",
                "CHOCH" if not choch_dir else "",
                "POI anclado a narrativa HTF" if not str(result.get("veredicto") or {}).__contains__("anchored") else "",
            ] if x
        ])
        if recomendacion == "En construcción: ":
            recomendacion = "Checklist verde: sesgo definido, estructura clara, zonas y confirmación M5 listas."
        else:
            recomendacion += " — esperar confirmación antes de entrar."

        return {
            "symbol": str(symbol),
            "bias": bias,
            "bias_razon": bias_razon,
            "estructura": estructura_txt,
            "zonas": zonas_txt,
            "ejecucion": ejecucion_txt,
            "sesion": sesion_txt,
            "recomendacion": recomendacion,
        }

    def _apply_result(self, result: dict, alert: bool = True) -> None:
        self._last_result = result
        self._pending_result = result

        # Always: lightweight chrome that lives on Principal (cheap labels)
        now = datetime.now(timezone.utc).strftime("%H:%M UTC")
        self.lbl_updated.setText(f"Última actualización: {now}")
        # FASE 5 (UI): "EN CONSTRUCCIÓN" (str no vacío) daba True con bool().
        # canonical_is_ready distingue los 3 estados: solo dict con entry = plan vigente.
        from app_observador.ui.format_helpers import canonical_is_ready

        has_can = canonical_is_ready(result.get("canonical"))
        self.subtitle.setText(
            "Motor sequence · plan canónico listo · demo LIMIT"
            if has_can
            else "Motor sequence · sin plan fresco · detalle en pestañas"
        )

        # Mark all detail tabs dirty; flush only the active one now
        self._dirty_tabs = {
            "Principal",
            "Señal",
            "Lab Setup",
            "Contexto",
            "Noticias",
            "Escáner",
            "Mapa ICT",
        }
        # Scanner always keeps last_result pointer (cheap)
        self.scanner.update_state(result)

        active = self._tab_name(self.tabs.currentIndex()) if hasattr(self, "tabs") else "Principal"
        if active == "Principal" or not active:
            self._update_principal(result)
            self._dirty_tabs.discard("Principal")
        else:
            # Still keep plan numbers for LIMIT if user returns to Principal later
            try:
                from app_observador.core.position_sizer_bridge import extract_levels

                self.btn_ps.setEnabled(extract_levels(result) is not None)
            except Exception:
                pass
            self._flush_tab(active)

        # Estado: uses process cache — safe to call; no double PowerShell
        try:
            self.estado.update_state()
        except Exception:
            pass

        color = result.get("semaforo", {}).get("color", "DESCCONOCIDO")
        if alert and self._last_color is not None and color != self._last_color:
            if color == "ROJO" or (color == "AMARILLO" and self._last_color == "VERDE"):
                log_event(
                    "main_window",
                    "alerta_disparada",
                    symbol=SYMBOL,
                    data={"de": self._last_color, "a": color},
                )
        self._last_color = color

        if result.get("errores"):
            log_error(
                "main_window",
                "ciclo_con_errores",
                Exception("; ".join(result["errores"])),
            )

    def _on_result(self, result: dict) -> None:
        self.btn.setEnabled(True)
        self.btn.setText("Actualizar")
        self._apply_result(result, alert=True)
        self._contexto_maybe_update(result)

    def _on_scanner_cycle(self, result: dict) -> None:
        """When Escáner runs a fresh cycle, keep the rest of the UI in sync."""
        self._apply_result(result, alert=False)

    def _chat_app_context(self) -> str:
        """Contexto vivo para el MODELO: ficha + motor + noticias (sin clicks del user)."""
        from app_observador.core.chat_context import build_chat_context

        card = ""
        try:
            card = self.scanner.last_report_text() or ""
        except Exception:
            card = ""
        return build_chat_context(self._last_result, scanner_text=card or None)


    def preload_contexto(self, symbols: list[str]) -> None:
        if getattr(self, "_contexto_preloading", False):
            return
        self._contexto_preloading = True
        self._contexto_queue = list(symbols)
        self._contexto_next()

    def _contexto_next(self) -> None:
        if not getattr(self, "_contexto_queue", []):
            self._contexto_preloading = False
            return
        sym = self._contexto_queue.pop(0)
        try:
            w = self.contexto_multiactivo
            w.set_preload_progress(
                len(w._cache),
                len(getattr(w, "_SYMBOLS", _SYMBOLS)),
                sym,
            )
            w.mark_loading(sym, True)
        except Exception:
            pass
        worker = _Worker(force_fetch=False, symbol=sym)
        worker.finished.connect(self._on_contexto_preload)
        worker.start()

    def _on_contexto_preload(self, result: dict) -> None:
        try:
            self.contexto_multiactivo.update_state(
                _build_contexto_state(result, force_symbol=result.get("symbol")),
            )
        except Exception:
            pass
        self._contexto_next()

    def _contexto_maybe_update(self, result: dict) -> None:
        try:
            sym = result.get("symbol")
            if sym in _SYMBOLS:
                self.contexto_multiactivo.update_state(
                    _build_contexto_state(result, force_symbol=sym),
                )
        except Exception:
            pass

def _build_contexto_state(result: dict, *, force_symbol: str | None = None) -> dict:
    """Build state dict for ContextoMultiactivoWidget from engine result."""
    symbol = force_symbol or result.get("symbol") or result.get("SYMBOL") or "EURUSD"
    estruct = result.get("estructura") or {}
    m15 = estruct.get("M15") or {}
    h4 = estruct.get("H4") or {}
    wyk = result.get("wyckoff") or {}
    wyk_m15 = wyk.get("M15") or {}

    bias = str(result.get("bias", "") or "NEUTRAL")
    bias_razon = "Alineación macro + intraday del motor." if bias not in ("NEUTRAL", "") else "Sin sesgo claro todavía."

    bos_dir = int(m15.get("bos_dir") or 0)
    choch_dir = int(m15.get("choch_dir") or 0)
    if bos_dir == 1 and choch_dir == 1:
        estructura_txt = "BOS alcista + CHOCH confirmado en M15."
    elif bos_dir == -1 and choch_dir == -1:
        estructura_txt = "BOS bajista + CHOCH confirmado en M15."
    elif bos_dir != 0:
        estructura_txt = f"BOS {'alcista' if bos_dir==1 else 'bajista'} en M15; CHOCH pendiente."
    elif h4.get("bos_dir"):
        estructura_txt = f"H4 muestra BOS {'alcista' if h4['bos_dir']==1 else 'bajista'}; M15 sin ruptura aún."
    else:
        estructura_txt = "Sin BOS/CHOCH claros todavía. Esperar ruptura o sweep."

    zonas = []
    if m15.get("fvg_state") and m15["fvg_state"] not in ("-", ""):
        zonas.append(f"FVG {m15.get('fvg_type','')} activo")
    if m15.get("ob_active"):
        zonas.append(f"OB {'comprador' if m15.get('ob_dir')=='LONG' else 'vendedor'} intacto")
    if not zonas:
        zonas.append("Sin zonas activas claras ahora")
    zonas_txt = "; ".join(zonas)

    ejec_tf = "M15"
    ejec_senal = "Sweep + retorno a OB / FVG respetado."
    if not m15.get("bos_dir"):
        ejec_tf = "H4 → M15"
        ejec_senal = "Primero buscar sweep/barrido; luego confirmar CHOCH."
    ejecucion_txt = f"Timeframe de ejecución: {ejec_tf}. Señal válida = {ejec_senal}"

    sesion_txt = "Killzone Londres + NY."
    sesion_parts = []
    try:
        from app_observador.core.timezone import killzone_activa_ahora
        if killzone_activa_ahora():
            sesion_parts.append("killzone activa ahora")
        else:
            sesion_parts.append("killzone fuera ahora")
    except Exception:
        sesion_parts.append("zona de sesión disponible")
    sesion_txt = "Killzone " + ", ".join(sesion_parts) + ". Operar con volumen cuando hay liquidez."

    recomendacion = "En construcción: "
    recomendacion += ", ".join(
        [
            x for x in [
                "sweep limpio en M15" if not m15.get("sweep_up") and not m15.get("sweep_down") else "",
                "CHOCH" if not choch_dir else "",
                "POI anclado a narrativa HTF" if not str(result.get("veredicto") or {}).__contains__("anchored") else "",
            ] if x
        ]
    )
    if recomendacion == "En construcción: ":
        recomendacion = "Checklist verde: sesgo definido, estructura clara, zonas y confirmación M5 listas."
    else:
        recomendacion += " — esperar confirmación antes de entrar."

    return {
        "symbol": str(symbol),
        "bias": bias,
        "bias_razon": bias_razon,
        "estructura": estructura_txt,
        "zonas": zonas_txt,
        "ejecucion": ejecucion_txt,
        "sesion": sesion_txt,
        "recomendacion": recomendacion,
    }

def main() -> int:
    from scripts._single_instance import SingleInstanceUi

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(app_stylesheet())
    QApplication.setApplicationName("SMC_OBSERVADOR")
    # La X oculta la ventana a la bandeja (closeEvent hace event.ignore()+hide()).
    # Sin esto, al no quedar ventanas visibles Qt mata el event loop y el
    # proceso muere -> al reabrir, el server SMC_observador_ui queda zombie y
    # la nueva instancia sale silenciosa (se "cierra sola").
    app.setQuitOnLastWindowClosed(False)

    # Single-instance tipo WhatsApp: si ya hay otro observador vivo, le avisamos
    # que se muestre y este proceso sale. Si somos el primero, arrancamos el
    # server que escucha ese aviso.
    si = SingleInstanceUi("observador_ui")
    if not si.is_first():
        si.activate_other()
        return 0

    win = MainWindow()
    si.listen(win)  # el server vive mientras 'si' y 'win' vivan
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
