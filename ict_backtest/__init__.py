"""ict_backtest — Backtest ICT desde cero (event-driven, vela a vela).

Modulos:
  structure.py : clasificacion bullish/bearish/ranging por TF (PARTE 1).
  rules.py     : mini-check del dashboard como reglas puras (intradia/scalping).
  engine.py    : construccion de senales + simulacion vela a vela (sin ML).
"""

from ict_backtest.structure import classify_structure, classify_multi_tf, momentum_direction
from ict_backtest.rules import evaluate, checklist_intradia, checklist_scalping, killzone_en
from ict_backtest.engine import ICTSignal, ICTTrade, simulate_trade

__all__ = [
    "classify_structure", "classify_multi_tf", "momentum_direction",
    "evaluate", "checklist_intradia", "checklist_scalping", "killzone_en",
    "ICTSignal", "ICTTrade", "simulate_trade",
]
