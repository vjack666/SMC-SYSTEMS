"""ict_backtest/bpr.py — Balanced Price Range (BPR): geometría + invalidación + decay.

BPR = solape en precio de un FVG y un OB de la misma dirección (tesis 21_POI T1).

Geometría / invalidación / decay: ver docstring histórica.

Rendimiento (perf):
  - OHLC y flags se leen una vez como numpy (sin data.iloc en el hot path)
  - Gaps FVG y bounds OB se precomputan vectorizados
  - Solo se barre lookback de OB en índices donde hay FVG (sparse)
  - Score por age vía LUT (half-life) en vez de pow por barra
  - Máquina de estados sigue siendo O(n) secuencial (inevitable para invalidación)

NO modifica BOS/CHOCH. NO usa ATR/RSI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

BprStatus = Literal["none", "just_created", "active", "mitigated_touch", "invalidated"]

_STATUS_NONE = 0
_STATUS_CREATED = 1
_STATUS_ACTIVE = 2
_STATUS_TOUCH = 3
_STATUS_INVALID = 4
_STATUS_NAMES = ("none", "just_created", "active", "mitigated_touch", "invalidated")


@dataclass(frozen=True)
class BprConfig:
    """Parámetros de construcción, invalidación y decay de score."""

    lookback: int = 30
    min_depth: float = 0.0
    use_ob_body: bool = True
    invalidate_on_body_close: bool = True
    track_mitigation_touch: bool = True
    require_ob_active: bool = True

    score_base: float = 1.0
    score_floor: float = 0.15
    half_life_bars: int = 48
    freeze_decay_on_touch: bool = False
    depth_boost: float = 0.0


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


def bpr_score_at_age(
    age: int,
    *,
    base: float = 1.0,
    half_life_bars: int = 48,
    floor: float = 0.15,
    frozen: bool = False,
    frozen_score: float | None = None,
) -> float:
    """Decay exponencial por half-life en barras."""
    if frozen:
        return float(frozen_score if frozen_score is not None else base)
    if half_life_bars <= 0:
        return float(max(floor, base))
    age = max(0, int(age))
    raw = base * (0.5 ** (age / float(half_life_bars)))
    return float(max(floor, raw))


def _score_lut(n: int, base: float, half_life: int, floor: float) -> np.ndarray:
    """LUT score[age] para age=0..n (inclusive)."""
    ages = np.arange(n + 1, dtype=np.float64)
    if half_life <= 0:
        return np.full(n + 1, max(floor, base), dtype=np.float64)
    raw = base * np.power(0.5, ages / float(half_life))
    return np.maximum(floor, raw)


def _precompute_fvg_gaps(
    high: np.ndarray,
    low: np.ndarray,
    fvg_bull: np.ndarray,
    fvg_bear: np.ndarray,
    zone_lo: np.ndarray | None,
    zone_hi: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Arrays f_lo, f_hi, f_dir (0 si no FVG). Vectorizado."""
    n = len(high)
    f_lo = np.full(n, np.nan)
    f_hi = np.full(n, np.nan)
    f_dir = np.zeros(n, dtype=np.int8)

    if zone_lo is not None and zone_hi is not None:
        bull = fvg_bull & np.isfinite(zone_lo) & np.isfinite(zone_hi)
        bear = fvg_bear & np.isfinite(zone_lo) & np.isfinite(zone_hi)
        f_lo = np.where(bull | bear, zone_lo, f_lo)
        f_hi = np.where(bull | bear, zone_hi, f_hi)
        f_dir = np.where(bull, 1, f_dir)
        f_dir = np.where(bear, -1, f_dir)
    else:
        # bull: [high[i-2], low[i]]
        if n >= 3:
            prev2_high = np.empty(n, dtype=np.float64)
            prev2_low = np.empty(n, dtype=np.float64)
            prev2_high[:2] = np.nan
            prev2_low[:2] = np.nan
            prev2_high[2:] = high[:-2]
            prev2_low[2:] = low[:-2]
            bull = fvg_bull.copy()
            bull[:2] = False
            bear = fvg_bear.copy()
            bear[:2] = False
            f_lo = np.where(bull, prev2_high, f_lo)
            f_hi = np.where(bull, low, f_hi)
            f_lo = np.where(bear, high, f_lo)
            f_hi = np.where(bear, prev2_low, f_hi)
            f_dir = np.where(bull, 1, f_dir)
            f_dir = np.where(bear, -1, f_dir)

    return f_lo, f_hi, f_dir


def _precompute_ob_bounds(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    ob_bull: np.ndarray,
    ob_bear: np.ndarray,
    ob_top: np.ndarray | None,
    ob_bot: np.ndarray | None,
    ob_invalid: np.ndarray | None,
    *,
    use_body: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """o_lo, o_hi, o_dir; dir=0 si no hay OB usable."""
    n = len(open_)
    o_dir = np.zeros(n, dtype=np.int8)
    o_dir = np.where(ob_bull, 1, o_dir)
    o_dir = np.where(ob_bear, -1, o_dir)

    if use_body:
        o_lo = np.minimum(open_, close)
        o_hi = np.maximum(open_, close)
    else:
        if ob_top is not None and ob_bot is not None:
            o_lo = np.where(np.isfinite(ob_bot), ob_bot, low)
            o_hi = np.where(np.isfinite(ob_top), ob_top, high)
        else:
            o_lo = low.copy()
            o_hi = high.copy()

    valid = (o_dir != 0) & (o_lo < o_hi)
    if ob_invalid is not None:
        valid &= ~ob_invalid
    o_dir = np.where(valid, o_dir, 0)
    return o_lo, o_hi, o_dir


def _best_overlap_for_fvg(
    i: int,
    f_lo: float,
    f_hi: float,
    f_dir: int,
    o_lo: np.ndarray,
    o_hi: np.ndarray,
    o_dir: np.ndarray,
    lookback: int,
    min_depth: float,
) -> tuple[float, float, float] | None:
    """Mejor solape OB en (i-lookback, i] same dir. Solo índices con o_dir!=0."""
    fvg_size = f_hi - f_lo
    if fvg_size <= 0:
        return None
    j0 = 0 if i < lookback else i - lookback
    # slice
    dirs = o_dir[j0 : i + 1]
    mask = dirs == f_dir
    if not np.any(mask):
        return None
    idxs = np.nonzero(mask)[0] + j0
    best = None
    best_depth = -1.0
    for j in idxs:
        lo = o_lo[j] if o_lo[j] > f_lo else f_lo
        hi = o_hi[j] if o_hi[j] < f_hi else f_hi
        # max(f_lo,o_lo), min(f_hi,o_hi)
        if lo < hi:
            depth = (hi - lo) / fvg_size
            if depth >= min_depth and depth > best_depth:
                best_depth = depth
                best = (lo, hi, depth)
    return best


def detect_bpr(frame: pd.DataFrame, cfg: BprConfig | None = None) -> pd.DataFrame:
    """Anota BPR + bpr_score sobre frame con FVG/OB. Hot path en numpy."""
    cfg = cfg or BprConfig()
    data = frame.copy().reset_index(drop=True)
    n = len(data)
    if n == 0:
        data["bpr_bullish"] = False
        data["bpr_bearish"] = False
        data["bpr_low"] = np.nan
        data["bpr_high"] = np.nan
        data["bpr_depth"] = np.nan
        data["bpr_status"] = "none"
        data["bpr_age"] = 0
        data["bpr_score"] = 0.0
        return data

    open_ = data["open"].to_numpy(dtype=np.float64, copy=False)
    high = data["high"].to_numpy(dtype=np.float64, copy=False)
    low = data["low"].to_numpy(dtype=np.float64, copy=False)
    close = data["close"].to_numpy(dtype=np.float64, copy=False)

    fvg_bull = (
        data["fvg_bullish"].to_numpy(dtype=bool, copy=False)
        if "fvg_bullish" in data.columns
        else np.zeros(n, dtype=bool)
    )
    fvg_bear = (
        data["fvg_bearish"].to_numpy(dtype=bool, copy=False)
        if "fvg_bearish" in data.columns
        else np.zeros(n, dtype=bool)
    )

    zone_lo = (
        data["fvg_zone_low"].to_numpy(dtype=np.float64, copy=False)
        if "fvg_zone_low" in data.columns
        else None
    )
    zone_hi = (
        data["fvg_zone_high"].to_numpy(dtype=np.float64, copy=False)
        if "fvg_zone_high" in data.columns
        else None
    )

    ob_bull = (
        data["ob_bullish"].to_numpy(dtype=bool, copy=False)
        if "ob_bullish" in data.columns
        else np.zeros(n, dtype=bool)
    )
    ob_bear = (
        data["ob_bearish"].to_numpy(dtype=bool, copy=False)
        if "ob_bearish" in data.columns
        else np.zeros(n, dtype=bool)
    )
    if not ob_bull.any() and not ob_bear.any() and "ob_direction" in data.columns:
        od = data["ob_direction"].astype(str).str.lower().to_numpy()
        ob_bull = od == "bullish"
        ob_bear = od == "bearish"

    ob_top = (
        data["ob_top"].to_numpy(dtype=np.float64, copy=False)
        if "ob_top" in data.columns
        else None
    )
    ob_bot = (
        data["ob_bottom"].to_numpy(dtype=np.float64, copy=False)
        if "ob_bottom" in data.columns
        else None
    )
    ob_invalid = None
    if cfg.require_ob_active and "ob_status" in data.columns:
        ob_invalid = data["ob_status"].astype(str).to_numpy() == "invalidated"

    f_lo, f_hi, f_dir = _precompute_fvg_gaps(
        high, low, fvg_bull, fvg_bear, zone_lo, zone_hi
    )
    o_lo, o_hi, o_dir = _precompute_ob_bounds(
        open_, high, low, close, ob_bull, ob_bear, ob_top, ob_bot, ob_invalid,
        use_body=cfg.use_ob_body,
    )

    # Precomputar mejores BPR solo en barras FVG (sparse)
    create_lo = np.full(n, np.nan)
    create_hi = np.full(n, np.nan)
    create_depth = np.full(n, np.nan)
    create_dir = np.zeros(n, dtype=np.int8)
    fvg_idxs = np.nonzero(f_dir != 0)[0]
    lb = cfg.lookback
    md = cfg.min_depth
    for i in fvg_idxs:
        best = _best_overlap_for_fvg(
            int(i), float(f_lo[i]), float(f_hi[i]), int(f_dir[i]),
            o_lo, o_hi, o_dir, lb, md,
        )
        if best is not None:
            create_lo[i], create_hi[i], create_depth[i] = best
            create_dir[i] = f_dir[i]

    # LUT de score para base=1; se escala por active_base al aplicar
    lut = _score_lut(n, 1.0, cfg.half_life_bars, 0.0)  # floor aplicado después con base

    bpr_bull = np.zeros(n, dtype=bool)
    bpr_bear = np.zeros(n, dtype=bool)
    bpr_lo = np.full(n, np.nan)
    bpr_hi = np.full(n, np.nan)
    bpr_depth = np.full(n, np.nan)
    bpr_score = np.zeros(n, dtype=np.float64)
    status_code = np.zeros(n, dtype=np.int8)
    age = np.zeros(n, dtype=np.int32)

    active_dir = 0
    active_lo = 0.0
    active_hi = 0.0
    active_idx = -1
    active_alive = False
    touched = False
    active_base = cfg.score_base
    frozen = False
    frozen_score = 0.0
    inv_on = cfg.invalidate_on_body_close
    track_touch = cfg.track_mitigation_touch
    freeze_touch = cfg.freeze_decay_on_touch
    floor = cfg.score_floor
    hl = cfg.half_life_bars

    for i in range(n):
        if active_alive:
            age[i] = i - active_idx
            close_i = close[i]
            invalidated = False
            if inv_on:
                if active_dir == 1 and close_i < active_lo:
                    invalidated = True
                elif active_dir == -1 and close_i > active_hi:
                    invalidated = True

            if invalidated:
                status_code[i] = _STATUS_INVALID
                bpr_score[i] = 0.0
                active_alive = False
                active_dir = 0
                touched = False
                frozen = False
            else:
                if track_touch and low[i] <= active_hi and high[i] >= active_lo:
                    if not touched and freeze_touch:
                        a = int(age[i])
                        if hl <= 0:
                            frozen_score = max(floor, active_base)
                        else:
                            frozen_score = max(
                                floor, active_base * (0.5 ** (a / float(hl)))
                            )
                        frozen = True
                    touched = True
                status_code[i] = _STATUS_TOUCH if touched else _STATUS_ACTIVE
                bpr_lo[i] = active_lo
                bpr_hi[i] = active_hi
                if active_dir == 1:
                    bpr_bull[i] = True
                else:
                    bpr_bear[i] = True
                if frozen:
                    bpr_score[i] = frozen_score
                else:
                    a = int(age[i])
                    if hl <= 0:
                        bpr_score[i] = max(floor, active_base)
                    else:
                        # lut es para base=1; escalar
                        bpr_score[i] = max(floor, active_base * lut[a] if a < len(lut) else floor)

        # nacimiento (puede reemplazar activo en la misma barra)
        if create_dir[i] != 0:
            lo = create_lo[i]
            hi = create_hi[i]
            depth = create_depth[i]
            bpr_lo[i] = lo
            bpr_hi[i] = hi
            bpr_depth[i] = depth
            status_code[i] = _STATUS_CREATED
            age[i] = 0
            if create_dir[i] == 1:
                bpr_bull[i] = True
                bpr_bear[i] = False
            else:
                bpr_bear[i] = True
                bpr_bull[i] = False
            active_base = cfg.score_base * (1.0 + cfg.depth_boost * float(depth))
            bpr_score[i] = max(floor, active_base)  # age 0
            active_dir = int(create_dir[i])
            active_lo = float(lo)
            active_hi = float(hi)
            active_idx = i
            active_alive = True
            touched = False
            frozen = False

    status = [_STATUS_NAMES[int(c)] for c in status_code]

    data["bpr_bullish"] = bpr_bull
    data["bpr_bearish"] = bpr_bear
    data["bpr_low"] = bpr_lo
    data["bpr_high"] = bpr_hi
    data["bpr_depth"] = bpr_depth
    data["bpr_status"] = status
    data["bpr_age"] = age
    data["bpr_score"] = bpr_score

    if "pd_type" not in data.columns:
        data["pd_type"] = "NONE"
    if "pd_tier" not in data.columns:
        data["pd_tier"] = "NONE"
    live = (status_code == _STATUS_CREATED) | (status_code == _STATUS_ACTIVE) | (
        status_code == _STATUS_TOUCH
    )
    data.loc[live, "pd_type"] = "BPR"
    data.loc[live, "pd_tier"] = "T1"

    return data


def validate_bpr_invalidation(
    data: pd.DataFrame,
    *,
    cfg: BprConfig | None = None,
) -> dict:
    """Invariantes I1–I5 (geometría/invalidación) + I6–I8 (score/decay)."""
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
    prev_score_in_life: float | None = None
    has_score = "bpr_score" in data.columns
    close_arr = data["close"].to_numpy(dtype=np.float64, copy=False)
    bpr_lo_arr = data["bpr_low"].to_numpy(dtype=np.float64, copy=False)
    bpr_hi_arr = data["bpr_high"].to_numpy(dtype=np.float64, copy=False)
    bull_arr = (
        data["bpr_bullish"].to_numpy(dtype=bool, copy=False)
        if "bpr_bullish" in data.columns
        else np.zeros(n, dtype=bool)
    )
    bear_arr = (
        data["bpr_bearish"].to_numpy(dtype=bool, copy=False)
        if "bpr_bearish" in data.columns
        else np.zeros(n, dtype=bool)
    )
    score_arr = (
        data["bpr_score"].to_numpy(dtype=np.float64, copy=False)
        if has_score
        else None
    )
    depth_arr = (
        data["bpr_depth"].to_numpy(dtype=np.float64, copy=False)
        if "bpr_depth" in data.columns
        else None
    )

    for i in range(n):
        st = status[i]
        lo = bpr_lo_arr[i]
        hi = bpr_hi_arr[i]
        bull = bool(bull_arr[i])
        bear = bool(bear_arr[i])
        sc = float(score_arr[i]) if score_arr is not None else float("nan")

        if st in ("none", "invalidated"):
            if has_score and st == "invalidated" and sc != 0.0:
                violations.append(f"I6@{i}: invalidated con score={sc}")
            if has_score and st == "none" and sc != 0.0:
                violations.append(f"I6@{i}: none con score={sc}")
            if st == "invalidated":
                if cfg.invalidate_on_body_close and np.isfinite(last_live_lo):
                    close_i = float(close_arr[i])
                    ok_reason = (
                        (last_live_dir == 1 and close_i < last_live_lo)
                        or (last_live_dir == -1 and close_i > last_live_hi)
                    )
                    if not ok_reason:
                        violations.append(
                            f"I3@{i}: invalidated sin close más allá del extremo "
                            f"(close={close_i}, box=[{last_live_lo},{last_live_hi}])"
                        )
                prev_score_in_life = None
            continue

        if st == "just_created":
            if not (bull or bear):
                violations.append(f"I1@{i}: just_created sin flag bull/bear")
            if not (np.isfinite(lo) and np.isfinite(hi) and float(lo) < float(hi)):
                violations.append(f"I1@{i}: just_created con intervalo inválido")
            if depth_arr is not None:
                depth = depth_arr[i]
                if np.isfinite(depth) and not (0.0 < float(depth) <= 1.0 + 1e-9):
                    violations.append(f"I4@{i}: depth={depth} fuera de (0,1]")
            last_live_lo, last_live_hi = float(lo), float(hi)
            last_live_dir = 1 if bull else -1
            if has_score:
                if sc + 1e-12 < cfg.score_floor:
                    violations.append(f"I7@{i}: score {sc} < floor {cfg.score_floor}")
                prev_score_in_life = sc

        elif st in ("active", "mitigated_touch"):
            if i > 0 and status[i - 1] == "invalidated":
                violations.append(f"I2@{i}: {st} tras invalidated sin create")
            if np.isfinite(lo) and np.isfinite(hi) and not (float(lo) < float(hi)):
                violations.append(f"I5@{i}: {st} con low>=high")
            if np.isfinite(lo):
                last_live_lo, last_live_hi = float(lo), float(hi)
                last_live_dir = 1 if bull else (-1 if bear else last_live_dir)
            if has_score:
                if sc + 1e-12 < cfg.score_floor:
                    violations.append(f"I7@{i}: score {sc} < floor")
                if prev_score_in_life is not None and not cfg.freeze_decay_on_touch:
                    if sc > prev_score_in_life + 1e-9:
                        violations.append(
                            f"I8@{i}: score subió con la edad {prev_score_in_life}→{sc}"
                        )
                prev_score_in_life = sc

    return {
        "ok": len(violations) == 0,
        "n": n,
        "counts": counts,
        "violations": violations[:50],
        "n_violations": len(violations),
    }
