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
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
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
        lay.setSpacing(10)
        lay.setContentsMargins(10, 8, 10, 8)

        self._dot = QLabel()
        self._dot.setFixedSize(88, 88)
        self._dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignCenter)

        self._txt = QLabel(label)
        self._txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._txt.setWordWrap(True)
        self._txt.setStyleSheet("color: #f2f2f2; font-size: 15px; font-weight: 800;")
        lay.addWidget(self._txt, 0, Qt.AlignmentFlag.AlignCenter)

        # --- lista de checks (✓/✗) debajo de la etiqueta ---
        self._checks = QWidget()
        self._checks.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._checks_lay = QVBoxLayout(self._checks)
        self._checks_lay.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._checks_lay.setSpacing(6)
        self._checks_lay.setContentsMargins(4, 0, 4, 0)
        lay.addWidget(self._checks, 0, Qt.AlignmentFlag.AlignTop)

        self._set_state(False, dim=True)

    def set_checks(self, items: list[tuple[bool, str]]) -> None:
        """Pinta la ista de checks de la fase (✓ verde / ✗ rojo)."""
        # limpiar widgets previos
        while self._checks_lay.count():
            item = self._checks_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for ok, text in items:
            lbl = QLabel(f"{'✓' if ok else '✗'}  {text}")
            lbl.setStyleSheet(
                f"color: {'#3ddc84' if ok else '#ff6b6b'};"
                f" font-size: 13px; font-weight: 600;"
            )
            lbl.setWordWrap(True)
            self._checks_lay.addWidget(lbl)

    def _set_state(self, on: bool, dim: bool = False) -> None:
        if dim:
            fill = "#20242c"
            ring = BORDER
        else:
            fill = "#1f9d55" if on else "#c0392b"
            ring = GREEN if on else RED
        self._dot.setStyleSheet(
            f"QLabel {{"
            f"  border: 4px solid {ring};"
            f"  border-radius: 44px;"  # círculo (88x88)
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
        # memoria de eventos del cruce (el motor es stateless por ciclo)
        self._k_prev: float | None = None
        self._d_prev: float | None = None
        self._cross_latch: dict | None = None  # {"side": "BULL"|"BEAR", "age": int}

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(16)

        # --- botón maestro ---
        self.btn = QPushButton("OFF")
        self.btn.setStyleSheet(_BTN_OFF)
        self.btn.setMinimumWidth(260)
        self.btn.clicked.connect(self._toggle)
        lay.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignHCenter)

        self.lbl_status = QLabel("BOT APAGADO")
        self.lbl_status.setStyleSheet("color: #c7ccd4; font-size: 14px; font-weight: 700;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.lbl_status)

        # --- panel semáforo (llena el ancho de la pestaña) ---
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
            f" border-radius: 12px; padding: 22px 18px; }}"
        )
        flay = QVBoxLayout(frame)
        flay.setSpacing(18)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        title = QLabel("SEGUIMIENTO DEL ESTOCÁSTICO (M15)")
        title.setStyleSheet(f"color: {TEXT_DIM}; font-size: 13px; font-weight: 700; letter-spacing: 1px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        flay.addWidget(title)

        # --- flujo horizontal de 4 etapas (llena el ancho de la pestaña) ---
        row = QHBoxLayout()
        row.setSpacing(10)
        row.setContentsMargins(4, 14, 4, 30)
        self._lights: dict[str, _Light] = {}
        n = len(_PHASES)
        for i, (key, label) in enumerate(_PHASES):
            stage = QFrame()
            stage.setObjectName("stage")
            stage.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            stage.setStyleSheet(
                f"QFrame#stage {{ background: {BG_PANEL}; border: 1px solid {BORDER};"
                f" border-radius: 10px; padding: 16px 14px; }}"
            )
            slay = QVBoxLayout(stage)
            slay.setSpacing(9)
            slay.setContentsMargins(6, 8, 6, 8)
            slay.setAlignment(Qt.AlignmentFlag.AlignTop)

            num = QLabel(f"{i + 1}")
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num.setFixedSize(26, 26)
            num.setStyleSheet(
                "QLabel { color: #0e1116; background: #7f8896; border-radius: 13px;"
                " font-size: 14px; font-weight: 800; }"
            )
            slay.addWidget(num, 0, Qt.AlignmentFlag.AlignCenter)

            light = _Light(label)
            self._lights[key] = light
            slay.addWidget(light, 0, Qt.AlignmentFlag.AlignCenter)

            row.addWidget(stage, 1)

            # conector "→" entre etapas
            if i < n - 1:
                arrow = QLabel("→")
                arrow.setStyleSheet(f"color: {TEXT_DIM}; font-size: 22px; font-weight: 800;")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                row.addWidget(arrow, 0)

        flay.addLayout(row)

        self.banner = QLabel("BOT APAGADO")
        self.banner.setStyleSheet(
            f"QLabel {{ color: {TEXT_DIM}; background: {BG_PANEL};"
            f" border: 1px solid {BORDER}; border-radius: 8px;"
            f" font-size: 16px; font-weight: 800; padding: 12px; }}"
        )
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        flay.addWidget(self.banner)

        lay.addWidget(frame)

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
        Mantiene memoria de eventos del cruce K/D entre ticks (el motor
        es stateless por ciclo y el cache solo mira la vela actual).
        """
        result = engine.load_cached()
        if not result:
            self.banner.setText("Esperando análisis del motor…")
            return

        states, details = self._build_state(result)

        all_green = all(states.values())
        for key, light in self._lights.items():
            light._set_state(states[key])
            light.set_checks(details[key])

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

    @staticmethod
    def _phase_details(result: dict) -> dict[str, list[tuple[bool, str]]]:
        """Sub-condiciones reales de cada fase, para la ista de checks.

        Solo expone lo que el motor YA calcula (single source of truth):
          - extreme/cross: 1 check ciego (el motor solo tira el bool).
          - confirm: 2 checks (cruce confirmado + motor en READY).
          - trend: 2 checks (macro alineado + intraday alineado).
        """
        verd = result.get("veredicto") or {}
        ca = verd.get("context_alignment") or {}
        stoch = result.get("stoch_m15") or {}

        stoch_confirm = bool(stoch.get("confirm", False))
        trigger_ready = str(ca.get("trigger", "")).upper() == "READY"
        macro = str(ca.get("macro", "")).upper()
        intraday = str(ca.get("intraday", "")).upper()
        # TENDENCIA A FAVOR = context_alignment del motor == ALIGNED
        # (el motor ya decidió si macro/intraday coinciden; no reinvento la lógica).
        aligned = str(ca.get("alignment", "")).upper() == "ALIGNED"

        return {
            "extreme": [
                (bool(stoch.get("extreme", False)), "en zona (sobrecompra/sobreventa)"),
            ],
            "cross": [
                (bool(stoch.get("cross", False)), "cruce K/D confirmado"),
            ],
            "confirm": [
                (stoch_confirm, "cruce confirmado"),
                (trigger_ready, "motor en READY"),
            ],
            "trend": [
                (aligned, f"macro alineado ({macro})"),
                (aligned, f"intraday alineado ({intraday})"),
            ],
        }

    # ── memoria de cruce (reglas R1-R5) ───────────────────────────────
    def _build_state(self, result: dict) -> tuple[dict[str, bool], dict[str, list[tuple[bool, str]]]]:
        """Calcula luces + checks CON memoria de eventos entre ticks.

        Single source of truth para los VALORES: el cache del motor
        (engine.load_cached). La MEMORIA del cruce vive en el widget
        (es UI de seguimiento, no recalcula MT5).

        R1 EXTREMO — luz ON si está en zona AHORA o hay cruce vigente
                          (memoria) que aún no expira.
        R2 CRUCE    — registra el lado (BULL/BEAR) y lo mantiene vigente.
        R3 TENDENCIA— lado del cruce vs bias del motor:
                          "a favor de tendencia" o "RETROCESO contra tendencia"
                          (se indica en el monitor).
        R5 CADUCIDAD— memoria expira a 12 ticks (~60s).
        """
        verd = result.get("veredicto") or {}
        ca = verd.get("context_alignment") or {}
        stoch = result.get("stoch_m15") or {}

        k = float(stoch.get("k", 50.0))
        d = float(stoch.get("d", 50.0))
        extreme = bool(stoch.get("extreme", False))
        cross = bool(stoch.get("cross", False))

        # ── deducir lado del cruce AHORA (K cruzó D) vs tick previo ──
        side_now: str | None = None
        if cross:
            kp, dp = self._k_prev, self._d_prev
            if kp is not None and dp is not None:
                if kp <= dp and k > d:
                    side_now = "BULL"
                elif kp >= dp and k < d:
                    side_now = "BEAR"
            if side_now is None:
                # sin previos: inferir por posición relativa de K vs D
                side_now = "BULL" if k > d else "BEAR"

        # ── actualizar latch (R2) ──
        if side_now:
            self._cross_latch = {"side": side_now, "age": 0}
        elif self._cross_latch is not None:
            self._cross_latch["age"] += 1
            if self._cross_latch["age"] > 12:  # R5: expira
                self._cross_latch = None

        # recordar k/d para el próximo tick
        self._k_prev, self._d_prev = k, d

        latch = self._cross_latch
        cross_vigente = latch is not None and latch["age"] <= 12

        # ── R1: luz EXTREMO vigente por memoria del cruce ──
        extreme_state = extreme or (latch is not None and latch["age"] <= 12)

        # ── R3: lado del cruce vs bias del motor ──
        macro = str(ca.get("macro", "")).upper()
        bias_side = "BULL" if macro == "BULLISH" else "BEAR" if macro == "BEARISH" else None
        retroceso = bool(latch and bias_side and latch["side"] != bias_side)

        stoch_confirm = bool(stoch.get("confirm", False))
        trigger_ready = str(ca.get("trigger", "")).upper() == "READY"
        aligned = str(ca.get("alignment", "")).upper() == "ALIGNED"

        states = {
            "extreme": extreme_state,
            "cross": cross_vigente,
            "confirm": stoch_confirm and trigger_ready,
            "trend": aligned,
        }

        # ── checks extendidos con la memoria ──
        extreme_checks = [(extreme, "en zona (sobrecompra/sobreventa)")]
        if extreme_state and not extreme and latch is not None:
            extreme_checks.append((True, f"cruce {latch['side']} vigente en memoria"))

        cross_label = (
            f"cruce {latch['side']} registrado" if latch is not None else "cruce K/D confirmado"
        )
        cross_checks = [(cross_vigente, cross_label)]

        trend_checks = [
            (aligned, f"macro alineado ({macro})"),
            (aligned, f"intraday alineado ({str(ca.get('intraday', '')).upper()})"),
        ]
        if latch is not None and bias_side:
            if retroceso:
                trend_checks.append(
                    (False, f"RETROCESO contra tendencia ({latch['side']} vs {bias_side})")
                )
            else:
                trend_checks.append((True, f"a favor de tendencia ({latch['side']})"))

        details = {
            "extreme": extreme_checks,
            "cross": cross_checks,
            "confirm": [
                (stoch_confirm, "cruce confirmado"),
                (trigger_ready, "motor en READY"),
            ],
            "trend": trend_checks,
        }
        return states, details

