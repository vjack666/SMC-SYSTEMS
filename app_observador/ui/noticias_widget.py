"""Pestaña NOTICIAS rediseñada: 'Diario ICT' en columnas tipo periódico.

Renderiza el informe generado por app_observador.core.news_ai (datos REALES del
motor + prosa LLM opcional) en 3 columnas estilo diario, que se actualiza según
la franja horaria (Asia / Londres / NY / Cierre). La generación con LLM corre en
un hilo aparte para NO congelar la UI; si ya hay cache de la franja, pinta al toque.

Mantiene update_state(events, fuente) por compatibilidad con main_window, pero
usa el informe del motor como fuente primaria.
"""
from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PySide6.QtWidgets import QTextBrowser

from app_observador.core import news_ai


class _NewsWorker(QThread):
    """Genera el informe en background (LLM puede tardar)."""

    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, result: dict, force_llm: bool = True) -> None:
        super().__init__()
        self._result = result
        self._force_llm = force_llm

    def run(self) -> None:
        try:
            rep = news_ai.generar(self._result, force_llm=self._force_llm)
            self.done.emit(rep)
        except Exception as e:  # pragma: no cover - defensive
            self.failed.emit(str(e))


class NoticiasWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._result: dict | None = None
        self._worker: _NewsWorker | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # Masthead + controles
        top = QHBoxLayout()
        self.title = QLabel("DIARIO ICT · NOTICIAS")
        self.title.setStyleSheet(
            "color:#e6e6e6; font-weight:800; font-size:14px; letter-spacing:1px;"
        )
        top.addWidget(self.title)
        top.addStretch()

        self.lbl_franja = QLabel("")
        self.lbl_franja.setStyleSheet("color:#9aa0a6; font-size:11px;")
        top.addWidget(self.lbl_franja)

        self.btn_regen = QPushButton("Regenerar ahora")
        self.btn_regen.setToolTip(
            "Fuerza la regeneración del informe (puede llamar al LLM)."
        )
        self.btn_regen.setStyleSheet("background:#1a1d24; color:#7fb3ff; border:1px solid #2a2e38; border-radius:4px; padding:3px 8px;")
        self.btn_regen.clicked.connect(self._regen)
        top.addWidget(self.btn_regen)
        layout.addLayout(top)

        # Cuerpo del periódico
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setStyleSheet("background:#15171c; border:1px solid #2a2e38; border-radius:6px;")
        layout.addWidget(self.browser, 1)

        # Placeholder hasta el primer ciclo
        self.browser.setHtml(
            "<div style='color:#6b7280; padding:12px;'>Esperando el primer "
            "ciclo del motor para armar el Diario ICT…</div>"
        )

    # ── API pública (main_window) ─────────────────────────────────────────
    def update_state(self, events: list[dict], fuente: str = "") -> None:
        """Compatibilidad: recibe el ciclo completo vía _apply_result.
        main_window llama con (result['noticias'], fuente); pero necesitamos el
        result entero. Por eso main_window now llama set_result() en su lugar.
        Esta firma la dejamos como no-op segura si alguien la invoca."""
        return

    def set_result(self, result: dict) -> None:
        """Pinta el informe de la franja actual. Si hay cache, al toque;
        si no, dispara worker async (no congela)."""
        self._result = result
        rep = news_ai.get_cached()
        if rep is not None:
            self._render(rep)
            return
        # No hay cache para esta franja → armar en background (determinista, SIN
        # LLM: el dashboard es superficie de LECTURA; las credenciales/LLM las
        # maneja el Chat tab. El LLM solo se invoca con "Regenerar ahora").
        franja = news_ai.franja_actual()
        self.lbl_franja.setText(f"Franja {franja} · armando…")
        self._start_worker(force_llm=False)

    def _regen(self) -> None:
        if self._result is None:
            return
        self._start_worker(force_llm=True)

    # ── Interno ───────────────────────────────────────────────────────────
    def _start_worker(self, force_llm: bool) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._worker = _NewsWorker(self._result or {}, force_llm=force_llm)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _on_done(self, rep: dict) -> None:
        self._render(rep)

    def _on_fail(self, err: str) -> None:
        # Fallback determinista (sin LLM) para no dejar la pestaña vacía
        try:
            if self._result is not None:
                rep = news_ai._prosa_determinista(
                    news_ai._extract(self._result), news_ai.franja_actual()
                )
                rep["franja"] = news_ai.franja_actual()
                rep["fuente"] = "determinista (error LLM)"
                rep["generado_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                rep["glosario"] = news_ai.glosario_html()
                self._render(rep)
                return
        except Exception:
            pass
        self.browser.setHtml(
            f"<div style='color:#c0392b; padding:12px;'>No se pudo generar el "
            f"informe: {err}</div>"
        )

    def _render(self, rep: dict) -> None:
        # Reusa resolve_chat_config (vía _llm_available) para indicar estado de
        # la IA sin duplicar lógica de credenciales.
        llm_ok = news_ai._llm_available()
        estado_ia = "IA ACTIVA" if llm_ok else "IA SIN CONEXIÓN · MODO LECTURA"
        self.lbl_franja.setText(
            f"Franja {rep.get('franja','')} · {rep.get('generado_utc','')} · "
            f"{rep.get('fuente','')} · {estado_ia}"
        )
        self.browser.setHtml(news_ai.render_html(rep))


# ── Compatibilidad: usado por resumen_widget (pestaña Resumen) ────────────
def _fmt_precio(x) -> str:
    """Formatea precio a 5 decimales; devuelve '' si no es número válido."""
    try:
        v = float(x)
        if v == 0.0 or v != v:  # 0.0 o NaN -> el motor no calculó BOS
            return ""
        return f"{v:.5f}"
    except (TypeError, ValueError):
        return ""


def resumen_estructura(estructura: dict) -> str:
    """Texto en criollo desde los datos reales de cada temporalidad.

    FASE E: muestra el nivel numérico del BOS (bos_level) y destaca el sweep
    de liquidez con color (rojo BSL / verde SSL) vía rich text. Si el motor no
    calculó BOS (bos_level 0.0/None) -> no inventa, solo dice estructura intacta.
    """
    if not estructura:
        return "Sin datos de estructura (MT5 no disponible)."

    def linea(tf: str) -> str:
        d = estructura.get(tf, {})
        if not d:
            return f"{tf}: sin datos"
        trend = {"": "indefinido", "BULLISH": "alcista", "BEARISH": "bajista",
                 "RANGING": "en rango"}.get(d.get("trend", ""), d.get("trend", ""))
        bos_dir = d.get("bos_dir", 0)
        bos_status = d.get("bos_status", "")
        bos_level = _fmt_precio(d.get("bos_level"))
        if bos_dir == 1 and bos_status == "active":
            bos = "BOS alcista (rompio estructura arriba)"
        elif bos_dir == -1 and bos_status == "active":
            bos = "BOS bajista (rompio estructura abajo)"
        elif bos_dir == 1:
            bos = "intenta BOS alcista (aun no confirma)"
        elif bos_dir == -1:
            bos = "intenta BOS bajista (aun no confirma)"
        else:
            bos = "estructura intacta"
        if bos_level:
            bos += f" @ {bos_level}"
        partes = [f"{tf}: {trend}, {bos}"]
        if d.get("sweep_up"):
            partes.append(
                "<b><span style='color:#ff6b6b;'>🔼 SWEEP BUY (BSL barrida)</span></b>")
        if d.get("sweep_down"):
            partes.append(
                "<b><span style='color:#51cf66;'>🔽 SWEEP SELL (SSL barrida)</span></b>")
        return "; ".join(partes) + "."

    wyk = estructura.get("WYCKOFF_M15", {})
    wyk_txt = ""
    if wyk:
        fase = wyk.get("phase_es", "")
        sesgo = wyk.get("bias", "")
        if fase or sesgo:
            wyk_txt = f"\nWyckoff M15: {fase} ({sesgo})".strip()
    return "\n".join([linea("D1"), linea("H4"), linea("M15")]) + wyk_txt
