from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from modules.swing.swing_detector import SwingConfig, detect_swings
from modules.trend.structure_classifier import StructureResult, classify_structure

MicroState = Literal["CONTINUATION", "PULLBACK", "UNCLEAR"]


@dataclass(frozen=True)
class MtfAnalysisResult:
    macro_trend: Literal["BULLISH", "BEARISH", "RANGING"]
    micro_state: MicroState
    d1_structure: StructureResult
    h4_structure: StructureResult
    agreement: bool


def _compute_macro_trend(
    d1_structure: StructureResult,
    h4_structure: StructureResult,
) -> tuple[Literal["BULLISH", "BEARISH", "RANGING"], bool]:
    d1_dir = d1_structure.structure
    h4_dir = h4_structure.structure

    agreement = (
        d1_dir == h4_dir
        and d1_dir in ("BULLISH", "BEARISH")
    )

    if agreement:
        return d1_dir, True
    return "RANGING", False


def _compute_micro_state(
    m15_frame: pd.DataFrame,
    macro_trend: Literal["BULLISH", "BEARISH", "RANGING"],
) -> MicroState:
    if macro_trend == "RANGING" or len(m15_frame) < 60:
        return "UNCLEAR"

    data = m15_frame.copy().reset_index(drop=True)
    close = data["close"]

    ema_fast = close.ewm(span=20, adjust=False).mean()
    ema_slow = close.ewm(span=50, adjust=False).mean()

    higher_high = float(data.iloc[-1]["high"]) > float(data.iloc[-5:-1]["high"].max())
    lower_low = float(data.iloc[-1]["low"]) < float(data.iloc[-5:-1]["low"].min())

    if macro_trend == "BULLISH":
        if float(ema_fast.iloc[-1]) > float(ema_slow.iloc[-1]) and higher_high:
            return "CONTINUATION"
        return "PULLBACK"

    if float(ema_fast.iloc[-1]) < float(ema_slow.iloc[-1]) and lower_low:
        return "CONTINUATION"
    return "PULLBACK"


def analyze_mtf(
    d1_frame: pd.DataFrame,
    h4_frame: pd.DataFrame,
    m15_frame: pd.DataFrame,
    swing_config: SwingConfig | None = None,
    n_swings: int = 3,
) -> MtfAnalysisResult:
    """Analyze macro + micro trend state across D1/H4/M15 timeframes."""
    if swing_config is None:
        swing_config = SwingConfig()

    d1_swings = detect_swings(d1_frame, swing_config)
    h4_swings = detect_swings(h4_frame, swing_config)

    d1_structure = classify_structure(d1_swings, n_swings=n_swings)
    h4_structure = classify_structure(h4_swings, n_swings=n_swings)

    macro_trend, agreement = _compute_macro_trend(d1_structure, h4_structure)
    micro_state = _compute_micro_state(m15_frame, macro_trend)

    return MtfAnalysisResult(
        macro_trend=macro_trend,
        micro_state=micro_state,
        d1_structure=d1_structure,
        h4_structure=h4_structure,
        agreement=agreement,
    )
