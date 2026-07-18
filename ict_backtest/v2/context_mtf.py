"""Multi-TF snapshots at decision time t — closed-only HTF (no mixing clocks).

Clock = exec/LTF bar time. Higher TFs are lookups of already-closed bars only.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ict_backtest._util import closed_row_at_time, tf_duration


def _trend_of(row: pd.Series | None) -> str:
    if row is None or (isinstance(row, float) and np.isnan(row)):
        return "RANGING"
    try:
        t = str(row.get("trend", row.get("macro_direction", "RANGING")))
    except Exception:
        return "RANGING"
    if t in ("BULLISH", "BEARISH"):
        return t
    return "RANGING"


def snapshot_tf(
    ms: dict[str, pd.DataFrame],
    tf: str,
    t: Any,
) -> dict[str, Any]:
    """Closed-only row snapshot for one TF at time t."""
    df = ms.get(tf)
    if df is None or len(df) == 0:
        return {"tf": tf, "available": False, "trend": "RANGING"}
    if tf in ("M1", "M5", "M15"):
        # LTF/exec: use last bar with time <= t (bar is the clock, already closed in loop)
        times = pd.to_datetime(df["time"], utc=True, errors="coerce")
        tt = pd.to_datetime(t, utc=True, errors="coerce")
        prior = df.index[times <= tt]
        if len(prior) == 0:
            return {"tf": tf, "available": False, "trend": "RANGING"}
        row = df.iloc[int(prior[-1])]
    else:
        row = closed_row_at_time(df, t, tf_duration(tf))
    if row is None:
        return {"tf": tf, "available": False, "trend": "RANGING"}
    fvg_state = str(row.get("fvg_state", "NONE") or "NONE")
    ob_dir = str(row.get("ob_direction", row.get("ob_dir", "-")) or "-")
    return {
        "tf": tf,
        "available": True,
        "trend": _trend_of(row),
        "close": float(row.get("close", np.nan) or np.nan),
        "high": float(row.get("high", np.nan) or np.nan),
        "low": float(row.get("low", np.nan) or np.nan),
        "sweep_up": bool(row.get("liquidity_sweep_up", False)),
        "sweep_down": bool(row.get("liquidity_sweep_down", False)),
        "bos_dir": int(row.get("bos_dir", row.get("bos_direction", 0)) or 0)
        if not isinstance(row.get("bos_direction", 0), str)
        else (1 if str(row.get("bos_direction")) == "BULLISH" else -1 if str(row.get("bos_direction")) == "BEARISH" else 0),
        "choch": str(row.get("choch_signal", row.get("choch_status", ""))),
        "fvg_state": fvg_state,
        "ob_dir": ob_dir,
        "time": str(row.get("time", t)),
    }


def dealing_range_pd(
    d1: pd.DataFrame,
    t: Any,
    lookback: int = 20,
) -> dict[str, Any]:
    """Premium/Discount from last N closed D1 bars ending at closed D1 for t."""
    row = closed_row_at_time(d1, t, tf_duration("D1"))
    if row is None or len(d1) < 5:
        return {"pd_side": "UNKNOWN", "eq": np.nan, "range_high": np.nan, "range_low": np.nan}
    times = pd.to_datetime(d1["time"], utc=True, errors="coerce")
    tt = pd.to_datetime(row["time"], utc=True, errors="coerce")
    # bars with time <= closed D1 time
    mask = times <= tt
    win = d1.loc[mask].tail(lookback)
    if len(win) < 3:
        return {"pd_side": "UNKNOWN", "eq": np.nan, "range_high": np.nan, "range_low": np.nan}
    rh = float(win["high"].max())
    rl = float(win["low"].min())
    eq = 0.5 * (rh + rl)
    px = float(row["close"])
    if px < eq:
        side = "DISCOUNT"
    elif px > eq:
        side = "PREMIUM"
    else:
        side = "EQ"
    return {
        "pd_side": side,
        "eq": eq,
        "range_high": rh,
        "range_low": rl,
        "close": px,
    }


def build_context_stack(
    ms: dict[str, pd.DataFrame],
    t: Any,
    *,
    tfs: tuple[str, ...] = ("D1", "H4", "H1", "M15"),
    anchored_pd_zones: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Top-down snapshots at t. Does not mix clocks — one t, many closed lookups.

    Si ``anchored_pd_zones`` trae zonas PD ancladas (p.ej. de htf_pd_index),
    se inyecta ``poi`` real en el snapshot del TF correspondiente (H4/H1).
    El ``dealing`` range (premium/discount) se inyecta como ``pd_side`` en D1/H4.
    """
    stack = {tf: snapshot_tf(ms, tf, t) for tf in tfs if tf in ms or tf in tfs}
    # ensure keys
    for tf in tfs:
        stack.setdefault(tf, {"tf": tf, "available": False, "trend": "RANGING"})
    # premium/discount por TF (D1/H4) via dealing range del propio TF
    for tf in ("D1", "H4"):
        df = ms.get(tf)
        if df is not None:
            dr = dealing_range_pd(df, t)
            stack[tf]["pd_side"] = dr.get("pd_side", "UNKNOWN")
    # POI anclado (H4/H1) desde htf_pd_index (Fase C)
    if anchored_pd_zones:
        for tf, zones in anchored_pd_zones.items():
            if tf in stack and zones:
                stack[tf]["pd_side"] = "PD"  # anclado presente
                stack[tf]["poi_count"] = len(zones)
    return stack


def top_down_allows_trade(
    stack: dict[str, Any],
    direction: int,
    *,
    require_d1: bool = True,
    require_h4: bool = True,
    require_h1: bool = True,
    require_pd: bool = True,
    counter_trend: bool = False,
) -> tuple[bool, str]:
    """Gate: D1 → H4 → H1 → PD. Returns (ok, reason).

    Note: run_sequence may already embed H4 bias; require_h4=False skips re-check
    (used for survival ablation of sequence-only flow).
    """
    d1 = stack.get("D1", {})
    h4 = stack.get("H4", {})
    h1 = stack.get("H1", {})
    dealing = stack.get("dealing", {})

    if require_d1:
        if not d1.get("available"):
            return False, "d1_unavailable"
        if d1.get("trend") == "RANGING":
            return False, "d1_ranging"
        # For with-trend models: D1 must agree with trade direction
        if not counter_trend:
            if direction > 0 and d1.get("trend") != "BULLISH":
                return False, "d1_against_long"
            if direction < 0 and d1.get("trend") != "BEARISH":
                return False, "d1_against_short"
        else:
            # CT: trade against D1 is intended
            if direction > 0 and d1.get("trend") != "BEARISH":
                return False, "d1_ct_needs_bearish"
            if direction < 0 and d1.get("trend") != "BULLISH":
                return False, "d1_ct_needs_bullish"

    if require_h4:
        if not h4.get("available"):
            return False, "h4_unavailable"
        if h4.get("trend") == "RANGING":
            return False, "h4_ranging"
        if not counter_trend:
            if direction > 0 and h4.get("trend") != "BULLISH":
                return False, "h4_against_long"
            if direction < 0 and h4.get("trend") != "BEARISH":
                return False, "h4_against_short"

    if require_h1 and "H1" in stack:
        if not h1.get("available"):
            return False, "h1_unavailable"
        # H1 must not be strongly opposing (ranging OK as soft zone)
        if not counter_trend:
            if direction > 0 and h1.get("trend") == "BEARISH":
                return False, "h1_opposes_long"
            if direction < 0 and h1.get("trend") == "BULLISH":
                return False, "h1_opposes_short"

    if require_pd:
        side = dealing.get("pd_side", "UNKNOWN")
        if side == "UNKNOWN":
            return False, "pd_unknown"
        # Longs prefer discount; shorts prefer premium (thesis / POI)
        if direction > 0 and side == "PREMIUM":
            return False, "long_in_premium"
        if direction < 0 and side == "DISCOUNT":
            return False, "short_in_discount"

    return True, "ok"
