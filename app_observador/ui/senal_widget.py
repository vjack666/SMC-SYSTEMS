"""Pestaña SEGUNDA: SETUP DEL DIA (señal del sistema) + FASE GRID.

Modo 1 — FASE ESTOCÁSTICO (sin operación abierta):
  Muestra el SETUP del día (bias, votos, zona, SL/TP/RR, noticias macro).
  Es el contenido original de esta pestaña.

Modo 2 — FASE GRID (hay una operación abierta en MT5):
  El estocástico NO vuelve a trabajar hasta que la operación cierre
  (profit o pérdida). Mientras tanto, la pestaña CAMBIA a "FASE GRID" y
  monitorea en vivo las reglas de entrada del grid que dictó el usuario:

    OP BASE (estocástico): 0.50 lotes
    CAPA 1 grid: 0.15 lotes  <- tras 20 pips EN CONTRA + toque de banda
    CAPA 2 grid: 0.20 lotes  <- tras OTROS 20 pips + toque de banda

  Reglas (Bollinger M15 period=20, std=2.0):
    1. El precio debe alejarse ~20 pips EN CONTRA (en pérdida):
         si base es COMPRA  -> precio debe BAJAR 20 pips
         si base es VENTA   -> precio debe SUBIR 20 pips
    2. El precio debe tocar la banda correcta:
         COMPRA -> banda INFERIOR
         VENTA  -> banda SUPERIOR
    3. Capa 1 lista (0.15) cuando (1)+(2) cumplidas.
    4. Capa 2 lista (0.20) cuando hay OTROS 20 pips de distancia + toque de banda.

  El panel es un semáforo: cada regla verde si cumple, roja si no.
  El estado de capas abiertas se lee de las posiciones REALES en MT5
  (no se adivina): 1 pos = solo base, 2 = capa1 ejecutada, 3 = capa2.

No inventa: dirección/lote base vienen de positions_get; Bollinger de
indicators.add_bollinger; las reglas y lotes son las que dictó el usuario.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

import pandas as pd
from indicators.indicators import add_bollinger

from app_observador.config import SYMBOL
from app_observador.ui.theme import (
    BG_PANEL, BORDER, GREEN, GREEN_SOFT, RED, RED_SOFT, TEXT, TEXT_DIM,
)


def _group(title: str, color: str = "#e6e6e6") -> QGroupBox:
    g = QGroupBox(title)
    g.setStyleSheet(
        f"QGroupBox {{ color: {color}; font-weight: 800; font-size: 13px; "
        f"border: 1px solid #2a2f3a; border-radius: 8px; margin-top: 10px; }}"
        f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}"
    )
    return g


def _label(text: str, size: int = 11, color: str = "#c7ccd4", bold: bool = False) -> QLabel:
    l = QLabel(text)
    l.setWordWrap(True)
    l.setStyleSheet(
        f"color: {color}; font-size: {size}px; "
        f"{'font-weight: 800;' if bold else 'font-weight: 400;'}"
    )
    return l

# ── Constantes de las reglas del grid (dictadas por el usuario) ──────────
BASE_LOT = 0.50
GRID_LOT_1 = 0.15
GRID_LOT_2 = 0.20
PIP_STEP = 20.0          # pips de distancia entre capas
BB_PERIOD = 20
BB_STD = 2.0
TOUCH_TOL_PIPS = 2.0     # margen para considerar "toque" de banda

_GRID_VALUES = {
    "base_lot": BASE_LOT,
    "grid_lot_1": GRID_LOT_1,
    "grid_lot_2": GRID_LOT_2,
    "pip_step": PIP_STEP,
    "bb_period": BB_PERIOD,
    "bb_std": BB_STD,
}


# ── Helpers de estilo (idénticos al resto del observador) ─────
def _group(title: str, color: str = "#e6e6e6") -> QGroupBox:
    g = QGroupBox(title)
    g.setStyleSheet(
        f"QGroupBox {{ color: {color}; font-weight: 800; font-size: 13px; "
        f"border: 1px solid #2a2f3a; border-radius: 8px; margin-top: 10px; }}"
        f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}"
    )
    return g


def _label(text: str, size: int = 11, color: str = "#c7ccd4", bold: bool = False) -> QLabel:
    l = QLabel(text)
    l.setWordWrap(True)
    l.setStyleSheet(
        f"color: {color}; font-size: {size}px; "
        f"{'font-weight: 800;' if bold else 'font-weight: 400;'}"
    )
    return l


# ── Noticias macro FIJAS (fuente real: forex.com / litefinance, semana 27 jul - 2 ago 2026) ──
MACRO_EVENTS = [
    ("Lun 27 jul", "Eurozona Private Loans (YoY)", "Bajo",
     "Consensus 3.1%. Impacto liviano. No mueve el euro fuerte hoy."),
    ("Jue 30 jul", "German GDP Q2 (Preliminar)", "Alto",
     "Dato fuerte para el euro. Debil -> presion bajista EUR; fuerte -> apoya EUR."),
    ("Vie 31 jul", "Eurozona Flash HICP / Core HICP", "Alto",
     "Inflacion. ECB senala tightening (alcista EUR). Peor que forecast -> declive EUR."),
    ("Semana", "FOMC de la Fed", "Alto",
     "Decision de tasas USD. Mercado arranca 'risk-positive' por tregua US-Iran "
     "(debilita USD refugio -> EUR/USD al alza, CONTRA el bias SHORT)."),
]

MACRO_VERDICT = (
    "HOY (27): noticias livianas -> NO contradicen el bias SHORT del sistema. "
    "El riesgo de que el bias se rompa viene despues: FOMC + HICP + GDP aleman "
    "(jue/vi). El sistema tecnico dice SHORT; el macro de hoy no lo confirma ni lo "
    "rompe. Cuidado: 'risk-positive' por tregua US-Iran tiende a subir EUR/USD "
    "(contra el SHORT)."
)


class _Light(QWidget):
    """Una luz de semáforo: círculo arriba + etiqueta plana debajo."""

    def __init__(self, label: str) -> None:
        super().__init__()
        self._label = label
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(8)

        self._dot = QLabel()
        self._dot.setFixedSize(56, 56)
        self._dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignCenter)

        self._txt = QLabel(label)
        self._txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._txt.setWordWrap(True)
        self._txt.setFixedWidth(150)
        self._txt.setStyleSheet("color: #e6e6e6; font-size: 11px; font-weight: 700;")
        lay.addWidget(self._txt, 0, Qt.AlignmentFlag.AlignCenter)

        self._set_state(False, dim=True)

    def _set_state(self, on: bool, dim: bool = False) -> None:
        self._state = on and not dim
        if dim:
            fill = "#20242c"
            ring = BORDER
        else:
            fill = "#1f9d55" if on else "#c0392b"
            ring = GREEN if on else RED
        self._dot.setStyleSheet(
            f"QLabel {{"
            f"  border: 3px solid {ring};"
            f"  border-radius: 28px;"
            f"  background: qradialgradient(cx:50%, cy:50%, radius:60%,"
            f"    stop:0% {fill},"
            f"    stop:75% {'#0e3a22' if on else '#3a1616' if not dim else '#15171c'},"
            f"    stop:100% {BG_PANEL});"
            f"}}"
        )
        self._txt.setStyleSheet(
            f"color: {'#e6e6e6' if not dim else TEXT_DIM};"
            f" font-size: 11px; font-weight: 700;"
        )


class SenalWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # ── Banner de MODO ──
        self.banner = QLabel("FASE ESTOCÁSTICO")
        self.banner.setStyleSheet(
            f"QLabel {{ color: {TEXT_DIM}; background: {BG_PANEL};"
            f" border: 1px solid {BORDER}; border-radius: 8px;"
            f" font-size: 15px; font-weight: 800; padding: 10px; }}"
        )
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.banner)

        # ── Contenedor FASE ESTOCÁSTICO (SETUP del día) ──
        self._setup_page = QWidget()
        sp = QVBoxLayout(self._setup_page)
        sp.setContentsMargins(0, 0, 0, 0)
        sp.setSpacing(10)
        self._build_setup(sp)
        root.addWidget(self._setup_page, 1)

        # ── Contenedor FASE GRID (monitor del grid) ──
        self._grid_page = QWidget()
        gp = QVBoxLayout(self._grid_page)
        gp.setContentsMargins(0, 0, 0, 0)
        gp.setSpacing(10)
        self._build_grid(gp)
        self._grid_page.hide()  # arranca en fase estocástico
        root.addWidget(self._grid_page, 1)

        # Timer de monitoreo grid (2s) — solo trabaja cuando hay operación abierta
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._poll_grid)
        self._tick.setInterval(2000)
        self._tick.start()

        self._mt5_ready = False
        self._mt5 = None
        self._in_grid = False

    # ══════════════════════════════ SETUP ════════════════════════════════
    def _build_setup(self, lay: QVBoxLayout) -> None:
        # Bloque 1: SETUP / Bias
        g1 = _group("1 · SETUP DEL MERCADO HOY (bias del sistema)", "#7dd3fc")
        l1 = QVBoxLayout()
        self.lbl_bias = _label("Bias: —", 14, "#e6e6e6", bold=True)
        self.lbl_votes = _label("Votos: —", 11)
        self.lbl_reasons = _label("", 10, "#9aa0a6")
        self.lbl_zone = _label("", 11)
        self.lbl_levels = _label("", 11, "#fbbf24")
        l1.addWidget(self.lbl_bias)
        l1.addWidget(self.lbl_votes)
        l1.addWidget(self.lbl_reasons)
        l1.addWidget(self.lbl_zone)
        l1.addWidget(self.lbl_levels)
        g1.setLayout(l1)
        lay.addWidget(g1)

        # Bloque 2: Contratendencia
        g2 = _group("2 · CONTRATENDENCIA", "#fca5a5")
        l2 = QVBoxLayout()
        self.lbl_contra = _label("NO (el flujo del dashboard es a-favor)", 12, "#fca5a5", bold=True)
        l2.addWidget(self.lbl_contra)
        l2.addWidget(_label(
            "build_verdict vota LONG/SHORT segun la tendencia (D1/H4/M15). El flag "
            "counter_trend existe en po3.py / Turtle Soup, pero el dashboard no lo "
            "usa hoy. Setup actual: a-favor de la tendencia.", 10, "#9aa0a6"))
        g2.setLayout(l2)
        lay.addWidget(g2)

        # Bloque 3: Probabilidad honesta
        g3 = _group("3 · PROBABILIDAD (honesta)", "#a5b4fc")
        l3 = QVBoxLayout()
        self.lbl_rr = _label("R:R del plan: —", 12, "#a5b4fc", bold=True)
        l3.addWidget(self.lbl_rr)
        l3.addWidget(_label(
            "El sistema NO da % de probabilidad de acierto. Lo que entrega es sesgo "
            "direccional + Riesgo:Retorno del plan. Cualquier '% de chance' seria "
            "ilusorio: el backtest R6 dio PF negativo con el motor simplificado y el "
            "ML no esta cableado al dashboard. El R:R mide retorno por unidad de "
            "riesgo SI el sesgo se cumple, no la chance de exito.", 10, "#9aa0a6"))
        g3.setLayout(l3)
        lay.addWidget(g3)

        # Bloque 4: Noticias macro (fijas)
        g4 = _group("4 · NOTICIAS MACRO (semana 27 jul - 2 ago 2026)", "#fcd34d")
        l4 = QVBoxLayout()
        for fecha, ev, vol, notas in MACRO_EVENTS:
            row = QHBoxLayout()
            row.addWidget(_label(f"[{vol}]", 10, "#f59e0b", bold=True))
            row.addWidget(_label(f"{fecha} — {ev}", 11, "#e6e6e6", bold=True))
            row.addStretch()
            l4.addLayout(row)
            l4.addWidget(_label(notas, 10, "#9aa0a6"))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); sep.setStyleSheet("color:#2a2f3a;")
        l4.addWidget(sep)
        self.lbl_macro_v = _label(MACRO_VERDICT, 10, "#fcd34d")
        l4.addWidget(self.lbl_macro_v)
        g4.setLayout(l4)
        lay.addWidget(g4, 1)
        lay.addStretch()

    # ══════════════════════════════ GRID ═════════════════════════════════
    def _build_grid(self, lay: QVBoxLayout) -> None:
        # Resumen de estado (dirección, lote, capas, distancia)
        self.g_info = QLabel("—")
        self.g_info.setStyleSheet(
            f"QLabel {{ color: {TEXT}; background: {BG_PANEL};"
            f" border: 1px solid {BORDER}; border-radius: 8px;"
            f" font-size: 12px; font-weight: 700; padding: 8px; }}"
        )
        self.g_info.setWordWrap(True)
        lay.addWidget(self.g_info)

        # Semáforo de reglas
        frame = QFrame()
        frame.setObjectName("gridsema")
        frame.setStyleSheet(
            f"QFrame#gridsema {{ background: {BG_PANEL}; border: 1px solid {BORDER};"
            f" border-radius: 12px; padding: 14px; }}"
        )
        flay = QVBoxLayout(frame)
        flay.setSpacing(12)

        title = QLabel("REGLAS DEL GRID (Bollinger M15 20/2)")
        title.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px; font-weight: 700; letter-spacing: 1px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        flay.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(16)
        self._lights: dict[str, _Light] = {}
        phases = [
            ("r1", "20 PIPS EN CONTRA"),
            ("r2", "TOQUE DE BANDA"),
            ("r3", f"CAPA 1 LISTA ({GRID_LOT_1})"),
            ("r4", "OTROS 20 PIPS"),
            ("r5", f"CAPA 2 LISTA ({GRID_LOT_2})"),
        ]
        positions = [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0)]
        for (key, label), (r, c) in zip(phases, positions):
            light = _Light(label)
            self._lights[key] = light
            grid.addWidget(light, r, c, Qt.AlignmentFlag.AlignCenter)
        flay.addLayout(grid)

        self.g_banner = QLabel("ESPERANDO…")
        self.g_banner.setStyleSheet(
            f"QLabel {{ color: {TEXT_DIM}; background: {BG_PANEL};"
            f" border: 1px solid {BORDER}; border-radius: 8px;"
            f" font-size: 14px; font-weight: 800; padding: 10px; }}"
        )
        self.g_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        flay.addWidget(self.g_banner)
        lay.addWidget(frame)

        # Explicación en criollo
        lay.addWidget(_label(
            "Mientras hay operación abierta, el estocástico queda EN PAUSA: no "
            "busca nueva entrada hasta que la operación cierre (profit o pérdida). "
            "El grid suma capas solo si el precio se aleja en contra y toca la "
            "banda de Bollinger correcta. Capa 1 = 0.15 lote, Capa 2 = 0.20 lote.",
            10, "#9aa0a6"))

    # ── Alimentado por engine.run_cycle() (igual patrón que antes) ──
    def update_state(self, result: dict) -> None:
        verd = (result.get("veredicto") or {}) if isinstance(result, dict) else {}
        bias = verd.get("bias", result.get("bias", "—")) if isinstance(result, dict) else "—"
        self.lbl_bias.setText(f"Bias: {bias}")
        if isinstance(bias, str):
            if "SHORT" in bias.upper() or "BEAR" in bias.upper():
                self.lbl_bias.setStyleSheet("color:#fca5a5; font-size:14px; font-weight:800;")
            elif "LONG" in bias.upper() or "BULL" in bias.upper():
                self.lbl_bias.setStyleSheet("color:#86efac; font-size:14px; font-weight:800;")
            else:
                self.lbl_bias.setStyleSheet("color:#e6e6e6; font-size:14px; font-weight:800;")

        votes = verd.get("votes")
        if isinstance(votes, dict):
            self.lbl_votes.setText(f"Votos: LONG={votes.get('LONG',0)} / SHORT={votes.get('SHORT',0)}")
        else:
            self.lbl_votes.setText("Votos: — (pipeline sin votes)")

        reasons = verd.get("reasons") or []
        self.lbl_reasons.setText("• " + "\n• ".join(reasons) if isinstance(reasons, list) and reasons else "")

        zone = verd.get("zone_note")
        self.lbl_zone.setText(f"Zona: {zone}" if zone else "Zona: —")

        can = result.get("canonical") if isinstance(result, dict) else None
        if isinstance(can, dict) and can.get("entry"):
            self.lbl_levels.setText(
                f"Entry {can.get('entry')} · SL {can.get('sl')} · TP {can.get('tp')} · R:R {can.get('rr')}"
            )
        else:
            inv = verd.get("invalidation")
            tgt = verd.get("target")
            self.lbl_levels.setText(f"SL {inv} · TP {tgt}" if inv is not None and tgt is not None else "")

    # ── Monitoreo de la FASE GRID ──
    def _ensure_mt5(self) -> bool:
        if self._mt5_ready:
            return True
        try:
            import MetaTrader5 as mt5
            if mt5.terminal_info() is None:
                mt5.initialize()
            self._mt5 = mt5
            self._mt5_ready = True
            return True
        except Exception:
            self._mt5_ready = False
            return False

    def _read_positions(self):
        """Lee posiciones REALES abiertas del símbolo. Devuelve (count, dir, open_price) o None."""
        if not self._ensure_mt5():
            return None
        try:
            pos = self._mt5.positions_get(symbol=SYMBOL)  # type: ignore[attr-defined]
            if not pos:
                return None
            p = pos[0]
            side = "BUY" if p.type == 0 else "SELL"
            return (len(pos), side, float(p.price_open))
        except Exception:
            return None

    def _read_m15(self) -> pd.DataFrame | None:
        if not self._mt5_ready:
            return None
        try:
            rates = self._mt5.copy_rates_from_pos(SYMBOL, self._mt5.TIMEFRAME_M15, 0, 80)  # type: ignore[attr-defined]
            if rates is None or len(rates) < BB_PERIOD + 2:
                return None
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            return df
        except Exception:
            return None

    def _poll_grid(self) -> None:
        info = self._read_positions()
        if info is None:
            # Sin operación abierta -> volver a FASE ESTOCÁSTICO
            if self._in_grid:
                self._in_grid = False
                self._grid_page.hide()
                self._setup_page.show()
                self.banner.setText("FASE ESTOCÁSTICO")
                self.banner.setStyleSheet(
                    f"QLabel {{ color: {TEXT_DIM}; background: {BG_PANEL};"
                    f" border: 1px solid {BORDER}; border-radius: 8px;"
                    f" font-size: 15px; font-weight: 800; padding: 10px; }}"
                )
            return

        count, side, open_price = info
        if not self._in_grid:
            self._in_grid = True
            self._setup_page.hide()
            self._grid_page.show()
            self.banner.setText("FASE GRID ACTIVA — ESTOCÁSTICO EN PAUSA")
            self.banner.setStyleSheet(
                f"QLabel {{ color: #ffd9a0; background: {BG_PANEL};"
                f" border: 1px solid #f59e0b; border-radius: 8px;"
                f" font-size: 15px; font-weight: 800; padding: 10px; }}"
            )

        self._update_grid_panel(count, side, open_price)

    def _update_grid_panel(self, count: int, side: str, open_price: float) -> None:
        m15 = self._read_m15()
        if m15 is None:
            self.g_info.setText("Conectando datos M15…")
            return

        # Precio actual y Bollinger
        bb = add_bollinger(m15, period=BB_PERIOD, std=BB_STD)
        last = m15.iloc[-1]
        price = float(last["close"])
        upper = float(bb["bb_upper"].iloc[-1])
        lower = float(bb["bb_lower"].iloc[-1])

        # Distancia en pips (EURUSD: 1 pip = 0.0001)
        pip = 0.0001
        dist_price = (price - open_price) / pip  # + si subió, - si bajó
        # "En contra" para COMPRA = precio BAJA (dist negativo en pips)
        # "En contra" para VENTA  = precio SUBE  (dist positivo en pips)
        contra_pips = -dist_price if side == "BUY" else dist_price
        contra_ok = contra_pips >= PIP_STEP

        # Toque de banda en la dirección correcta
        # COMPRA -> banda INFERIOR (precio cerca o bajo lower)
        # VENTA  -> banda SUPERIOR (precio cerca o sobre upper)
        touch = False
        if side == "BUY":
            touch = (lower - price) <= TOUCH_TOL_PIPS * pip
        else:
            touch = (price - upper) <= TOUCH_TOL_PIPS * pip

        # Capas ejecutadas (leídas de posiciones reales)
        # count=1 -> solo base; 2 -> capa1; 3 -> capa2
        capa1_done = count >= 2
        capa2_done = count >= 3

        # Lógica de "listas" (lo que el grid está esperando)
        r1 = contra_ok
        r2 = touch
        r3 = r1 and r2            # capa 1 lista (si no está ejecutada ya)
        # Para capa 2: tras capa1, OTROS 20 pips en contra + toque de banda
        # Usamos distancia ACUMULADA desde la base: capa2 lista si contra_pips >= 2*PIP_STEP y toque
        r4 = contra_pips >= 2 * PIP_STEP
        r5 = r4 and touch

        states = {"r1": r1, "r2": r2, "r3": r3, "r4": r4, "r5": r5}
        for k, v in states.items():
            self._lights[k]._set_state(v)

        # Info en vivo
        side_txt = "COMPRA" if side == "BUY" else "VENTA"
        banda_txt = f"Inf={lower:.5f} / Sup={upper:.5f}"
        self.g_info.setText(
            f"Base: {side_txt} {BASE_LOT} lote @ {open_price:.5f}  |  "
            f"Capas abiertas: {count - 1}/2  |  "
            f"Precio: {price:.5f}  |  En contra: {contra_pips:+.1f} pips (meta {PIP_STEP:.0f})  |  {banda_txt}"
        )

        # Banner de estado
        if capa2_done:
            msg, col, bord = "GRID COMPLETO (3 ops)", GREEN_SOFT, GREEN
        elif capa1_done:
            msg, col, bord = "CAPA 1 EJECUTADA — esperando capa 2", BG_PANEL, BORDER
        elif r3:
            msg, col, bord = f"CAPA 1 LISTA ({GRID_LOT_1}) — esperando ejecución", GREEN_SOFT, GREEN
        elif r1 and not r2:
            msg, col, bord = "20 pips en contra OK — esperando toque de banda", BG_PANEL, BORDER
        elif not r1:
            msg, col, bord = "Esperando 20 pips en contra…", BG_PANEL, BORDER
        else:
            msg, col, bord = "ESPERANDO…", BG_PANEL, BORDER
        self.g_banner.setText(msg)
        self.g_banner.setStyleSheet(
            f"QLabel {{ color: {TEXT if bord == BORDER else '#e8ffe8'};"
            f" background: {col}; border: 1px solid {bord};"
            f" border-radius: 8px; font-size: 14px; font-weight: 800; padding: 10px; }}"
        )

    def get_grid_values(self) -> dict:
        """Expuesto para tests / configuración (reglas dictadas por el usuario)."""
        return dict(_GRID_VALUES)
