"""ict_backtest/plan_driver.py — Fase 5: score de alineacion multi-TF.

El plan es HERRAMIENTA DE ANALISIS, no gate (decision de Ruben 2026-07-19:
M5/M1 son BONUS, no condicion; el umbral lo fija el mercado con evidencia,
no antes). score_plan MIDE la alineacion de cada senal y la adjunta como
AlignmentReport. NO descarta senales.

Pesos (alineacion, no filtro):
  D1  context ok      +1.0
  H4  bias ok         +1.0
  H1  POI armado      +1.0
  M15 setup completo  +1.0
  M5  confirmacion    +0.5  (bonus)
  M1  trigger fino    +0.5  (bonus)

Score maximo ~5.0. Una senal sin M5/M1 queda en 4.0 y SIGUE siendo
valida para analisis (no se borra). Solo falta contexto base (D1/H4/H1)
o setup (M15) cuando esas capas no aportan -> score bajo, se marca.

Funcion PURA: recibe objetos/senales ya filtrados a barras cerradas <= t
(closed-only anti look-ahead, el loop driver se encarga de eso). No accede
a discos ni a bar_index. No altera el conteo de senales de run_sequence.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ict_backtest.plan_emitters import emit_d1, emit_h4, emit_h1, emit_m15
from ict_backtest.plan_fsm import PlanVerdict


@dataclass
class AlignmentReport:
    """Desglose de alineacion multi-TF para una senal. score es la suma."""

    score: float
    d1: bool
    h4: bool
    h1: bool
    m15: bool
    m5: bool
    m1: bool
    m15_anchored: bool = False
    po3_complete: bool = False

    def as_dict(self) -> dict:
        return {
            "score": self.score,
            "d1": self.d1,
            "h4": self.h4,
            "h1": self.h1,
            "m15": self.m15,
            "m5": self.m5,
            "m1": self.m1,
            "m15_anchored": self.m15_anchored,
            "po3_complete": self.po3_complete,
        }


def _confirm(confirm: dict | None, direction: int) -> bool:
    if not confirm:
        return False
    return bool(confirm.get("confirmed")) and confirm.get("direction") == direction


def build_confirm_from_tf(df, t, direction: int) -> dict:
    """Confirma un TF (M5/M1) desde su market_structure, closed-only.

    Mira barras con time <= t (anti look-ahead). Si hay BOS o CHOCH activo
    en la MISMA direccion que el setup, confirma. Funcion pura.
    """
    if df is None or len(df) == 0:
        return {"direction": direction, "confirmed": False}
    t = pd.to_datetime(t)
    past = df[df["time"] <= t]
    if len(past) == 0:
        return {"direction": direction, "confirmed": False}
    dir_col = past["bos_dir"].iloc[-1] if "bos_dir" in past else 0
    choch_col = past["choch_dir"].iloc[-1] if "choch_dir" in past else 0
    confirmed = (dir_col == direction) or (choch_col == direction)
    return {"direction": direction, "confirmed": bool(confirmed)}


def score_plan(
    signal: dict,
    *,
    d1_objs: list,
    h4_objs: list,
    h1_objs: list,
    m15_signal: dict,
    m5_confirm: dict | None = None,
    m1_trigger: dict | None = None,
    m15_anchored: bool = False,
    po3_complete: bool = False,
) -> AlignmentReport:
    """Mide la alineacion multi-TF de una senal. NO filtra.

    Cada capa suma si su emisor emite el veredicto esperado. M5/M1 son
    bonus (+0.5) solo si confirman en la MISMA direccion que el setup.
    m15_anchored (+0.5, Brecha B) bonifica el POI anclado a narrativa HTF.
    po3_complete (+0.5, Brecha E) bonifica PO3 A/M/D alineado en la direccion.
    """
    direction = signal.get("direction", 0)
    score = 0.0

    d1 = emit_d1(d1_objs)
    d1_ok = d1 is not None and d1.verdict is PlanVerdict.CONTEXT_OK
    if d1_ok:
        score += 1.0

    h4 = emit_h4(h4_objs)
    h4_ok = h4 is not None and h4.verdict is PlanVerdict.CONTEXT_OK
    if h4_ok:
        score += 1.0

    h1 = emit_h1(h1_objs)
    h1_ok = h1 is not None and h1.verdict is PlanVerdict.ZONE_ARMED
    if h1_ok:
        score += 1.0

    m15 = emit_m15([m15_signal])
    m15_ok = m15 is not None and m15.verdict in (
        PlanVerdict.SETUP_LIVE,
        PlanVerdict.STRUCTURE_OK,
    )
    if m15_ok:
        score += 1.0

    base_ok = d1_ok and h4_ok and h1_ok

    m5 = _confirm(m5_confirm, direction)
    if m5 and base_ok:
        # Bonus solo si hay contexto superior (el plan existe para refinar)
        score += 0.5

    m1 = _confirm(m1_trigger, direction)
    if m1 and base_ok:
        score += 0.5

    if m15_anchored and base_ok:
        # Brecha B: POI anclado a narrativa HTF = bonus (+0.5), no condicion
        score += 0.5

    if po3_complete and base_ok:
        # Brecha E: PO3 A/M/D alineado en la direccion = bonus (+0.5)
        score += 0.5

    return AlignmentReport(
        score=score,
        d1=d1_ok,
        h4=h4_ok,
        h1=h1_ok,
        m15=m15_ok,
        m5=m5,
        m1=m1,
        m15_anchored=m15_anchored,
        po3_complete=po3_complete,
    )
