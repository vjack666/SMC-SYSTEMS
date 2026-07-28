"""Pestaña "Auto" — semi-automatización del grid DEMO + semáforo de seguimiento.

Un solo botón maestro ON/OFF (default OFF) que enciende/apaga el proceso
scripts/run_demo_grid.py vía process_control (pythonw en background).
El bot se apaga SOLO al cumplir la meta (+$60 o -2% del saldo); un QTimer
de 1s detecta ese auto-apagado y vuelve el botón a OFF.

Mientras está ENCENDIDO, un panel tipo semáforo muestra en vivo las 4 fases
del estocástico M15 que el bot evalúa para entrar. Cada fase se enciende en
verde cuando se cumple y queda en rojo cuando no — pensado para leerse de
golpe, sin jerga técnica:
  1. PRECIO EN EXTREMO  — el estocástico está en sobrecompra o sobreventa.
  2. GIRO LISTO         — la línea rápida (K) acaba de cruzar a la lenta (D).
  3. SEÑAL FIRME        — el cruce es real, no un roce de ruido.
  4. TENDENCIA A FAVOR  — la dirección del cruce coincide con la del mercado.

Cuando las 4 están en verde, el banner dice "¡MOMENTO DE ENTRAR!".

El semáforo se calcula en la propia pestaña leyendo MT5 en vivo (igual que el
runner), en paralelo y sin tocar el proceso hijo. Fiel a la lógica de
signals/stochastic_signal.py + trend_context.build_trend_context_frame.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app_observador.config import SYMBOL
from app_observador.core import process_control as pc
from app_observador.ui.theme import (
    BG_PANEL,
    BORDER,
    GREEN,
    GREEN_SOFT,
    RED,
    RED_SOFT,
    TEXT,
    TEXT_DIM,
)

from indicators.indicators import add_stochastic
from signals.stochastic_signal import (
    MIN_SEP,
    OVERBOUGHT,
    OVERSOLD,
    ZONE_HOLD,
)

# --- estilo del botón maestro (idéntico al original) -----------------------
_BTN_ON = (
    "QPushButton { background-color: #1f6f3f; color: #e8ffe8; font-weight: 800; "
    "font-size: 18px; border: 2px solid #2ecc71; border-radius: 12px; padding: 24px 40px; }"
    "QPushButton:hover { background-color: #268a4d; }"
)
# OFF = gris neutro (apagado), para NO competir con el rojo del semáforo
_BTN_OFF = (
    "QPushButton { background-color: #2a2e38; color: #c7ccd4; font-weight: 800; "
    "font-size: 18px; border: 2px solid #3d4450; border-radius: 12px; padding: 24px 40px; }"
    "QPushButton:hover { background-color: #333845; }"
)

# --- fases del semáforo (texto plano, sin jerga) --------------------------
_PHASES = [
    ("extreme", "PRECIO EN EXTREMO"),
    ("cross", "GIRO LISTO"),
    ("confirm", "SEÑAL FIRME"),
    ("trend", "TENDENCIA A FAVOR"),
]

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "mt5"


class _Light(QWidget):
    """Una luz de semáforo: círculo arriba + etiqueta plana debajo."""

    def __init__(self, label: str) -> None:
        super().__init__()
        self._label = label
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(8)

        self._dot = QLabel()
        self._dot.setFixedSize(64, 64)
        self._dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignCenter)

        self._txt = QLabel(label)
        self._txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._txt.setWordWrap(True)
        self._txt.setFixedWidth(140)
        self._txt.setStyleSheet("color: #e6e6e6; font-size: 12px; font-weight: 700;")
        lay.addWidget(self._txt, 0, Qt.AlignmentFlag.AlignCenter)

        self._set_state(False, dim=True)

    def _set_state(self, on: bool, dim: bool = False) -> None:
        if dim:
            fill = "#20242c"
            ring = BORDER
        else:
            fill = "#1f9d55" if on else "#c0392b"
            ring = GREEN if on else RED
        self._dot.setStyleSheet(
            f"QLabel {{"
            f"  border: 3px solid {ring};"
            f"  border-radius: 32px;"  # círculo (64x64)
            f"  background: qradialgradient(cx:50%, cy:50%, radius:60%,"
            f"    stop:0% {fill},"
            f"    stop:75% {'#0e3a22' if on else '#3a1616' if not dim else '#15171c'},"
            f"    stop:100% {BG_PANEL});"
            f"}}"
        )
        self._txt.setStyleSheet(
            f"color: {'#e6e6e6' if not dim else TEXT_DIM};"
            f" font-size: 12px; font-weight: 700;"
        )


class AutopilotWidget(QWidget):
    """Master toggle + semáforo de seguimiento para el grid DEMO."""

    def __init__(self) -> None:
        super().__init__()
        self._was_on = False
        self._mt5_ready = False
        self._mt5: object | None = None
        self._ctx_cache: dict | None = None
        self._ctx_age = 0.0

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(16)

        # --- botón maestro ---
        self.btn = QPushButton("OFF")
        self.btn.setStyleSheet(_BTN_OFF)
        self.btn.setMinimumWidth(260)
        self.btn.clicked.connect(self._toggle)
        lay.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignCenter)

        self.lbl_status = QLabel("BOT APAGADO")
        self.lbl_status.setStyleSheet("color: #c7ccd4; font-size: 14px; font-weight: 700;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.lbl_status)

        # --- panel semáforo ---
        self._build_semaphore(lay)

        expl = QLabel("Encendés vos. Se apaga solo al cumplir +$60 o -2% del saldo.")
        expl.setStyleSheet("color: #8a919c; font-size: 12px;")
        expl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        expl.setWordWrap(True)
        lay.addWidget(expl)

        # timer de encendido/apagado (1s)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(1000)

        # timer del semáforo (2s) — solo trabaja cuando está ON
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._update_semaphore)
        self._tick.setInterval(2000)

    # ── construcción del panel ─────────────────────────────────────────
    def _build_semaphore(self, lay: QVBoxLayout) -> None:
        frame = QFrame()
        frame.setObjectName("semaframe")
        frame.setStyleSheet(
            f"QFrame#semaframe {{ background: {BG_PANEL}; border: 1px solid {BORDER};"
            f" border-radius: 12px; padding: 16px; }}"
        )
        flay = QVBoxLayout(frame)
        flay.setSpacing(14)

        title = QLabel("SEGUIMIENTO DEL ESTOCÁSTICO (M15)")
        title.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px; font-weight: 700; letter-spacing: 1px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        flay.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(18)
        self._lights: dict[str, _Light] = {}
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        for (key, label), (r, c) in zip(_PHASES, positions):
            light = _Light(label)
            self._lights[key] = light
            grid.addWidget(light, r, c, Qt.AlignmentFlag.AlignCenter)
        flay.addLayout(grid)

        self.banner = QLabel("BOT APAGADO")
        self.banner.setStyleSheet(
            f"QLabel {{ color: {TEXT_DIM}; background: {BG_PANEL};"
            f" border: 1px solid {BORDER}; border-radius: 8px;"
            f" font-size: 16px; font-weight: 800; padding: 12px; }}"
        )
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        flay.addWidget(self.banner)

        lay.addWidget(frame, 0, Qt.AlignmentFlag.AlignCenter)

    # ── acciones ───────────────────────────────────────────────────────
    def _toggle(self) -> None:
        if self._was_on:
            res = pc.stop_script(pc.DEMO_GRID_SCRIPT)
            self._apply_state(False, "BOT APAGADO" if res.ok else res.message)
            self._tick.stop()
            self._dim_semaphore("BOT APAGADO")
        else:
            res = pc.start_script(pc.DEMO_GRID_SCRIPT)
            if res.running:
                self._ensure_mt5()
                self._tick.start()
                self._dim_semaphore(None)  # quita el estado apagado
            self._apply_state(res.running, "BOT ENCENDIDO" if res.running else res.message)

    def _poll(self) -> None:
        running = pc.is_script_running(pc.DEMO_GRID_SCRIPT)
        if self._was_on and not running:
            self._tick.stop()
            self._apply_state(False, "Meta alcanzada — bot apagado")
            self._dim_semaphore("META ALCANZADA")
        elif running and not self._was_on:
            self._apply_state(True, "BOT ENCENDIDO")

    def _apply_state(self, on: bool, status: str) -> None:
        self._was_on = on
        self.btn.setText("ON" if on else "OFF")
        self.btn.setStyleSheet(_BTN_ON if on else _BTN_OFF)
        self.lbl_status.setText(status)

    # ── semáforo ───────────────────────────────────────────────────────
    def _ensure_mt5(self) -> None:
        if self._mt5_ready:
            return
        try:
            import MetaTrader5 as mt5

            if mt5.terminal_info() is None:
                mt5.initialize()
            self._mt5 = mt5
            self._mt5_ready = True
        except Exception:
            self._mt5_ready = False

    def _dim_semaphore(self, text: str | None) -> None:
        for light in self._lights.values():
            light._set_state(False, dim=True)
        if text is not None:
            self.banner.setStyleSheet(
                f"QLabel {{ color: {TEXT_DIM}; background: {BG_PANEL};"
                f" border: 1px solid {BORDER}; border-radius: 8px;"
                f" font-size: 16px; font-weight: 800; padding: 12px; }}"
            )
            self.banner.setText(text)

    def _update_semaphore(self) -> None:
        if not self._mt5_ready:
            self._ensure_mt5()
            if not self._mt5_ready:
                self.banner.setText("Esperando MT5…")
                return

        m15 = self._read_m15()
        if m15 is None or len(m15) < 3:
            self.banner.setText("Sin datos M15…")
            return

        states = self._eval_phases(m15)
        all_green = all(states.values())

        for key, light in self._lights.items():
            light._set_state(states[key])

        if all_green:
            self.banner.setStyleSheet(
                f"QLabel {{ color: #e8ffe8; background: {GREEN_SOFT};"
                f" border: 1px solid {GREEN}; border-radius: 8px;"
                f" font-size: 18px; font-weight: 800; padding: 12px; }}"
            )
            self.banner.setText("¡MOMENTO DE ENTRAR!")
        else:
            self.banner.setStyleSheet(
                f"QLabel {{ color: {TEXT_DIM}; background: {BG_PANEL};"
                f" border: 1px solid {BORDER}; border-radius: 8px;"
                f" font-size: 16px; font-weight: 800; padding: 12px; }}"
            )
            self.banner.setText("ESPERANDO CONDICIONES…")

    def _read_m15(self) -> pd.DataFrame | None:
        try:
            rates = self._mt5.copy_rates_from_pos(SYMBOL, self._mt5.TIMEFRAME_M15, 0, 80)  # type: ignore[attr-defined]
            if rates is None or len(rates) < 3:
                return None
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            return df
        except Exception:
            return None

    def _eval_phases(self, m15: pd.DataFrame) -> dict[str, bool]:
        # Reusa el estocástico si ya viene calculado (como detect_stochastic_signal);
        # si no, lo calcula desde OHLC. Así el semáforo es fiel al runner y testeable.
        if {"stoch_k", "stoch_d"}.issubset(m15.columns):
            st = m15
        else:
            st = add_stochastic(m15)
        k = st["stoch_k"].to_numpy()
        d = st["stoch_d"].to_numpy()
        n = len(k)
        i = n - 1
        while i > 0 and (pd.isna(k[i]) or pd.isna(d[i])):
            i -= 1
        if i < 1:
            return {k_: False for k_, _ in _PHASES}

        ki, di = float(k[i]), float(d[i])
        kp, dp = float(k[i - 1]), float(d[i - 1])

        # 1. PRECIO EN EXTREMO
        in_oversold = (ki < OVERSOLD) and (di < OVERSOLD)
        in_overbought = (ki > OVERBOUGHT) and (di > OVERBOUGHT)
        extreme = in_oversold or in_overbought

        # 2. GIRO LISTO (cruce K/D)
        bull_cross = (kp <= dp) and (ki > di)
        bear_cross = (kp >= dp) and (ki < di)
        cross = bull_cross or bear_cross

        # 3. SEÑAL FIRME (confirmación de cruce)
        sep = abs(ki - di)
        if bull_cross:
            momentum_ok = (ki - kp) > 0
            zone_holds = ki < ZONE_HOLD
        else:
            momentum_ok = (ki - kp) < 0
            zone_holds = ki > (100.0 - ZONE_HOLD)
        confirm = cross and (sep >= MIN_SEP) and momentum_ok and zone_holds

        # 4. TENDENCIA A FAVOR (contexto del mercado coincide con la dirección)
        side = "BUY" if bull_cross else ("SELL" if bear_cross else "")
        ctx_dir = self._context_direction()
        trend = bool(side) and (side == ctx_dir)

        return {
            "extreme": extreme,
            "cross": cross,
            "confirm": confirm,
            "trend": trend,
        }

    def _context_direction(self) -> str:
        """Dirección que dicta el contexto (HTF), cacheada 10s.

        Usa el mismo build_trend_context_frame que el runner para ser fiel.
        """
        self._ctx_age += 2.0
        if self._ctx_cache is None or self._ctx_age >= 10.0:
            try:
                from trend_context import build_trend_context_frame

                m15 = self._read_m15()
                if m15 is not None:
                    ctx = build_trend_context_frame(SYMBOL, m15, data_dir=_DATA_DIR)
                    self._ctx_cache = (
                        ctx.iloc[-1].to_dict() if ctx is not None and len(ctx) else None
                    )
                    self._ctx_age = 0.0
            except Exception:
                return ""
        c = self._ctx_cache or {}
        htf = str(c.get("htf_bias", "")).upper()
        if htf == "BULLISH":
            return "BUY"
        if htf == "BEARISH":
            return "SELL"
        return ""
