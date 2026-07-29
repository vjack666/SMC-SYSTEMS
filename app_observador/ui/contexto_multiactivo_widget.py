"""Contexto multiactivo: panel de contexto ICT sin recomputar nada.

- Selector horizontal de activos: EURUSD, GBPUSD, NZDUSD, USDCHF, USDJPY,
  AUDUSD, USDCAD, XAUUSD. El activo resaltado indica qué `state` se está
  mostrando.
- Panel dummy con secciones en español simple:
  1) SESGO, 2) ESTRUCTURA, 3) ZONAS, 4) EJECUCIÓN, 5) SESIÓN, 6) RECOMENDACIÓN.
- Consume un dictionary `state` por método público `update_state(state: dict)`.
  No recalcula nada; el provider le pasa el diccionario ya armado.
"""
from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app_observador.ui.theme import (
    ACCENT,
    BORDER,
    GREEN,
    RED,
    TEXT,
    TEXT_DIM,
    YELLOW,
)

_SYMBOLS = [
    "EURUSD",
    "GBPUSD",
    "NZDUSD",
    "USDCHF",
    "USDJPY",
    "AUDUSD",
    "USDCAD",
    "XAUUSD",
]

_DEFAULT_STATE: Dict = {
    "symbol": "EURUSD",
    "bias": "Bullish",
    "bias_razon": "HTF closed BOS + retorno a OB; fluye dinero en compradores.",
    "estructura": "BOS confirmado en H4; rango limpio arriba/abajo.",
    "zonas": "FVG vigente arriba del precio; OB de absorción intacto abajo.",
    "ejecucion": "Mirá M15 si hay sweep/CHOCH; señal válida = retorno al OB.",
    "sesion": "Killzone Londres + NY; Montevideo está fuera ahora.",
    "recomendacion": "En construcción: falta sweep limpio en M15, esperar CHOCH para entrada.",
}


class _SectionCard(QFrame):
    def __init__(self, title: str, body: str = "") -> None:
        super().__init__()
        self.setObjectName("contextSection")
        self.setStyleSheet(
            f"QFrame#contextSection {{"
            f"background-color: #15171c;"
            f"border: 1px solid {BORDER};"
            f"border-radius: 8px;"
            f"margin-top: 8px;"
            f"}}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)
        lbl_title = QLabel(title)
        lbl_title.setObjectName("sectionTitle")
        lbl_title.setStyleSheet(
            f"color: {ACCENT}; font-weight: 700; letter-spacing: 0.3px;"
        )
        root.addWidget(lbl_title)

        self.lbl_body = QLabel(body or "—")
        self.lbl_body.setWordWrap(True)
        self.lbl_body.setStyleSheet(
            f"color: {TEXT}; font-size: 13px;"
            f"background: transparent; border: none;"
        )
        self.lbl_body.setTextFormat(Qt.PlainText)
        root.addWidget(self.lbl_body, 1)

    def set_body(self, text: str) -> None:
        self.lbl_body.setText(text or "—")


class ContextoMultiactivoWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("contextoMultiactivo")
        self._symbol_buttons: Dict[str, QPushButton] = {}
        self._active_symbol: str = _DEFAULT_STATE.get("symbol", _SYMBOLS[0])
        self._current_state: Dict = dict(_DEFAULT_STATE)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 8, 6, 8)
        root.setSpacing(8)

        header = QLabel("Contexto multiactivo")
        header.setStyleSheet(f"color: {TEXT}; font-size: 15px; font-weight: 800;")
        root.addWidget(header)

        self.lbl_progress = QLabel("Iniciando contexto…")
        self.lbl_progress.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        root.addWidget(self.lbl_progress)

        self._cache: Dict[str, Dict] = {}
        self._loading: Dict[str, bool] = {s: False for s in _SYMBOLS}

        # Selector de activos
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        for sym in _SYMBOLS:
            btn = QPushButton(sym)
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda checked, s=sym: self._on_symbol_clicked(s))
            btn.setStyleSheet(self._btn_stylesheet(sym == self._active_symbol))
            if sym == self._active_symbol:
                btn.setChecked(True)
            toolbar.addWidget(btn)
            self._symbol_buttons[sym] = btn
        root.addLayout(toolbar)

        # Panel scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }}"
            f"QScrollBar:vertical {{ background: #15171c; width: 10px; }}"
            f"QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; }}"
        )
        panel = QWidget()
        panel.setStyleSheet(f"background-color: #0f1115;")
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self._section_sesgo = _SectionCard("1) SESGO", _DEFAULT_STATE.get("bias", ""))
        self._section_estructura = _SectionCard("2) ESTRUCTURA", _DEFAULT_STATE.get("estructura", ""))
        self._section_zonas = _SectionCard("3) ZONAS", _DEFAULT_STATE.get("zonas", ""))
        self._section_ejecucion = _SectionCard("4) EJECUCIÓN", _DEFAULT_STATE.get("ejecucion", ""))
        self._section_sesion = _SectionCard("5) SESIÓN", _DEFAULT_STATE.get("sesion", ""))
        self._section_recomendacion = _SectionCard("6) RECOMENDACIÓN", _DEFAULT_STATE.get("recomendacion", ""))

        for section in [
            self._section_sesgo,
            self._section_estructura,
            self._section_zonas,
            self._section_ejecucion,
            self._section_sesion,
            self._section_recomendacion,
        ]:
            v.addWidget(section)
        v.addStretch(1)

        scroll.setWidget(panel)
        root.addWidget(scroll, 1)

        self._render_state(self._active_symbol)

    def update_state(self, state: dict) -> None:
        if not isinstance(state, dict):
            return
        state.setdefault("symbol", self._active_symbol)
        state.setdefault("bias", "")
        state.setdefault("bias_razon", "")
        state.setdefault("estructura", "")
        state.setdefault("zonas", "")
        state.setdefault("ejecucion", "")
        state.setdefault("sesion", "")
        state.setdefault("recomendacion", "")

        sym = state.get("symbol") or self._active_symbol
        if sym in _SYMBOLS:
            self._cache[sym] = dict(state)
            self._loading[sym] = False
            self._update_progress_label()
            self._current_state = dict(state)
            self._active_symbol = sym
            self._highlight_symbol_button(sym)
        self._render_state(self._active_symbol)

    def _update_progress_label(self) -> None:
        done = len(self._cache)
        total = len(_SYMBOLS)
        self.lbl_progress.setText(f"Iniciando contexto… {done}/{total}")

    def set_preload_progress(self, done: int, total: int, current_symbol: str = "") -> None:
        if current_symbol:
            self.lbl_progress.setText(f"Iniciando contexto… {done}/{total} ({current_symbol})")
        elif done >= total:
            self.lbl_progress.setText("Contexto listo.")
        else:
            self.lbl_progress.setText(f"Iniciando contexto… {done}/{total}")

    def mark_loading(self, symbol: str, loading: bool = True) -> None:
        if symbol not in _SYMBOLS:
            return
        self._loading[symbol] = loading
        if loading:
            self._active_symbol = symbol
            self._highlight_symbol_button(symbol)
            self._render_state(symbol)

    def _on_symbol_clicked(self, symbol: str) -> None:
        self._active_symbol = symbol
        self._current_state.setdefault("symbol", symbol)
        self._highlight_symbol_button(symbol)
        self._render_state(symbol)

    def _highlight_symbol_button(self, symbol: str) -> None:
        for sym, btn in self._symbol_buttons.items():
            btn.setChecked(sym == symbol)
            btn.setStyleSheet(self._btn_stylesheet(sym == symbol))

    def _btn_stylesheet(self, active: bool) -> str:
        bg = ACCENT if active else "#1a1d24"
        fg = "#0f1115" if active else TEXT_DIM
        border = ACCENT if active else BORDER
        return (
            f"QPushButton {{"
            f"background-color: {bg};"
            f"color: {fg};"
            f"border: 1px solid {border};"
            f"border-radius: 6px;"
            f"padding: 6px 12px;"
            f"font-weight: 600;"
            f"}}"
            f"QPushButton:hover {{"
            f"background-color: {ACCENT if not active else bg};"
            f"color: {'#0f1115' if not active else fg};"
            f"}}"
        )

    def _apply_sections(self, bias, estructura, zonas, ejecucion, sesion, recomendacion) -> None:
        self._section_sesgo.set_body(bias)
        self._section_estructura.set_body(estructura)
        self._section_zonas.set_body(zonas)
        self._section_ejecucion.set_body(ejecucion)
        self._section_sesion.set_body(sesion)
        self._section_recomendacion.set_body(recomendacion)

    def _render_state(self, symbol: str) -> None:
        use_symbol = symbol or self._active_symbol
        if self._loading.get(use_symbol, False):
            self._apply_sections(
                bias="Cargando…",
                estructura="Cargando…",
                zonas="Cargando…",
                ejecucion="Cargando…",
                sesion="Cargando…",
                recomendacion="Calculando. Si falta data para este par, el sistema lo indica abajo.",
            )
            return

        state = self._cache.get(use_symbol)
        if state is None:
            state = self._current_state if self._current_state.get("symbol") == use_symbol else {}
        if not state:
            state = _DEFAULT_STATE

        self._apply_sections(
            bias=state.get("bias", "") or "",
            estructura=state.get("estructura", "") or "",
            zonas=state.get("zonas", "") or "",
            ejecucion=state.get("ejecucion", "") or "",
            sesion=state.get("sesion", "") or "",
            recomendacion=state.get("recomendacion", "") or "En construcción: aún no hay datos suficientes, esperar siguiente ciclo.",
        )
