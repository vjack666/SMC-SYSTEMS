"""FASE A — Panel MARKET STATE always-on (síntesis del pipeline jerárquico).

Absorbe el contexto que antes vivía en SesgoWidget:
- Sesgo institucional (macro + intraday)
- Wyckoff M15
- Fase ICT, confianza, calidad setup
- Confirmación M5, sesiones, riesgo abrir
- SMT, premium/discount, régimen, POI, trigger

No recalcula nada: solo pinta lo que el motor ya produjo.
"""
from __future__ import annotations

from collections import Counter
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame

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

        self.title = QLabel("CONTEXTO DEL MERCADO")
        self.title.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; font-weight: 800; letter-spacing: 1px;")
        lay.addWidget(self.title)

        self.lbl_bias = QLabel("SESGO: —")
        self.lbl_bias.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700;")
        lay.addWidget(self.lbl_bias)

        self.lbl_wyckoff = QLabel("WYCKOFF M15: —")
        self.lbl_wyckoff.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_wyckoff)

        self.lbl_fase = QLabel("FASE ICT: —")
        self.lbl_fase.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_fase)

        self.lbl_conf = QLabel("CONFIANZA: —")
        self.lbl_conf.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_conf)

        self.lbl_setup_quality = QLabel("CALIDAD SETUP: —")
        self.lbl_setup_quality.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_setup_quality)

        self.lbl_exec_m5 = QLabel("CONFIRMACIÓN M5: —")
        self.lbl_exec_m5.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_exec_m5)

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

        self.lbl_regime = QLabel("RÉGIMEN: —")
        self.lbl_regime.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_regime)

        self.lbl_poi = QLabel("POI: —")
        self.lbl_poi.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_poi)

        self.lbl_trigger = QLabel("TRIGGER: —")
        self.lbl_trigger.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_trigger)

    # ------------------------------------------------------------------
    def update_state(self, result: dict) -> None:
        verd = result.get("veredicto", {}) or {}
        ca = verd.get("context_alignment") or {}
        sem = result.get("semaforo") or {}
        wyk = result.get("wyckoff") or result.get("wyckoff", {}) or {}
        wyk_m15 = wyk.get("M15") if isinstance(wyk, dict) else None

        macro = ca.get("macro", "—")
        intraday = ca.get("intraday", "—")
        macro_txt = "LONG" if str(macro).upper() == "BULLISH" else "SHORT" if str(macro).upper() == "BEARISH" else str(macro)
        intra_txt = "LONG" if str(intraday).upper() == "BULLISH" else "SHORT" if str(intraday).upper() == "BEARISH" else str(intraday)
        self.lbl_bias.setText(f"SESGO: macro={macro_txt} · intradía={intra_txt}")

        if wyk_m15:
            fase = wyk_m15.get("phase_es", "INDEFINIDA")
            sesgo = wyk_m15.get("bias", "—")
            self.lbl_wyckoff.setText(f"WYCKOFF M15: {fase} (sesgo {sesgo})")
        else:
            self.lbl_wyckoff.setText("WYCKOFF M15: —")

        stages = ca.get("stages") or {}
        fase = " ".join(f"{k}:{v}" for k, v in stages.items()) or "—"
        self.lbl_fase.setText(f"FASE ICT: {fase}")

        conf = ca.get("confidence")
        if isinstance(conf, (int, float)):
            color = GREEN if conf >= 70 else (YELLOW if conf >= 40 else RED)
            self.lbl_conf.setText(f"CONFIANZA: {conf}%")
            self.lbl_conf.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 700;")
        else:
            self.lbl_conf.setText("CONFIANZA: EN CONSTRUCCIÓN")
            self.lbl_conf.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")

        sq = ca.get("setup_quality_pct")
        if isinstance(sq, (int, float)):
            color_sq = GREEN if sq >= 70 else (YELLOW if sq >= 40 else RED)
            self.lbl_setup_quality.setText(f"CALIDAD SETUP: {int(sq)}%")
            self.lbl_setup_quality.setStyleSheet(f"color: {color_sq}; font-size: 12px; font-weight: 700;")
        else:
            self.lbl_setup_quality.setText("CALIDAD SETUP: —")
            self.lbl_setup_quality.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")

        score = ca.get("exec_m5_score")
        matches = ca.get("exec_m5_matches", [])
        if isinstance(score, int):
            color_exec = GREEN if score >= 2 else (YELLOW if score == 1 else TEXT_DIM)
            c = Counter(matches)
            parts = [f"{k}×{v}" for k, v in c.items()]
            detail = ", ".join(parts) if parts else "sin coincidencias"
            self.lbl_exec_m5.setText(f"CONFIRMACIÓN M5: {score} ({detail})")
            self.lbl_exec_m5.setStyleSheet(f"color: {color_exec}; font-size: 12px; font-weight: 700;")
        else:
            self.lbl_exec_m5.setText("CONFIRMACIÓN M5: —")
            self.lbl_exec_m5.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")

        try:
            kz = killzone_activa_ahora() or "fuera de killzone"
            reloj = operator_clock_str()
        except Exception:
            kz, reloj = "—", "—"
        self.lbl_sesion.setText(f"SESIONES: {kz} · {reloj}")

        color_sem = sem.get("color", "—")
        self.lbl_riesgo.setText(f"RIESGO ABRIR: semáforo={color_sem}")

        smt = ca.get("smt", "—")
        if smt == "DIVERGE":
            self.lbl_smt.setText("SMT: DIVERGE (alerta trampa)")
            self.lbl_smt.setStyleSheet(f"color: {RED}; font-size: 12px; font-weight: 700;")
        elif smt == "ALIGNED":
            self.lbl_smt.setText("SMT: ALINEADO (confirma)")
            self.lbl_smt.setStyleSheet(f"color: {GREEN}; font-size: 12px; font-weight: 700;")
        else:
            self.lbl_smt.setText("SMT: EN CONSTRUCCIÓN")
            self.lbl_smt.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")

        pd = ca.get("premium_discount", "—")
        if pd in ("DISCOUNT", "PREMIUM"):
            color_pd = GREEN if pd == "DISCOUNT" else YELLOW
            self.lbl_pd.setText(f"PREMIUM/DISCOUNT: {pd}")
            self.lbl_pd.setStyleSheet(f"color: {color_pd}; font-size: 12px; font-weight: 700;")
        else:
            self.lbl_pd.setText("PREMIUM/DISCOUNT: EN CONSTRUCCIÓN")
            self.lbl_pd.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")

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
