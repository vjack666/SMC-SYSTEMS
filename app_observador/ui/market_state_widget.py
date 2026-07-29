"""FASE A — Panel MARKET STATE always-on (síntesis del pipeline jerárquico).

Lee `result["veredicto"]["context_alignment"]` (macro/intraday/poi/trigger/
confidence/stages) + semáforo + killzone, y muestra de un vistazo el estado
operacional del mercado. No recalcula nada: el motor (engine.run_cycle ->
pipeline.run_pipeline) ya produjo todo. Reutiliza timezone.py para sesiones.

Backtest fuera de alcance: se alimenta solo de engine.run_cycle / run_pipeline.
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt

from app_observador.core.timezone import killzone_activa_ahora, operator_clock_str
from app_observador.ui.theme import TEXT, TEXT_DIM, ACCENT, GREEN, YELLOW, RED, BORDER
from app_observador.ui.format_helpers import format_poi, format_trigger


class MarketStateWidget(QFrame):
    """Síntesis always-on del estado del mercado (jerarquía ICT, no votos)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("marketState")
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(f"QFrame#marketState {{ border: 1px solid {BORDER}; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        self.title = QLabel("MARKET STATE")
        self.title.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; font-weight: 800; letter-spacing: 1px;")
        lay.addWidget(self.title)

        self.lbl_bias = QLabel("SESGO INSTITUCIONAL: —")
        self.lbl_bias.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700;")
        lay.addWidget(self.lbl_bias)

        self.lbl_fase = QLabel("FASE ICT: —")
        self.lbl_fase.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_fase)

        self.lbl_conf = QLabel("CONFIANZA: —")
        self.lbl_conf.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_conf)

        self.lbl_setup_quality = QLabel("CALIDAD SETUP: —")
        self.lbl_setup_quality.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_setup_quality)

        self.lbl_sesion = QLabel("SESIONES: —")
        self.lbl_sesion.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_sesion)

        self.lbl_riesgo = QLabel("RIESGO ABRIR: —")
        self.lbl_riesgo.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_riesgo)

        self.lbl_smt = QLabel("SMT: —")
        self.lbl_smt.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_smt)

        self.lbl_pd = QLabel("PREMIUM/DISCOUNT: —")
        self.lbl_pd.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_pd)

        # Régimen de mercado (volatilidad por RANGO PURO, sin ATR)
        self.lbl_regime = QLabel("RÉGIMEN: —")
        self.lbl_regime.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_regime)

        # FASE 5 (UI): POI enriquecido (tier/anclado/apilado/bonus)
        self.lbl_poi = QLabel("POI: —")
        self.lbl_poi.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_poi)

        # FASE 5 (UI): trigger como máquina de estados
        self.lbl_trigger = QLabel("TRIGGER: —")
        self.lbl_trigger.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_trigger)

    # ------------------------------------------------------------------
    def update_state(self, result: dict) -> None:
        verd = result.get("veredicto", {}) or {}
        ca = verd.get("context_alignment") or {}
        sem = result.get("semaforo") or {}

        # Sesgo institucional (macro + intraday)
        macro = ca.get("macro", "—")
        intraday = ca.get("intraday", "—")
        self.lbl_bias.setText(f"SESGO INSTITUCIONAL: macro={macro} · intraday={intraday}")

        # Fase ICT = los stages del pipeline (D1/H4/H1/M15_POI/M5_TRIGGER)
        stages = ca.get("stages") or {}
        fase = " ".join(f"{k}:{v}" for k, v in stages.items()) or "—"
        self.lbl_fase.setText(f"FASE ICT: {fase}")

        # Confianza (alineación de capas, no votos)
        conf = ca.get("confidence")
        if isinstance(conf, (int, float)):
            color = GREEN if conf >= 70 else (YELLOW if conf >= 40 else RED)
            self.lbl_conf.setText(f"CONFIANZA: {conf}%")
            self.lbl_conf.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 700;")
        else:
            self.lbl_conf.setText("CONFIANZA: EN CONSTRUCCIÓN")
            self.lbl_conf.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")

        # Calidad del setup (score combinado 0-100)
        sq = ca.get("setup_quality_pct")
        if isinstance(sq, (int, float)):
            color_sq = GREEN if sq >= 70 else (YELLOW if sq >= 40 else RED)
            self.lbl_setup_quality.setText(f"CALIDAD SETUP: {int(sq)}%")
            self.lbl_setup_quality.setStyleSheet(f"color: {color_sq}; font-size: 12px; font-weight: 700;")
        else:
            self.lbl_setup_quality.setText("CALIDAD SETUP: —")
            self.lbl_setup_quality.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")

        # Sesiones (reutiliza timezone.py; el motor no calcula esto)
        try:
            kz = killzone_activa_ahora() or "fuera de killzone"
            reloj = operator_clock_str()
        except Exception:
            kz, reloj = "—", "—"
        self.lbl_sesion.setText(f"SESIONES: {kz} · {reloj}")

        # Riesgo de abrir (semáforo del motor)
        color_sem = sem.get("color", "—")
        self.lbl_riesgo.setText(f"RIESGO ABRIR: semáforo={color_sem}")

        # SMT (par correlacionado): DIVERGE = alerta de trampa, ALIGNED = confirma
        smt = ca.get("smt", "—")
        if smt == "DIVERGE":
            self.lbl_smt.setText(f"SMT: DIVERGE (alerta trampa)")
            self.lbl_smt.setStyleSheet(f"color: {RED}; font-size: 12px; font-weight: 700;")
        elif smt == "ALIGNED":
            self.lbl_smt.setText(f"SMT: ALINEADO (confirma)")
            self.lbl_smt.setStyleSheet(f"color: {GREEN}; font-size: 12px; font-weight: 700;")
        else:
            self.lbl_smt.setText("SMT: EN CONSTRUCCIÓN")
            self.lbl_smt.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")

        # Premium/Discount del POI vs rango D1
        pd = ca.get("premium_discount", "—")
        if pd in ("DISCOUNT", "PREMIUM"):
            color_pd = GREEN if pd == "DISCOUNT" else YELLOW
            self.lbl_pd.setText(f"PREMIUM/DISCOUNT: {pd}")
            self.lbl_pd.setStyleSheet(f"color: {color_pd}; font-size: 12px; font-weight: 700;")
        else:
            self.lbl_pd.setText("PREMIUM/DISCOUNT: EN CONSTRUCCIÓN")
            self.lbl_pd.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")

        # Régimen de mercado (RANGO PURO, sin ATR): HIGH_VOL/NORMAL/LOW_VOL
        regime = ca.get("regime", "—")
        if regime in ("HIGH_VOL", "NORMAL", "LOW_VOL"):
            _rmap = {"HIGH_VOL": ("VOLATILIDAD ALTA", RED),
                     "NORMAL": ("NORMAL", GREEN),
                     "LOW_VOL": ("VOLATILIDAD BAJA", YELLOW)}
            _txt, _col = _rmap[regime]
            self.lbl_regime.setText(f"RÉGIMEN: {_txt}")
            self.lbl_regime.setStyleSheet(f"color: {_col}; font-size: 12px; font-weight: 700;")
        else:
            self.lbl_regime.setText("RÉGIMEN: EN CONSTRUCCIÓN")
            self.lbl_regime.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")

        # FASE 5 (UI): POI enriquecido y trigger como máquina de estados.
        # Funciones puras testeables (format_helpers). Solo pintan lo que el
        # motor ya produjo; si el campo falta → "EN CONSTRUCCIÓN".
        self.lbl_poi.setText(format_poi(ca))
        poi_tier = ca.get("poi_tier")
        if poi_tier and str(poi_tier).upper() not in ("SKIP", "PENDING"):
            self.lbl_poi.setStyleSheet(f"color: {GREEN}; font-size: 12px; font-weight: 700;")
        else:
            self.lbl_poi.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")

        machine = ca.get("trigger_machine")
        self.lbl_trigger.setText(format_trigger(machine))
        if machine == "TRIGGER_READY":
            self.lbl_trigger.setStyleSheet(f"color: {GREEN}; font-size: 12px; font-weight: 700;")
        elif machine == "TRIGGER_READY_OFF_SESSION":
            self.lbl_trigger.setStyleSheet(f"color: {YELLOW}; font-size: 12px; font-weight: 700;")
        else:
            self.lbl_trigger.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
