from __future__ import annotations

from typing import Any

import pandas as pd


EVENT_SCHEMA_COLUMNS = [
    "structure_scale",
    "structure_event",
    "imbalance_state",
    "mitigation_method",
    "ob_state",
    "session_bucket",
]


def session_bucket(timestamp: pd.Timestamp) -> str:
    ts = pd.to_datetime(timestamp, utc=True)
    hour = int(ts.hour)
    if 0 <= hour < 7:
        return "asia"
    if 7 <= hour < 12:
        return "london"
    if 12 <= hour < 17:
        return "overlap"
    if 17 <= hour < 22:
        return "new_york"
    return "off_session"


def _normalize_structure_event(value: Any) -> str:
    text = str(value).upper()
    if text in {"CHOCH_BULLISH", "CHOCH_BEARISH"}:
        return "choch"
    if text in {"CHOCH_PLUS_BULLISH", "CHOCH_PLUS_BEARISH"}:
        return "choch_plus"
    if text in {"BOS", "BOS_BULLISH", "BOS_BEARISH"}:
        return "bos"
    return "none"


def _normalize_ob_state(is_ob_new: bool, within_ob: bool, ob_mitigated: bool, is_breaker: bool) -> str:
    if is_breaker:
        return "breaker"
    if ob_mitigated:
        return "mitigated"
    if within_ob:
        return "within"
    if is_ob_new:
        return "new"
    return "none"


def build_event_schema_row(
    *,
    timestamp: pd.Timestamp,
    structure_scale: str,
    structure_event: str,
    imbalance_state: str,
    mitigation_method: str,
    is_ob_new: bool,
    within_ob: bool,
    ob_mitigated: bool,
    is_breaker: bool,
) -> dict[str, str]:
    scale = structure_scale if structure_scale in {"internal", "swing"} else "internal"
    state = imbalance_state if imbalance_state in {"new", "entered", "within", "mitigated", "exited"} else "new"
    method = mitigation_method if mitigation_method in {"close", "wick", "average"} else "wick"

    return {
        "structure_scale": scale,
        "structure_event": _normalize_structure_event(structure_event),
        "imbalance_state": state,
        "mitigation_method": method,
        "ob_state": _normalize_ob_state(is_ob_new, within_ob, ob_mitigated, is_breaker),
        "session_bucket": session_bucket(timestamp),
    }
