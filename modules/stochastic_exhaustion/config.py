from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StochasticExhaustionConfig:
    oversold_threshold: float = 30.0
    overbought_threshold: float = 70.0
    min_cycles: int = 2
    epsilon: float = 0.0001
    compression_ratio: float = 0.6
    lookback: int = 20
    rsi_period: int = 14
