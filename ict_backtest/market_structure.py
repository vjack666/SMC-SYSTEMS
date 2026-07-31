"""ict_backtest/market_structure.py — Reglas canonicas BOS / CHOCH (ICT/SMC).

Diseno corregido (estado secuencial + onset-only + clasificacion TF):
- bias state: 0 = sin estructura, +1 = alcista, -1 = bajista
- BOS: ruptura confirmada del swing previo, en la direccion del bias actual
  o desde bias=0.
- CHOCH: ruptura confirmada del swing opuesto que define el caracter
  de la tendencia anterior (no el nivel ya roto por el BOS anterior).
- Solo emite en el onset (primera confirmacion del nivel), evitando repeticiones.
- Estructura invalida por evento: close vuelve a cruzar el nivel roto.
- Clasificacion: HTF si el swing roto pertenece a la lista HTF pasada;
  ITF si pertenece a un TF intermedio; LTF si es del propio frame analizado.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StructureConfig:
    swing_lookback: int = 5
    confirm_bars: int = 2
    # Clasificacion de niveles por capa temporal.
    # Si se pasa, `detect_market_structure` marca HTF/ITF/LTF en `event_tf_level`.
    # Formato: {"HTF": {nivel1, nivel2,...}, "ITF": {...}}
    # Si es None, `event_tf_level` queda en blanco para ese evento.
    tf_levels: dict[str, set[float]] | None = None


def _swing_points(frame: pd.DataFrame, lookback: int) -> tuple[pd.Series, pd.Series]:
    """Detecta swing high/low SIN look-ahead."""
    window = lookback + 1
    roll_h = frame["high"].rolling(window=window, center=False, min_periods=window)
    roll_l = frame["low"].rolling(window=window, center=False, min_periods=window)
    max_h = roll_h.max()
    min_l = roll_l.min()
    sh_raw = frame["high"].where(
        (frame["high"] == max_h) & (max_h > max_h.shift(1).fillna(max_h))
    )
    sl_raw = frame["low"].where(
        (frame["low"] == min_l) & (min_l < min_l.shift(1).fillna(min_l))
    )
    return sh_raw.shift(lookback).ffill(), sl_raw.shift(lookback).ffill()


def _label_swings(swing_high: pd.Series, swing_low: pd.Series) -> pd.Series:
    labels = pd.Series(["NONE"] * len(swing_high), index=swing_high.index)
    new_high = swing_high.notna() & (swing_high != swing_high.shift(1))
    new_low = swing_low.notna() & (swing_low != swing_low.shift(1))
    prev_high = swing_high.where(new_high).ffill().shift(1)
    prev_low = swing_low.where(new_low).ffill().shift(1)
    labels[new_high & prev_high.isna()] = "HH"
    labels[new_high & (swing_high > prev_high)] = "HH"
    labels[new_high & (swing_high < prev_high)] = "LH"
    labels[new_low & prev_low.isna()] = "HL"
    labels[new_low & (swing_low > prev_low)] = "HL"
    labels[new_low & (swing_low < prev_low)] = "LL"
    return labels.where(new_high | new_low, pd.NA).ffill().fillna("NONE")


def _consecutive_break(break_mask: pd.Series, confirm_bars: int) -> pd.Series:
    """True donde hay `confirm_bars` rupturas CONSECUTIVAS del nivel."""
    if confirm_bars <= 1:
        return break_mask
    out = np.zeros(len(break_mask), dtype=bool)
    run = 0
    arr = break_mask.to_numpy()
    for i in range(len(arr)):
        run = run + 1 if arr[i] else 0
        if run >= confirm_bars:
            out[i] = True
    return pd.Series(out, index=break_mask.index)


def _classify_level(level: float, tf_levels: dict[str, set[float]]) -> str:
    if not tf_levels:
        return ""
    if level in tf_levels.get("HTF", set()):
        return "HTF"
    if level in tf_levels.get("ITF", set()):
        return "ITF"
    return "LTF"


def detect_market_structure(
    frame: pd.DataFrame,
    config: StructureConfig | None = None,
    tf_levels: dict[str, set[float]] | None = None,
) -> pd.DataFrame:
    """Aplica las reglas canonicas BOS/CHOCH con estado secuencial y clasifica HTF/ITF/LTF.

    Si `config.tf_levels` o `tf_levels` están presentes, coloca en `event_tf_level`
    HTF/ITF/LTF según la pertenencia del swing roto a esos conjuntos.
    """
    if config is None:
        config = StructureConfig()
    levels = tf_levels if tf_levels is not None else (config.tf_levels or {})

    d = frame.copy().reset_index(drop=True)
    sh, sl = _swing_points(d, config.swing_lookback)
    d["swing_high"], d["swing_low"] = sh, sl
    d["swing_label"] = _label_swings(sh, sl)

    if "time" not in d.columns:
        d["time"] = pd.Series([pd.NaT] * len(d), index=d.index)

    bull_break = d["close"] > sh.shift(1)
    bear_break = d["close"] < sl.shift(1)
    bull_conf = _consecutive_break(bull_break, config.confirm_bars)
    bear_conf = _consecutive_break(bear_break, config.confirm_bars)

    n = len(d)
    bos_dir = np.zeros(n, dtype=int)
    choch_dir = np.zeros(n, dtype=int)
    bos_level = np.full(n, np.nan)
    choch_level = np.full(n, np.nan)
    bos_status = pd.Series(["none"] * n, index=d.index, dtype=object)
    choch_status = pd.Series(["none"] * n, index=d.index, dtype=object)
    bos_age = pd.Series(0, index=d.index, dtype=int)
    choch_age = pd.Series(0, index=d.index, dtype=int)
    structure_label = pd.Series("", index=d.index, dtype=object)
    event_tf_level = pd.Series("", index=d.index, dtype=object)

    bias = 0
    last_bos_idx = -1
    last_choch_idx = -1
    bos_active = False
    choch_active = False
    last_bos_level_val = float("nan")
    last_choch_level_val = float("nan")

    close = d["close"].to_numpy()
    sh_arr = sh.to_numpy()
    sl_arr = sl.to_numpy()

    for i in range(1, n):
        event_dir = 0
        event_level = float("nan")
        event_type = ""
        tf_level = ""

        # Detectar ruptura confirmada
        if bull_conf.iloc[i]:
            event_dir = 1
            event_level = float(sh_arr[i - 1]) if i > 0 else float("nan")
        elif bear_conf.iloc[i]:
            event_dir = -1
            event_level = float(sl_arr[i - 1]) if i > 0 else float("nan")

        if event_dir != 0 and not np.isnan(event_level):
            # Clasificar segun bias
            if bias == 0 or bias == event_dir:
                event_type = "BOS"
                bos_dir[i] = event_dir
                bos_level[i] = event_level
                bias = event_dir
                last_bos_idx = i
                last_bos_level_val = event_level
                bos_active = True
                tf_level = _classify_level(event_level, levels)
                # Un BOS nuevo invalida CHOCH previo
                choch_active = False
            else:
                # CHOCH: confirmar que rompe el swing opuesto de la estructura
                if event_dir == 1:
                    opposite_level = float("nan")
                    for j in range(last_bos_idx, -1, -1):
                        if not np.isnan(sh_arr[j]):
                            opposite_level = float(sh_arr[j])
                            break
                    if not np.isnan(opposite_level) and event_level > opposite_level:
                        event_type = "CHOCH"
                        choch_dir[i] = event_dir
                        choch_level[i] = opposite_level
                        bias = event_dir
                        last_choch_idx = i
                        last_choch_level_val = opposite_level
                        tf_level = _classify_level(opposite_level, levels)
                        choch_active = True
                        bos_active = False
                else:
                    opposite_level = float("nan")
                    for j in range(last_bos_idx, -1, -1):
                        if not np.isnan(sl_arr[j]):
                            opposite_level = float(sl_arr[j])
                            break
                    if not np.isnan(opposite_level) and event_level < opposite_level:
                        event_type = "CHOCH"
                        choch_dir[i] = event_dir
                        choch_level[i] = opposite_level
                        bias = event_dir
                        last_choch_idx = i
                        last_choch_level_val = opposite_level
                        tf_level = _classify_level(opposite_level, levels)
                        choch_active = True
                        bos_active = False

            if event_type:
                structure_label[i] = event_type
                event_tf_level[i] = tf_level

        # Invalidacion BOS
        if bos_active and last_bos_idx >= 0:
            crossed = (bos_dir[last_bos_idx] == 1 and close[i] < last_bos_level_val) or \
                      (bos_dir[last_bos_idx] == -1 and close[i] > last_bos_level_val)
            if crossed:
                bos_status.iloc[last_bos_idx] = "invalidated"
                bos_active = False
            else:
                bos_status.iloc[last_bos_idx] = "active"
            bos_age.iloc[last_bos_idx] = i - last_bos_idx

        # Invalidacion CHOCH
        if choch_active and last_choch_idx >= 0:
            crossed = (choch_dir[last_choch_idx] == 1 and close[i] < last_choch_level_val) or \
                      (choch_dir[last_choch_idx] == -1 and close[i] > last_choch_level_val)
            if crossed:
                choch_status.iloc[last_choch_idx] = "invalidated"
                choch_active = False
            else:
                choch_status.iloc[last_choch_idx] = "active"
            choch_age.iloc[last_choch_idx] = i - last_choch_idx

    d["bos_dir"] = bos_dir
    d["choch_dir"] = choch_dir
    d["bos_level"] = bos_level
    d["choch_level"] = choch_level
    d["bos_status"] = bos_status
    d["choch_status"] = choch_status
    d["bos_age"] = bos_age
    d["choch_age"] = choch_age
    d["structure_label"] = structure_label
    d["event_tf_level"] = event_tf_level
    d["trend"] = _derive_trend(d)
    return d


def _derive_trend(d: pd.DataFrame) -> pd.Series:
    """Tendencia por pendiente de swings: HH/HL -> BULLISH; LH/LL -> BEARISH; sino RANGING."""
    lab = d["swing_label"].fillna("NONE")
    bull = (lab == "HH") | (lab == "HL")
    bear = (lab == "LH") | (lab == "LL")
    return np.select([bull, bear], ["BULLISH", "BEARISH"], default="RANGING")


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from ict_backtest.data_feed import load_frames
    fr = load_frames("XAUUSD", ("H4",))
    ms = detect_market_structure(fr["H4"])
    bos_onsets = int((ms["bos_dir"] != 0).sum())
    choch_onsets = int((ms["choch_dir"] != 0).sum())
    print("BOS onsets:", bos_onsets)
    print("CHOCH onsets:", choch_onsets)
    print("BOS >= CHOCH:", bos_onsets >= choch_onsets)
    print("trend counts:", ms["trend"].value_counts().to_dict())
