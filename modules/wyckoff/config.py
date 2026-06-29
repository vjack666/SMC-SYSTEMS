from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WyckoffConfig:
    swing_lookback: int = 5
    volume_threshold: float = 1.5
    phase_lookback: int = 30
    spring_depth_atr: float = 0.3
    sos_min_atr: float = 1.0
    lps_max_atr: float = 0.7
