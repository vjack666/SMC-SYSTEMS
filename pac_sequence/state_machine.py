from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


STATES = {
    "FVG_CREATED": "FVG_CREATED",
    "FVG_MITIGATED": "FVG_MITIGATED",
    "STRUCTURE_CONFIRMED": "STRUCTURE_CONFIRMED",
    "ENTRY_READY": "ENTRY_READY",
}

INVALIDATION_REASONS = {
    "OPPOSITE_CHOCH": "OPPOSITE_CHOCH",
    "OPPOSITE_BOS": "OPPOSITE_BOS",
    "FVG_INVALIDATED": "FVG_INVALIDATED",
    "TTL_EXPIRED": "TTL_EXPIRED",
}


@dataclass(frozen=True)
class StateMachineConfig:
    ttl_bars: int = 64
    structure_scale: str = "internal"
    mitigation_method: str = "wick"


def _wick_mitigated(low: float, high: float, zone_low: float, zone_high: float) -> bool:
    return (low <= zone_high) and (high >= zone_low)


def _close_mitigated(direction: int, close: float, zone_low: float, zone_high: float) -> bool:
    if direction == 1:
        return close <= zone_high
    return close >= zone_low


def _average_mitigated(low: float, high: float, zone_low: float, zone_high: float) -> bool:
    avg = (zone_low + zone_high) * 0.5
    return (low <= avg <= high)


def _is_mitigated(method: str, direction: int, low: float, high: float, close: float, zone_low: float, zone_high: float) -> bool:
    if method == "close":
        return _close_mitigated(direction, close, zone_low, zone_high)
    if method == "average":
        return _average_mitigated(low, high, zone_low, zone_high)
    return _wick_mitigated(low, high, zone_low, zone_high)


def run_state_machine(
    *,
    scored: pd.DataFrame,
    create_idx: int,
    direction: int,
    zone_low: float,
    zone_high: float,
    config: StateMachineConfig,
    setup_id: str,
) -> dict[str, object]:
    transitions: list[dict[str, object]] = []
    invalidations: list[dict[str, object]] = []

    mitigation_idx: int | None = None
    structure_idx: int | None = None
    entry_idx: int | None = None
    touch_count = 0

    created_row = scored.iloc[create_idx]
    transitions.append(
        {
            "setup_id": setup_id,
            "bar_idx": int(create_idx),
            "time": str(created_row["time"]),
            "from_state": "NONE",
            "to_state": STATES["FVG_CREATED"],
            "reason": "FVG_DETECTED",
        }
    )

    end_idx = min(len(scored) - 1, create_idx + int(config.ttl_bars))
    for j in range(create_idx + 1, end_idx + 1):
        row = scored.iloc[j]
        low = float(pd.to_numeric(row.get("low", np.nan), errors="coerce"))
        high = float(pd.to_numeric(row.get("high", np.nan), errors="coerce"))
        close = float(pd.to_numeric(row.get("close", np.nan), errors="coerce"))

        if not np.isfinite(low) or not np.isfinite(high) or not np.isfinite(close):
            continue

        choch = str(row.get("choch_signal", "NONE"))
        bos = int(pd.to_numeric(row.get("bos_direction", 0), errors="coerce"))

        opposite_choch = (direction == 1 and "BEARISH" in choch) or (direction == -1 and "BULLISH" in choch)
        if opposite_choch:
            invalidations.append(
                {
                    "setup_id": setup_id,
                    "bar_idx": int(j),
                    "time": str(row["time"]),
                    "reason": INVALIDATION_REASONS["OPPOSITE_CHOCH"],
                }
            )
            return {
                "mitigation_idx": mitigation_idx,
                "structure_idx": structure_idx,
                "entry_idx": None,
                "touch_count": touch_count,
                "invalidation": INVALIDATION_REASONS["OPPOSITE_CHOCH"],
                "transitions": transitions,
                "invalidations": invalidations,
            }

        if (direction == 1 and bos < 0) or (direction == -1 and bos > 0):
            invalidations.append(
                {
                    "setup_id": setup_id,
                    "bar_idx": int(j),
                    "time": str(row["time"]),
                    "reason": INVALIDATION_REASONS["OPPOSITE_BOS"],
                }
            )
            return {
                "mitigation_idx": mitigation_idx,
                "structure_idx": structure_idx,
                "entry_idx": None,
                "touch_count": touch_count,
                "invalidation": INVALIDATION_REASONS["OPPOSITE_BOS"],
                "transitions": transitions,
                "invalidations": invalidations,
            }

        if direction == 1 and close < zone_low:
            invalidations.append(
                {
                    "setup_id": setup_id,
                    "bar_idx": int(j),
                    "time": str(row["time"]),
                    "reason": INVALIDATION_REASONS["FVG_INVALIDATED"],
                }
            )
            return {
                "mitigation_idx": mitigation_idx,
                "structure_idx": structure_idx,
                "entry_idx": None,
                "touch_count": touch_count,
                "invalidation": INVALIDATION_REASONS["FVG_INVALIDATED"],
                "transitions": transitions,
                "invalidations": invalidations,
            }

        if direction == -1 and close > zone_high:
            invalidations.append(
                {
                    "setup_id": setup_id,
                    "bar_idx": int(j),
                    "time": str(row["time"]),
                    "reason": INVALIDATION_REASONS["FVG_INVALIDATED"],
                }
            )
            return {
                "mitigation_idx": mitigation_idx,
                "structure_idx": structure_idx,
                "entry_idx": None,
                "touch_count": touch_count,
                "invalidation": INVALIDATION_REASONS["FVG_INVALIDATED"],
                "transitions": transitions,
                "invalidations": invalidations,
            }

        touched = (low <= zone_high) and (high >= zone_low)
        if touched:
            touch_count += 1

        if mitigation_idx is None and _is_mitigated(config.mitigation_method, direction, low, high, close, zone_low, zone_high):
            mitigation_idx = j
            transitions.append(
                {
                    "setup_id": setup_id,
                    "bar_idx": int(j),
                    "time": str(row["time"]),
                    "from_state": STATES["FVG_CREATED"],
                    "to_state": STATES["FVG_MITIGATED"],
                    "reason": f"MITIGATED_{config.mitigation_method.upper()}",
                }
            )
            continue

        if mitigation_idx is not None and structure_idx is None:
            if (direction == 1 and bos > 0) or (direction == -1 and bos < 0):
                structure_idx = j
                transitions.append(
                    {
                        "setup_id": setup_id,
                        "bar_idx": int(j),
                        "time": str(row["time"]),
                        "from_state": STATES["FVG_MITIGATED"],
                        "to_state": STATES["STRUCTURE_CONFIRMED"],
                        "reason": "BOS_CONFIRMED",
                    }
                )
                entry_idx = j
                transitions.append(
                    {
                        "setup_id": setup_id,
                        "bar_idx": int(j),
                        "time": str(row["time"]),
                        "from_state": STATES["STRUCTURE_CONFIRMED"],
                        "to_state": STATES["ENTRY_READY"],
                        "reason": "ENTRY_TRIGGERED",
                    }
                )
                return {
                    "mitigation_idx": mitigation_idx,
                    "structure_idx": structure_idx,
                    "entry_idx": entry_idx,
                    "touch_count": touch_count,
                    "invalidation": None,
                    "transitions": transitions,
                    "invalidations": invalidations,
                }

    invalidations.append(
        {
            "setup_id": setup_id,
            "bar_idx": int(end_idx),
            "time": str(scored.iloc[end_idx]["time"]),
            "reason": INVALIDATION_REASONS["TTL_EXPIRED"],
        }
    )
    return {
        "mitigation_idx": mitigation_idx,
        "structure_idx": structure_idx,
        "entry_idx": None,
        "touch_count": touch_count,
        "invalidation": INVALIDATION_REASONS["TTL_EXPIRED"],
        "transitions": transitions,
        "invalidations": invalidations,
    }
