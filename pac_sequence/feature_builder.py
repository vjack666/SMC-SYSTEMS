from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from pac_sequence.event_schema import build_event_schema_row


PAC_FEATURE_COLUMNS = [
    "bars_since_fvg_creation",
    "bars_since_mitigation",
    "mitigation_depth_pct",
    "mitigation_touch_count",
    "distance_prev_day_high",
    "distance_prev_day_low",
    "distance_eqh",
    "distance_eql",
    "ob_overlap_with_fvg",
    "ob_state",
    "session_bucket",
    "hour_sin",
    "hour_cos",
    "structure_event",
    "structure_scale",
]


def _distance(value: float, reference: float, atr: float) -> float:
    if not np.isfinite(value) or not np.isfinite(reference) or not np.isfinite(atr) or atr <= 0.0:
        return float("nan")
    return float((value - reference) / atr)


def build_prev_day_levels(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame[["time", "high", "low"]].copy().sort_values("time")
    daily = data.set_index("time").resample("1D").agg({"high": "max", "low": "min"})
    daily = daily.shift(1).rename(columns={"high": "prev_day_high", "low": "prev_day_low"})
    levels = pd.merge_asof(
        data[["time"]],
        daily.reset_index().sort_values("time"),
        on="time",
        direction="backward",
    )
    return levels


def build_pac_feature_row(
    *,
    scored: pd.DataFrame,
    idx: int,
    create_idx: int,
    mitigation_idx: int | None,
    direction: int,
    zone_low: float,
    zone_high: float,
    touch_count: int,
    structure_scale: str,
    structure_event: str,
    imbalance_state: str,
    mitigation_method: str,
    levels: pd.DataFrame,
) -> dict[str, Any]:
    row = scored.iloc[idx]
    atr = float(pd.to_numeric(row.get("atr", np.nan), errors="coerce"))
    close = float(pd.to_numeric(row.get("close", np.nan), errors="coerce"))
    low = float(pd.to_numeric(row.get("low", np.nan), errors="coerce"))
    high = float(pd.to_numeric(row.get("high", np.nan), errors="coerce"))

    pd_high = float(pd.to_numeric(levels.iloc[idx].get("prev_day_high", np.nan), errors="coerce"))
    pd_low = float(pd.to_numeric(levels.iloc[idx].get("prev_day_low", np.nan), errors="coerce"))

    eqh_ref = float(pd.to_numeric(row.get("last_swing_high", np.nan), errors="coerce"))
    eql_ref = float(pd.to_numeric(row.get("last_swing_low", np.nan), errors="coerce"))

    zone_size = max(1e-12, float(abs(zone_high - zone_low)))
    if direction == 1:
        depth = (zone_high - low) / zone_size
    else:
        depth = (high - zone_low) / zone_size
    depth = float(min(2.0, max(-1.0, depth)))

    ob_top = float(pd.to_numeric(row.get("ob_top", np.nan), errors="coerce"))
    ob_bottom = float(pd.to_numeric(row.get("ob_bottom", np.nan), errors="coerce"))
    ob_overlap = 0
    if np.isfinite(ob_top) and np.isfinite(ob_bottom):
        ob_low = min(ob_top, ob_bottom)
        ob_high = max(ob_top, ob_bottom)
        if (ob_low <= zone_high) and (ob_high >= zone_low):
            ob_overlap = 1

    schema = build_event_schema_row(
        timestamp=pd.to_datetime(row["time"], utc=True),
        structure_scale=structure_scale,
        structure_event=structure_event,
        imbalance_state=imbalance_state,
        mitigation_method=mitigation_method,
        is_ob_new=bool(row.get("ob_bullish", False) or row.get("ob_bearish", False)),
        within_ob=bool(np.isfinite(ob_top) and np.isfinite(ob_bottom) and (low <= max(ob_top, ob_bottom)) and (high >= min(ob_top, ob_bottom))),
        ob_mitigated=False,
        is_breaker=False,
    )

    hour = int(pd.to_datetime(row["time"], utc=True).hour)
    hour_sin = float(math.sin((2.0 * math.pi * hour) / 24.0))
    hour_cos = float(math.cos((2.0 * math.pi * hour) / 24.0))

    return {
        "bars_since_fvg_creation": int(max(0, idx - create_idx)),
        "bars_since_mitigation": int(max(0, idx - mitigation_idx)) if mitigation_idx is not None else int(max(0, idx - create_idx)),
        "mitigation_depth_pct": depth,
        "mitigation_touch_count": int(max(0, touch_count)),
        "distance_prev_day_high": _distance(close, pd_high, atr),
        "distance_prev_day_low": _distance(close, pd_low, atr),
        "distance_eqh": _distance(close, eqh_ref, atr),
        "distance_eql": _distance(close, eql_ref, atr),
        "ob_overlap_with_fvg": int(ob_overlap),
        "ob_state": schema["ob_state"],
        "session_bucket": schema["session_bucket"],
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
        "structure_event": schema["structure_event"],
        "structure_scale": schema["structure_scale"],
    }
