from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from modules.trend.ml_model import predict_confidence
from modules.trend.mtf_analyzer import MtfAnalysisResult, analyze_mtf


@dataclass(frozen=True)
class TrendSignalResult:
    macro_trend: Literal["BULLISH", "BEARISH", "RANGING"]
    micro_state: Literal["CONTINUATION", "PULLBACK", "UNCLEAR"]
    confidence: float
    is_valid: bool
    reason: str
    agreement: bool
    details: MtfAnalysisResult


def _load_frame(data_dir: Path, symbol: str, timeframe: str) -> pd.DataFrame:
    file_path = data_dir / f"{symbol}_{timeframe}.parquet"
    if not file_path.exists():
        raise FileNotFoundError(f"Missing data file: {file_path}")
    frame = pd.read_parquet(file_path).copy()
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    return frame.sort_values("time").reset_index(drop=True)


def get_trend_signal(
    symbol: str,
    macro_tf_primary: str = "D1",
    macro_tf_secondary: str = "H4",
    micro_tf: str = "M15",
    data_dir: Path = Path("data/mt5"),
) -> TrendSignalResult:
    """Get current multi-timeframe trend signal and ML confidence for a symbol."""
    d1 = _load_frame(data_dir, symbol, macro_tf_primary)
    h4 = _load_frame(data_dir, symbol, macro_tf_secondary)
    m15 = _load_frame(data_dir, symbol, micro_tf)

    analysis = analyze_mtf(d1, h4, m15)

    features = {
        "atr_ratio": 1.0,
        "swing_amplitude_atr": 1.0,
        "candle_body_ratio_10": float(
            (m15["close"] - m15["open"]).abs().tail(10).mean()
            / (m15["high"] - m15["low"]).tail(10).replace(0.0, pd.NA).mean()
        ),
        "distance_from_last_swing_atr": 1.0,
        "volume_trend_slope_10": float(m15["tick_volume"].tail(10).diff().mean())
        if "tick_volume" in m15.columns
        else 0.0,
        "d1_h4_agreement": 1.0 if analysis.agreement else 0.0,
        "micro_state_encoded": 1.0
        if analysis.micro_state == "CONTINUATION"
        else (0.0 if analysis.micro_state == "PULLBACK" else -1.0),
        "consecutive_structure_count": float(len(analysis.d1_structure.swing_sequence[-4:])),
    }

    try:
        confidence = predict_confidence(features)
    except (FileNotFoundError, ValueError):
        confidence = 0.7 if analysis.agreement and analysis.micro_state == "CONTINUATION" else 0.4

    is_valid = (
        analysis.macro_trend in ("BULLISH", "BEARISH")
        and analysis.micro_state != "UNCLEAR"
        and confidence > 0.65
    )

    if analysis.macro_trend == "RANGING":
        reason = "Blocked: macro trend is RANGING (D1/H4 disagreement or unclear structure)."
    elif confidence <= 0.65:
        reason = f"Blocked: confidence {confidence:.3f} <= 0.65 threshold."
    elif analysis.micro_state != "CONTINUATION":
        reason = f"Blocked: micro state is {analysis.micro_state}, waiting CONTINUATION."
    else:
        reason = (
            f"Valid trend signal: {analysis.macro_trend} + "
            f"{analysis.micro_state} with confidence {confidence:.3f}."
        )

    return TrendSignalResult(
        macro_trend=analysis.macro_trend,
        micro_state=analysis.micro_state,
        confidence=float(confidence),
        is_valid=is_valid,
        reason=reason,
        agreement=analysis.agreement,
        details=analysis,
    )


__all__ = ["TrendSignalResult", "get_trend_signal"]
