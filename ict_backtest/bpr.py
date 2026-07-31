"""ict_backtest/bpr.py — Balanced Price Range (BPR): geometría + invalidación.

BPR = solape en precio de un FVG y un OB de la misma dirección (tesis 21_POI T1).

Geometría (sin indicadores):
    bpr_low  = max(fvg_low, ob_low)
    bpr_high = min(fvg_high, ob_high)
    hay_BPR  <=> bpr_low < bpr_high

Invalidación event-driven (como OB, no por edad sola):
    1) Cierre de cuerpo más allá del extremo lejano del BPR
       - BPR bull: close < bpr_low  → invalidated
       - BPR bear: close > bpr_high → invalidated
    2) mitigated_touch: high/low toca el cuadro sin cierre más allá

Estados: none | just_created | active | mitigated_touch | invalidated

NO modifica BOS/CHOCH. NO usa ATR/RSI. Solo high/low/open/close.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

BprStatus = Literal["none", "just_created", "active", "mitigated_touch", "invalidated"]


@dataclass(frozen=True)
class BprConfig:
    """Parámetros de construcción e invalidación BPR."""

    lookback: int = 30
    min_depth: float = 0.0
    use_ob_body: bool = True
    invalidate_on_body_close: bool = True
    track_mitigation_touch: bool = True
    require_ob_active: bool = True


def overlap_interval(
    a_lo: float, a_hi: float, b_lo: float, b_hi: float
) -> tuple[float, float] | None:
    """Intersección de dos intervalos. None si no hay solape estricto."""
    if not (a_lo < a_hi and b_lo < b_hi):
        return None
    lo = max(a_lo, b_lo)
    hi = min(a_hi, b_hi)
    if lo < hi:
        return (lo, hi)
    return None


def _fvg_gap_bounds(data: pd.DataFrame, i: int) -> tuple[float, float, int] | None:
    """Gap real del FVG en barra i. dir +1 bull / -1 bear."""
    row = data.iloc[i]
    if bool(row.get("fvg_bullish", False)):
        if "fvg_zone_low" in data.columns and pd.notna(row.get("fvg_zone_low")):
            return float(row["fvg_zone_low"]), float(row["fvg_zone_high"]), 1
        if i < 2:
            return None
        return float(data.iloc[i - 2]["high"]), float(row["low"]), 1
    if bool(row.get("fvg_bearish", False)):
        if "fvg_zone_low" in data.columns and pd.notna(row.get("fvg_zone_low")):
            return float(row["fvg_zone_low"]), float(row["fvg_zone_high"]), -1
        if i < 2:
            return None
        return float(row["high"]), float(data.iloc[i - 2]["low"]), -1
    return None


def _ob_bounds(
    data: pd.DataFrame, j: int, *, use_body: bool
) -> tuple[float, float, int] | None:
    """Intervalo del OB en barra j. dir +1 bull / -1 bear."""
    row = data.iloc[j]
    bull = bool(row.get("ob_bullish", False))
    bear = bool(row.get("ob_bearish", False))
    if not bull and not bear:
        od = str(row.get("ob_direction", "-")).lower()
        bull = od == "bullish"
        bear = od == "bearish"
    if not bull and not bear:
        return None
    direction = 1 if bull else -1
    if use_body:
        o, c = float(row["open"]), float(row["close"])
        lo, hi = min(o, c), max(o, c)
    else:
        if pd.notna(row.get("ob_bottom")) and pd.notna(row.get("ob_top")):
            lo, hi = float(row["ob_bottom"]), float(row["ob_top"])
        else:
            lo, hi = float(row["low"]), float(row["high"])
    if not (lo < hi):
        return None
    if "ob_status" in data.columns:
        st = str(row.get("ob_status", ""))
        if st == "invalidated":
            return None
    return lo, hi, direction


def detect_bpr(frame: pd.DataFrame, cfg: BprConfig | None = None) -> pd.DataFrame:
    """Anota columnas BPR sobre un frame que ya tenga FVG y OB detectados.

    Columnas: bpr_bullish/bearish, bpr_low/high, bpr_depth, bpr_status, bpr_age.
    pd_type=BPR, pd_tier=T1 en barras live.
    """
    cfg = cfg or BprConfig()
    data = frame.copy().reset_index(drop=True)
    n = len(data)

    bpr_bull = np.zeros(n, dtype=bool)
    bpr_bear = np.zeros(n, dtype=bool)
    bpr_lo = np.full(n, np.nan)
    bpr_hi = np.full(n, np.nan)
    bpr_depth = np.full(n, np.nan)
    status: list[str] = ["none"] * n
    age = np.zeros(n, dtype=int)

    active_dir = 0
    active_lo = float("nan")
    active_hi = float("nan")
    active_idx = -1
    active_alive = False
    touched = False

    for i in range(n):
        if active_alive:
            age[i] = i - active_idx
            close_i = float(data.iloc[i]["close"])
            high_i = float(data.iloc[i]["high"])
            low_i = float(data.iloc[i]["low"])

            invalidated = False
            if cfg.invalidate_on_body_close:
                if active_dir == 1 and close_i < active_lo:
                    invalidated = True
                elif active_dir == -1 and close_i > active_hi:
                    invalidated = True

            if invalidated:
                status[i] = "invalidated"
                active_alive = False
                active_dir = 0
                touched = False
            else:
                if cfg.track_mitigation_touch:
                    if low_i <= active_hi and high_i >= active_lo:
                        touched = True
                status[i] = "mitigated_touch" if touched else "active"
                bpr_lo[i] = active_lo
                bpr_hi[i] = active_hi
                if active_dir == 1:
                    bpr_bull[i] = True
                else:
                    bpr_bear[i] = True

        gap = _fvg_gap_bounds(data, i)
        if gap is None:
            continue
        f_lo, f_hi, f_dir = gap
        fvg_size = f_hi - f_lo
        if fvg_size <= 0:
            continue

        j0 = max(0, i - cfg.lookback)
        best: tuple[float, float, float] | None = None
        for j in range(j0, i + 1):
            if cfg.require_ob_active and "ob_status" in data.columns:
                st = str(data.iloc[j].get("ob_status", "none"))
                if st == "invalidated":
                    continue
            ob = _ob_bounds(data, j, use_body=cfg.use_ob_body)
            if ob is None:
                continue
            o_lo, o_hi, o_dir = ob
            if o_dir != f_dir:
                continue
            box = overlap_interval(f_lo, f_hi, o_lo, o_hi)
            if box is None:
                continue
            lo, hi = box
            depth = (hi - lo) / fvg_size
            if depth < cfg.min_depth:
                continue
            if best is None or depth > best[2]:
                best = (lo, hi, depth)

        if best is None:
            continue

        lo, hi, depth = best
        bpr_lo[i] = lo
        bpr_hi[i] = hi
        bpr_depth[i] = depth
        status[i] = "just_created"
        age[i] = 0
        if f_dir == 1:
            bpr_bull[i] = True
        else:
            bpr_bear[i] = True

        active_dir = f_dir
        active_lo, active_hi = lo, hi
        active_idx = i
        active_alive = True
        touched = False

    data["bpr_bullish"] = bpr_bull
    data["bpr_bearish"] = bpr_bear
    data["bpr_low"] = bpr_lo
    data["bpr_high"] = bpr_hi
    data["bpr_depth"] = bpr_depth
    data["bpr_status"] = status
    data["bpr_age"] = age

    is_bpr = bpr_bull | bpr_bear
    if "pd_type" not in data.columns:
        data["pd_type"] = "NONE"
    if "pd_tier" not in data.columns:
        data["pd_tier"] = "NONE"
    live = is_bpr & np.array([s not in ("invalidated", "none") for s in status])
    data.loc[live, "pd_type"] = "BPR"
    data.loc[live, "pd_tier"] = "T1"

    return data


def validate_bpr_invalidation(
    data: pd.DataFrame,
    *,
    cfg: BprConfig | None = None,
) -> dict:
    """Auditoría de consistencia de la máquina de estados BPR.

    Invariantes:
      I1: just_created solo con flags e intervalo válido
      I2: no active inmediatamente tras invalidated sin create
      I3: invalidated solo si close cruza extremo lejano (si cfg lo exige)
      I4: depth en (0, 1] en just_created
      I5: nunca low >= high en estados live
    """
    cfg = cfg or BprConfig()
    violations: list[str] = []
    n = len(data)
    if n == 0 or "bpr_status" not in data.columns:
        return {"ok": True, "n": n, "violations": [], "counts": {}, "n_violations": 0}

    status = data["bpr_status"].astype(str).tolist()
    counts: dict[str, int] = {}
    for s in status:
        counts[s] = counts.get(s, 0) + 1

    last_live_lo = float("nan")
    last_live_hi = float("nan")
    last_live_dir = 0

    for i in range(n):
        st = status[i]
        lo = data["bpr_low"].iloc[i]
        hi = data["bpr_high"].iloc[i]
        bull = bool(data["bpr_bullish"].iloc[i]) if "bpr_bullish" in data.columns else False
        bear = bool(data["bpr_bearish"].iloc[i]) if "bpr_bearish" in data.columns else False

        if st == "just_created":
            if not (bull or bear):
                violations.append(f"I1@{i}: just_created sin flag bull/bear")
            if not (pd.notna(lo) and pd.notna(hi) and float(lo) < float(hi)):
                violations.append(f"I1@{i}: just_created con intervalo inválido")
            depth = data["bpr_depth"].iloc[i] if "bpr_depth" in data.columns else np.nan
            if pd.notna(depth) and not (0.0 < float(depth) <= 1.0 + 1e-9):
                violations.append(f"I4@{i}: depth={depth} fuera de (0,1]")
            last_live_lo, last_live_hi = float(lo), float(hi)
            last_live_dir = 1 if bull else -1

        elif st in ("active", "mitigated_touch"):
            if i > 0 and status[i - 1] == "invalidated":
                violations.append(f"I2@{i}: {st} tras invalidated sin create")
            if pd.notna(lo) and pd.notna(hi) and not (float(lo) < float(hi)):
                violations.append(f"I5@{i}: {st} con low>=high")
            if pd.notna(lo):
                last_live_lo, last_live_hi = float(lo), float(hi)
                last_live_dir = 1 if bull else (-1 if bear else last_live_dir)

        elif st == "invalidated":
            if cfg.invalidate_on_body_close and pd.notna(last_live_lo):
                close_i = float(data.iloc[i]["close"])
                ok_reason = (
                    (last_live_dir == 1 and close_i < last_live_lo)
                    or (last_live_dir == -1 and close_i > last_live_hi)
                )
                if not ok_reason:
                    violations.append(
                        f"I3@{i}: invalidated sin close más allá del extremo "
                        f"(close={close_i}, box=[{last_live_lo},{last_live_hi}])"
                    )

    return {
        "ok": len(violations) == 0,
        "n": n,
        "counts": counts,
        "violations": violations[:50],
        "n_violations": len(violations),
    }
