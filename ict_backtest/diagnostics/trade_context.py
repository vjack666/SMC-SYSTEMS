"""Fase D — Paso 2: contrato de datos TradeContext (inmutable).

TradeContext es el "expediente clinico" de UN trade. Se CONGELA una sola vez
por el `TradeContextBuilder` (diagnostics/context_builder.py) en el momento de
la simulacion. Despues es SOLO LECTURA: el Diagnosis Engine lo consume, nunca
lo muta (anti sesgo de retrospectiva = mismo peligro que look-ahead R4).

NO pertenece a R7 (motor de decision): el motor nunca lee TradeContext para
operar. Es solo registro para diagnostico post-backtest.

Ids persistentes (estilo quant research profesional):
  backtest_id   : id de la corrida (reconstruye Backtest 15 -> Trade 34)
  trade_id      : UUID estable del trade en todo el reporte
  signal_id     : referencia a la senal R7 que lo origino (trazabilidad)
  context_version: version del esquema (reconstruye contexto anual si la
                  estrategia evoluciona)
  context_created_at: UTC timestamp de congelacion (garante que fue ANTES
                  del resultado, anti look-ahead)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Version del esquema TradeContext. Subir al cambiar campos para poder
# reconstruir reportes historicos sin ambiguedad.
CONTEXT_VERSION = "ctx-1.0"


@dataclass(frozen=True)
class TradeContext:
    # --- identificadores persistentes (trazabilidad quant) ---
    backtest_id: str
    trade_id: str
    signal_id: str
    context_version: str = CONTEXT_VERSION
    context_created_at: str = ""  # UTC ISO; lo fija el builder al congelar

    # --- identidad ---
    symbol: str = ""
    entry_time: str = ""
    exit_time: str = ""
    direction: int = 0

    # --- entry context ---
    htf_trend: str = "RANGING"
    htf_bias: str = "RANGING"
    sweep_up: bool = False
    sweep_down: bool = False
    # FASE C (metadata, nunca input de decision)
    zone_authority: dict | None = None  # {has_htf_anchor, tier, stacking_level,
                                         #  confidence_weight, level}

    # --- structure quality (deuda R7/sequence, NO Fase C) ---
    displacement_gap: int = 0
    bos_gap: int = 0
    atr_z: float = 0.0
    sl_is_structural: bool = False
    dist_entry_to_sl_r: float = 0.0
    phase_log: tuple[str, ...] = field(default_factory=tuple)  # sweep->displace->BOS->return

    # --- exit diagnostics ---
    exit_reason: str = ""
    pnl_r: float = 0.0
    mfe_r: float = 0.0
    mae_r: float = 0.0
    hold_bars: int = 0
    adverse_excursion_at_exit: float = 0.0
    time_in_drawdown: float = 0.0

    # --- regime (HOY NO EXISTE; si otra fase lo agrega, se consume aqui) ---
    regime_tag: str | None = None
    htf_bias_at_exit: str | None = None
