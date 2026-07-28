"""Pestaña "Auto" — semi-automatización del grid DEMO + semáforo de seguimiento.

Un solo botón maestro ON/OFF (default OFF) que enciende/apaga el proceso
scripts/run_demo_grid.py vía process_control (pythonw en background).
El bot se apaga SOLO al cumplir la meta (+$60 o -2% del saldo); un QTimer
de 1s detecta ese auto-apagado y vuelve el botón a OFF.

Mientras está ENCENDIDO, un panel tipo semáforo muestra las 4 fases que el
MOTOR GRANDE (engine.run_cycle) evalúa para la entrada. El semáforo es un
VISOR FIEL del motor: NO recalcula nada, lee el cache de run_cycle
(data/blackbox/last_cycle.json). Así lo que ves es lo que el motor dicta:
  1. PRECIO EN EXTREMO  — el estocástico M15 está en sobrecompra/sobreventa.
  2. GIRO LISTO         — la línea rápida (K) cruzó a la lenta (D).
  3. SEÑAL FIRME        — el motor marca el trigger como READY (no ruido).
  4. TENDENCIA A FAVOR  — el contexto HTF del motor está ALINEADO (macro+intraday).

Cuando las 4 están en verde, el banner dice "¡MOMENTO DE ENTRAR!".

Single source of truth: el semáforo consume engine.load_cached(); el cerebro
de señal (stochastic_signal / trend_context por cuenta propia) quedó eliminado.
"""
from __future__ import annotations

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
from app_observador.core import engine
from app_observador.core import process_control as pc
from app_observador.ui.theme import (
    BG_PANEL,
    BORDER,
    GREEN,
    GREEN_SOFT,
    RED,
    TEXT,
    TEXT_DIM,
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

# --- fases del semáforo (texto plano, sin jerga) --------------------------
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

        # timer del semáforo (5s) — solo trabaja cuando está ON.
        # Subido de 2s para no saturar MT5 con 2 consultas/seg (fluidez UI).
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._update_semaphore)
        self._tick.setInterval(5000)

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
        """Visor fiel del motor grande: lee el cache de run_cycle.

        No recalcula nada (MT5/stochastic_signal quedaron eliminados).
        Si el motor aún no escribió cache, espera al próximo tick.
        """
        result = engine.load_cached()
        if not result:
            self.banner.setText("Esperando análisis del motor…")
            return

        states = self._lights_from_cache(result)
        all_green = all(states.values())

        for key, light in self._lights.items():
            light._set_state(states[key])

        bias = str(result.get("bias", ""))
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
            self.banner.setText(f"ESPERANDO — {bias}")

    @staticmethod
    def _lights_from_cache(result: dict) -> dict[str, bool]:
        """Mapea el veredicto del motor grande a las 4 luces del semáforo.

        Single source of truth: el motor (run_cycle) ya calculó todo.
          - extreme/cross/confirm <- stoch_m15 (que el motor expone en el cache)
          - trend (TENDENCIA A FAVOR) <- context_alignment del motor ALINEADO
          - confirm (SEÑAL FIRME) <- trigger == READY del motor
        """
        verd = result.get("veredicto") or {}
        ca = verd.get("context_alignment") or {}
        stoch = result.get("stoch_m15") or {}

        extreme = bool(stoch.get("extreme", False))
        cross = bool(stoch.get("cross", False))
        stoch_confirm = bool(stoch.get("confirm", False))
        trend = str(ca.get("alignment", "")).upper() == "ALIGNED"
        # SEÑAL FIRME: el cruce está confirmado (estocástico) Y el motor
        # marca el trigger como READY (no ruido de cruce aislado).
        trigger_ready = str(ca.get("trigger", "")).upper() == "READY"
        confirm = stoch_confirm and trigger_ready

        return {
            "extreme": extreme,
            "cross": cross,
            "confirm": confirm,
            "trend": trend,
        }
