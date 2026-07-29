"""Pestaña #2 — LABORATORIO DE SETUP (DIDACTICA).

Explica QUE pasa y POR QUE con los datos REALES del motor (engine.run_cycle):
  - Modelo ICT auto-detectado (reusa modelo_ict de resumen_widget) + por que gano.
  - Fase Wyckoff M15 + significado (regla del mercado, no opinion).
  - Logica del setup paso a paso (sesgo -> estructura -> entrada/SL/TP -> R:R).
  - Veredicto honesto: si el R:R < 1:2 el setup se DESCARTA y se explica por que.

Los 4 cuadros principales se muestran en una grilla 2x2 (aprovecha el espacio).
No inventa: todo refleja el dict que produce engine.run_cycle(). Se actualiza
con el mismo timer de 5 min de la app (0 CPU extra entre refrescos).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QGroupBox, QScrollArea,
    QFrame, QTextBrowser, QPushButton, QHBoxLayout, QMessageBox,
)

from app_observador.ui.resumen_widget import modelo_ict
from app_observador.core.position_sizer_bridge import (
    extract_levels,
    send_and_place_limit,
    send_result_to_position_sizer,
)

ROOT = Path(__file__).resolve().parents[3]
RULEBOOK = ROOT / "docs" / "WYCKOFF_RULEBOOK.md"
ICT_DIR = ROOT / "docs" / "ict"

# Significado corto de cada fase Wyckoff (para la explicacion didactica).
WYCKOFF_SIGNIFICADO = {
    "Accumulation": "El smart money esta COMPRANDO en silencio. El precio forma un rango de absorcion. Senal de posible subida (Markup) despues.",
    "Markup": "Fase de SUBLIDA. El precio ya rompio el rango hacia arriba. Tendencia alcista en marcha.",
    "Distribution": "El smart money esta VENDIENDO en silencio. El precio forma un rango de entrega. Senal de posible bajada (Markdown) despues.",
    "Markdown": "Fase de BAJADA. El precio ya rompio el rango hacia abajo. Tendencia bajista en marcha.",
    "Spring": "Falsa rupture ABAJO del rango (los osos pican el stop) y el precio vuelve adentro. Senal alcista (trampa).",
    "Upthrust": "Falsa rupture ARRIBA del rango (los toros pican el stop) y el precio vuelve adentro. Senal bajista (trampa).",
    "SOS": "Sign of Strength. Confirmacion de fuerza compradora (rompimiento de la linea de oferta).",
    "SOW": "Sign of Weakness. Confirmacion de debilidad vendedora (rompimiento de la linea de demanda).",
}

# Modelos ICT: explicacion didactica de por que aplica cada uno.
ICT_EXPLICACION = {
    "Unicorn (FVG + OB)": "El mas limpio: hay un FVG y un Order Block JUNTOS en M15. Las dos huellas institucionales coinciden en el mismo sitio. Alta probabilidad.",
    "Silver Bullet": "Es intradia: el precio barre liquidez y deja un FVG dentro de la killzone (London o NY AM). Setup rapido, ideal para scalping.",
    "Turtle Soup": "Es de REVERSION: el precio barre la liquidez y hace un fakeout CONTRA la tendencia mayor (D1), luego gira. Hay que esperar el MSS opuesto.",
    "Power of Three (PO3)": "Es de CONTINUACION: el sesgo y la tendencia D1 van alineados. El smart money acumula, manipula (sweep) y sigue la marea.",
}


def _fmt(x) -> str:
    try:
        return f"{float(x):.5f}"
    except Exception:
        return str(x)


class LabSetupWidget(QWidget):
    """Pestaña didactica: explica el setup con datos reales del motor."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Scroll para que quepa en cualquier tamano de ventana
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        # Titulo
        title = QLabel("LABORATORIO DE SETUP — por que el mercado dice esto")
        title.setStyleSheet("color: #7fb3ff; font-weight: bold; font-size: 15px;")
        root.addWidget(title)

        # Grilla 2x2 con los 4 cuadros principales (aprovecha todo el espacio).
        grid = QGridLayout()
        grid.setSpacing(10)
        # Reparto uniforme de los 4 cuadrantes.
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        root.addLayout(grid)

        # --- Grupo 1: MODELO ICT DETECTADO (arriba-izquierda) ---
        self.g_modelo = QGroupBox("1) MODELO ICT DETECTADO (auto-adaptado a tus datos)")
        self.g_modelo.setStyleSheet("QGroupBox { color: #9fd3a0; font-weight: bold; }")
        m_layout = QVBoxLayout(self.g_modelo)
        self.lbl_modelo = QTextBrowser()
        self.lbl_modelo.setOpenExternalLinks(False)
        self.lbl_modelo.setStyleSheet(
            "background-color: #15171c; color: #e6e6e6; border: none; font-size: 12px;")
        m_layout.addWidget(self.lbl_modelo)
        grid.addWidget(self.g_modelo, 0, 0)

        # --- Grupo 2: FASE WYCKOFF (arriba-derecha) ---
        self.g_wyk = QGroupBox("2) FASE WYCKOFF (la regla del mercado)")
        self.g_wyk.setStyleSheet("QGroupBox { color: #c9a3ff; font-weight: bold; }")
        w_layout = QVBoxLayout(self.g_wyk)
        self.lbl_wyk = QTextBrowser()
        self.lbl_wyk.setStyleSheet(
            "background-color: #15171c; color: #e6e6e6; border: none; font-size: 12px;")
        w_layout.addWidget(self.lbl_wyk)
        grid.addWidget(self.g_wyk, 0, 1)

        # --- Grupo 3: LOGICA DEL SETUP (abajo-izquierda) ---
        self.g_logica = QGroupBox("3) LOGICA DEL SETUP (paso a paso)")
        self.g_logica.setStyleSheet("QGroupBox { color: #7fb3ff; font-weight: bold; }")
        l_layout = QVBoxLayout(self.g_logica)
        self.lbl_logica = QTextBrowser()
        self.lbl_logica.setStyleSheet(
            "background-color: #15171c; color: #e6e6e6; border: none; font-size: 12px;")
        l_layout.addWidget(self.lbl_logica)
        grid.addWidget(self.g_logica, 1, 0)

        # --- Grupo 4: VEREDICTO HONESTO (abajo-derecha) ---
        self.g_veredicto = QGroupBox("4) VEREDICTO HONESTO (con R:R)")
        self.g_veredicto.setStyleSheet("QGroupBox { color: #ffd479; font-weight: bold; }")
        v_layout = QVBoxLayout(self.g_veredicto)
        self.lbl_veredicto = QTextBrowser()
        self.lbl_veredicto.setStyleSheet(
            "background-color: #15171c; color: #e6e6e6; border: none; font-size: 12px;")
        v_layout.addWidget(self.lbl_veredicto)
        grid.addWidget(self.g_veredicto, 1, 1)

        scroll.setWidget(inner)

        # Action bar OUTSIDE scroll — always visible (was easy to miss below the 2x2 grid).
        action = QHBoxLayout()
        action.setContentsMargins(14, 8, 14, 10)
        self.btn_ps = QPushButton("Colocar orden LIMIT (Entry+SL+TP)")
        self.btn_ps.setMinimumHeight(40)
        self.btn_ps.setToolTip(
            "Coloca una orden pendiente LIMIT en MT5 demo con Entry/SL/TP del setup.\n"
            "También escribe el handoff al Position Sizer (settings + archivo)."
        )
        from app_observador.ui.theme import btn_primary
        self.btn_ps.setStyleSheet(btn_primary() + " QPushButton { font-size: 13px; min-height: 36px; }")
        self.btn_ps.clicked.connect(self._on_send_to_position_sizer)
        action.addWidget(self.btn_ps)
        self.lbl_ps_status = QLabel("Sin plan cargado.")
        self.lbl_ps_status.setStyleSheet("color: #aaa; font-size: 11px;")
        self.lbl_ps_status.setWordWrap(True)
        action.addWidget(self.lbl_ps_status, 1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll, 1)
        outer.addLayout(action)

        self._last_result: dict | None = None

    # ------------------------------------------------------------------ update
    def update_state(self, result: dict | None = None) -> None:
        self._last_result = result
        from app_observador.core.position_sizer_bridge import extract_levels
        # Skip heavy HTML rebuild when tab is not visible (caller may still set _last_result)
        if result is not None and not self.isVisible():
            # Still keep LIMIT button state for top bar when parent asks via extract_levels
            levels = None
            try:
                levels = extract_levels(result)
            except Exception:
                levels = None
            if levels is None:
                self.btn_ps.setEnabled(False)
                self.lbl_ps_status.setText("Plan en memoria (abrí Lab para ver detalle).")
            else:
                self.btn_ps.setEnabled(True)
                flag = "R:R ok" if levels.valid_rr else "R:R bajo (demo ok)"
                self.lbl_ps_status.setText(
                    f"Listo: {levels.side} E={levels.entry:.5f} SL={levels.sl:.5f} "
                    f"TP={levels.tp:.5f} (1:{levels.rr:.2f}, {flag})"
                )
            return
        if not result or not result.get("estructura"):
            self.lbl_modelo.setHtml(
                "<span style='color:#ff8a80'>Sin datos del motor (MT5 no disponible). "
                "El loop actualiza los datos cada 5 min.</span>")
            self.lbl_wyk.setHtml("")
            self.lbl_logica.setHtml("")
            self.lbl_veredicto.setHtml("")
            self.btn_ps.setEnabled(False)
            self.lbl_ps_status.setText("Sin plan cargado.")
            return

        estructura = result["estructura"]
        bias = result.get("bias", "NEUTRAL (esperar)")
        votes = result.get("veredicto", {}).get("votes")
        m15 = estructura.get("M15", {})

        # ---- (1) Modelo ICT ----
        nombre, libro, score = modelo_ict(estructura, bias, votes)
        explica = ICT_EXPLICACION.get(nombre, "")
        libro_ref = f"  [docs/ict/{libro}]" if (ICT_DIR / libro).exists() else ""
        self.lbl_modelo.setHtml(
            f"<p style='font-size:14px;'>"
            f"<b style='color:#9fd3a0'>Modelo mas coherente: {nombre}</b> "
            f"(score {score}){libro_ref}</p>"
            f"<p style='color:#cfcfcf;'>{explica}</p>"
            f"<p style='color:#888;'>El modelo se elige por PUNTUACION sobre tus datos reales "
            f"(sweep, BOS, FVG, OB, killzone, alineacion D1), no esta escrito a mano.</p>"
        )

        # ---- (2) Fase Wyckoff ----
        wyk = estructura.get("WYCKOFF_M15") or {}
        fase = (wyk.get("phase_es", "") or "").split()[0] if wyk.get("phase_es") else ""
        sesgo_w = wyk.get("bias", "")
        conf = wyk.get("confidence")
        conf_txt = f" {conf:.0%}" if isinstance(conf, (int, float)) else ""
        sig = WYCKOFF_SIGNIFICADO.get(fase, "")
        # FASE B: eventos ya calculados por fase_wyckoff_m15 (WyckoffAgent).
        eventos = wyk.get("eventos") or []
        evt_txt = ", ".join(str(e) for e in eventos) if eventos else "ninguno claro"
        regla = ""
        if RULEBOOK.exists():
            regla = "  [docs/WYCKOFF_RULEBOOK.md]"
        self.lbl_wyk.setHtml(
            f"<p style='font-size:14px;'>"
            f"<b style='color:#c9a3ff'>Fase M15: {wyk.get('phase_es','INDEFINIDA')}</b> "
            f"(sesgo {sesgo_w}{conf_txt}){regla}</p>"
            f"<p style='color:#9fe3ff;'><b>Eventos:</b> {evt_txt}</p>"
            f"<p style='color:#cfcfcf;'>{sig}</p>"
            f"<p style='color:#888;'>Wyckoff es una LEY del mercado (oferta/demanda), "
            f"no una opinion. Te dice en que tramo del ciclo esta el precio.</p>"
        )

        # ---- (3) Logica del setup ----
        dir_setup = "NEUTRAL"
        if isinstance(votes, dict):
            if votes.get("LONG", 0) > votes.get("SHORT", 0):
                dir_setup = "LONG"
            elif votes.get("SHORT", 0) > votes.get("LONG", 0):
                dir_setup = "SHORT"
        d1 = estructura.get("D1", {})
        h4 = estructura.get("H4", {})
        tendencia_d1 = d1.get("trend", "RANGING")
        bos_m15 = int(m15.get("bos_dir", 0) or 0)
        sweep_up = bool(m15.get("sweep_up")) or bool(h4.get("sweep_up"))
        sweep_down = bool(m15.get("sweep_down")) or bool(h4.get("sweep_down"))

        pasos = []
        pasos.append(f"<b>1. Sesgo del dia:</b> {bias} "
                     f"(votos L:{votes.get('LONG',0) if votes else 0} / "
                     f"S:{votes.get('SHORT',0) if votes else 0}).")
        pasos.append(f"<b>2. Contexto (la marea):</b> D1 {tendencia_d1} / "
                     f"H4 {h4.get('trend','?')}. "
                     + ("Alineado." if tendencia_d1 in ("BULLISH", "BEARISH") else "En rango -> sin marea clara."))
        pasos.append(f"<b>3. Estructura M15:</b> BOS {'alcista' if bos_m15==1 else 'bajista' if bos_m15==-1 else 'intacta'} "
                     f"(dir={bos_m15}).")
        if sweep_up or sweep_down:
            pasos.append(f"<b>4. Liquidez barrida:</b> "
                         f"{'arriba (BSL)' if sweep_up else ''}"
                         f"{' y ' if sweep_up and sweep_down else ''}"
                         f"{'abajo (SSL)' if sweep_down else ''}. El smart money cazo stops antes de girar.")
        else:
            pasos.append(f"<b>4. Liquidez:</b> aun sin barrido confirmado. Esperar el sweep.")
        pasos.append(f"<b>5. Direccion del setup:</b> {dir_setup} "
                     f"(del sesgo + BOS M15).")
        pasos.append("<b>6. Entrada/SL/TP:</b> ver abajo en el veredicto (zona OTE M15).")
        pasos.append("<b>7. Filtro final:</b> R:R >= 1:2 (regla Stellar). Si no llega, el setup se DESCARTA.")
        self.lbl_logica.setHtml(
            "<br>".join(f"<p style='color:#e6e6e6; margin:2px 0;'>{p}</p>" for p in pasos)
        )

        # ---- (4) Veredicto honesto con R:R ----
        verd = result.get("veredicto", {})
        zone = verd.get("zone_note", "")
        invalid = verd.get("invalidation")
        target = verd.get("target")
        plan_ok = None
        rr_txt = ""
        if dir_setup in ("LONG", "SHORT") and invalid is not None and target is not None and m15:
            lo, hi = m15.get("ote_long", (0, 0)) if dir_setup == "LONG" else m15.get("ote_short", (0, 0))
            try:
                entry = (float(lo) + float(hi)) / 2.0
                risk = abs(entry - float(invalid))
                reward = abs(float(target) - entry)
                rr = reward / risk if risk > 0 else 0
                plan_ok = rr >= 2.0
                rr_txt = (f"<b>Entrada (OTE):</b> {_fmt(entry)} &nbsp;|&nbsp; "
                          f"<b>SL:</b> {_fmt(invalid)} &nbsp;|&nbsp; "
                          f"<b>TP:</b> {_fmt(target)}<br>"
                          f"<b>R:R:</b> 1:{rr:.2f} &nbsp;->&nbsp; "
                          f"<span style='color:#9fd3a0;'>VALIDO</span>" if plan_ok else
                          f"<span style='color:#ff8a80;'>DESCARTAR (R:R &lt; 1:2)</span>")
                if not plan_ok:
                    rr_txt += " &nbsp;<i>El beneficio no compensa el riesgo. Mejor esperar otro setup.</i>"
            except Exception:
                rr_txt = ""
        color = result.get("semaforo", {}).get("color", "")
        nota_color = {
            "VERDE": "<span style='color:#9fd3a0;'>VERDE = hay setup valido Y limpio. El cielo esta despejado y el R:R sirve.</span>",
            "AMARILLO": "<span style='color:#ffd479;'>AMARILLO = contexto limpio pero SIN setup valido (R:R &lt; 1:2) o noticia roja. Esperar.</span>",
            "ROJO": "<span style='color:#ff8a80;'>ROJO = no operar hoy (noticia roja + sesgo opuesto, o sesgo neutral sin confirmar).</span>",
        }.get(color, "")
        self.lbl_veredicto.setHtml(
            f"<p style='color:#e6e6e6;'>{zone}</p>"
            + (f"<p style='color:#e6e6e6;'>{rr_txt}</p>" if rr_txt else
               "<p style='color:#ff8a80;'>Sin plan de trade (sesgo NEUTRAL o sin datos de invalidacion).</p>")
            + (f"<p style='color:#cfcfcf;'>{nota_color}</p>" if nota_color else "")
            + "<p style='color:#888;'>El semaforo solo dice VERDE cuando hay un setup BUENO y el R:R sirve. "
            "Si dice AMARILLO, el mapa esta limpio pero el setup no conviene hoy.</p>"
            + "<p style='color:#7fb3ff;'>Demo: botón "
            "<b>Colocar orden LIMIT</b> envía Entry/SL/TP a MT5 como pendiente "
            "(y actualiza archivos del Position Sizer).</p>"
        )

        levels = extract_levels(result)
        if levels is None:
            self.btn_ps.setEnabled(False)
            self.lbl_ps_status.setText(
                "Botón desactivado: falta LONG/SHORT + OTE + SL + TP en el veredicto."
            )
        else:
            self.btn_ps.setEnabled(True)
            flag = "R:R ok" if levels.valid_rr else "R:R bajo (demo ok)"
            self.lbl_ps_status.setText(
                f"Listo: {levels.side} E={levels.entry:.5f} SL={levels.sl:.5f} "
                f"TP={levels.tp:.5f} (1:{levels.rr:.2f}, {flag})"
            )

    def _on_send_to_position_sizer(self) -> None:
        """Write PS handoff + place pending LIMIT with SL/TP on MT5 (demo)."""
        try:
            levels = extract_levels(self._last_result)
        except Exception as e:
            QMessageBox.warning(self, "Colocar orden", f"Error leyendo plan: {e}")
            return
        if levels is None:
            QMessageBox.information(
                self,
                "Colocar orden",
                "No hay números de orden ahora.\n"
                "Necesitás sesgo LONG/SHORT, zona OTE M15, invalidación (SL) y target (TP).",
            )
            return

        detail = "\n".join(levels.summary_lines())
        warn = ""
        if not levels.valid_rr:
            warn = (
                "\n\n⚠ Lab marcaría DESCARTAR (R:R < 1:2). "
                "Igual podés colocar LIMIT en demo para probar el cableado."
            )
        box = QMessageBox(self)
        box.setWindowTitle("Colocar orden LIMIT en MT5")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(
            "¿Colocar orden PENDIENTE (LIMIT/STOP) en la cuenta demo de MT5?\n\n"
            f"{levels.side} {levels.symbol}\n"
            f"Entry {levels.entry:.5f}  |  SL {levels.sl:.5f}  |  TP {levels.tp:.5f}\n"
            f"Riesgo ~{levels.risk_pct:.2f}% del balance (lotaje auto).\n\n"
            "También actualiza archivos del Position Sizer (Entry/SL/TP)."
        )
        box.setDetailedText(detail + warn)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return

        try:
            levels, paths, order = send_and_place_limit(self._last_result)
        except ValueError as e:
            QMessageBox.warning(self, "Colocar orden", str(e))
            return
        except OSError as e:
            QMessageBox.critical(self, "Colocar orden", f"Archivo handoff:\n{e}")
            return
        except Exception as e:
            QMessageBox.critical(self, "Colocar orden", f"MT5 error:\n{e}")
            return

        clip = (
            f"{levels.symbol} {levels.side}\n"
            f"Entry: {levels.entry:.5f}\n"
            f"SL: {levels.sl:.5f}\n"
            f"TP: {levels.tp:.5f}\n"
            f"R:R 1:{levels.rr:.2f}"
        )
        try:
            QGuiApplication.clipboard().setText(clip)
        except Exception:
            pass

        sizing = order.get("sizing") or {}
        ok = bool(order.get("ok"))
        ticket = order.get("ticket") or 0
        status = (
            f"OK ticket={ticket} vol={order.get('volume')} "
            f"@ {order.get('price')}  ret={order.get('retcode')}"
            if ok
            else f"FALLÓ ret={order.get('retcode')} {order.get('comment')}"
        )
        self.lbl_ps_status.setText(status)
        open_orders = order.get("open_orders") or []
        orders_txt = "\n".join(
            f"  #{o['ticket']} px={o['price_open']} SL={o['sl']} TP={o['tp']} vol={o['volume']}"
            for o in open_orders
        ) or "  (sin pendientes en el libro)"
        path_txt = "\n".join(str(p) for p in paths)
        msg = (
            f"{'ORDEN COLOCADA' if ok else 'FALLO AL COLOCAR'}\n\n"
            f"{detail}\n\n"
            f"Lot: {sizing.get('lot')}  risk$: {sizing.get('risk_money')}\n"
            f"retcode: {order.get('retcode')}  {order.get('comment')}\n"
            f"ticket: {ticket}\n\n"
            f"Pendientes {levels.symbol} ahora:\n{orders_txt}\n\n"
            f"Handoff PS:\n{path_txt}\n\n"
            "Para ver Entry/SL/TP en el panel del Position Sizer: "
            "quitá y volvé a adjuntar el EA en el chart EURUSD "
            "(settings en disco ya actualizados), o recompilá el PS parcheado."
        )
        if ok:
            QMessageBox.information(self, "Orden LIMIT", msg)
        else:
            QMessageBox.critical(self, "Orden LIMIT", msg)
