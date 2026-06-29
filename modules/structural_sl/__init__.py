"""Structural Stop Loss module for ICT-based trading systems."""

from .backtest import StructuralBacktestConfig, run_structural_backtest
from .detector import (
    StructuralStop,
    apply_structural_stops_to_frame,
    calculate_structural_stop,
    detect_liquidity_sweep,
    detect_origin_swing,
)

__all__ = [
    "StructuralStop",
    "calculate_structural_stop",
    "detect_origin_swing",
    "detect_liquidity_sweep",
    "apply_structural_stops_to_frame",
    "StructuralBacktestConfig",
    "run_structural_backtest",
]
