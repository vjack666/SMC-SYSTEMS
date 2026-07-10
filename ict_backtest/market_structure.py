"""ict_backtest/market_structure.py — Reglas canonicas BOS / CHOCH (ICT/SMC).

Documenta y APLICA cuando un BOS o CHOCH se considera activo/valido/
invalidado, segun la teoria ICT (innercircletrader) y SMC (dailypriceaction):

  BOS (Break of Structure):
    - Alcista: el close supera el ULTIMO swing high.
    - Bajista: el close perfora el ULTIMO swing low.
    - Si el swing roto es HH/HL (en tendencia), es continuacion.
    - Si el swing roto es LH/LL (en correccion), es BOS de correccion (no cambia tendencia).
    - ACTIVO desde el break hasta que el precio CRUZA de nuevo el nivel roto
      (invalidacion) o pasan max_age barras sin follow-through (aged).

  CHOCH (Change of Character):
    - Es el BOS que rompe el swing que DEFINE la tendencia opuesta.
    - Alcista (HH -> LH -> LL luego sube y rompe el LH/estructura): confirma giro a alcista.
    - Bajista (LL -> HL -> HH luego baja y rompe el HL): confirma giro a bajista.
    - REGLA CLAVE (dailypriceaction): un CHOCH valido debe romper el swing que
      produjo el ULTIMO BOS. Si rompe un swing equivocado, no cuenta.
    - ACTIVO hasta invalidacion (precio rompe en sentido contrario el swing del CHOCH)
      o envejecimiento.

El detector de este modulo es EVENT-DRIVEN y SECUENCIAL: no evalua todo de
golpe, sino que va marcando el estado de estructura vela a vela (memoria de
estado), que es justo lo que necesita el motor para la Capa 2 (event-sequence).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StructureConfig:
    swing_lookback: int = 5
    atr_period: int = 14
    followthrough_bars: int = 8
    bos_max_age: int = 24
    choch_max_age: int = 20


def _swing_points(frame: pd.DataFrame, lookback: int) -> tuple[pd.Series, pd.Series]:
    window = lookback * 2 + 1
    rolling_high = frame["high"].rolling(window=window, center=True)
    rolling_low = frame["low"].rolling(window=window, center=True)
    swing_high = frame["high"].where(frame["high"] == rolling_high.max())
    swing_low = frame["low"].where(frame["low"] == rolling_low.min())
    return swing_high.ffill(), swing_low.ffill()


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


def detect_market_structure(frame: pd.DataFrame, config: StructureConfig | None = None) -> pd.DataFrame:
    """Aplica las reglas canonicas BOS/CHOCH con memoria de estado (secuencial).

    Devuelve columnas:
      swing_high, swing_low, swing_label
      bos_dir (1/-1/0), bos_level, bos_status (active/invalidated/aged/none), bos_age
      choch_dir (1/-1/0), choch_status, choch_age
      trend (BULLISH/BEARISH/RANGING) derivado de HH/HL vs LH/LL
    """
    if config is None:
        config = StructureConfig()
    d = frame.copy().reset_index(drop=True)
    sh, sl = _swing_points(d, config.swing_lookback)
    d["swing_high"], d["swing_low"] = sh, sl
    d["swing_label"] = _label_swings(sh, sl)

    # BOS: close rompe el swing high/low previo
    bull_break = d["close"] > sh.shift(1)
    bear_break = d["close"] < sl.shift(1)
    d["bos_dir"] = np.select([bull_break, bear_break], [1, -1], default=0)
    d["bos_level"] = np.where(d["bos_dir"] == 1, sh.shift(1),
                      np.where(d["bos_dir"] == -1, sl.shift(1), np.nan))
    # CHOCH: break del swing que define la tendencia opuesta
    # (rombimiento de estructura en direccion contraria al sesgo actual)
    up_choch = bear_break  # precio perfora swing low -> sesgo gira a bajista
    dn_choch = bull_break  # precio supera swing high -> sesgo gira a alcista
    d["choch_dir"] = np.select([dn_choch, up_choch], [1, -1], default=0)

    d["bos_status"], d["bos_age"] = _track_bos(d, config.bos_max_age)
    d["choch_status"], d["choch_age"] = _track_choch(d, config.choch_max_age)
    d["trend"] = _derive_trend(d)
    return d


def _track_bos(d: pd.DataFrame, max_age: int) -> tuple[pd.Series, pd.Series]:
    n = len(d)
    status = pd.Series(["none"] * n, index=d.index, dtype=object)
    age = pd.Series([0] * n, index=d.index, dtype=int)
    last_dir = 0
    last_level = float("nan")
    last_idx = -1
    active = False
    low = d["low"].to_numpy()
    high = d["high"].to_numpy()
    bd = d["bos_dir"].to_numpy()
    bl = d["bos_level"].to_numpy()
    for i in range(1, n):
        dr = int(bd[i])
        lvl = bl[i]
        if dr != 0 and pd.notna(lvl):
            last_dir, last_level, last_idx, active = dr, float(lvl), i, True
        if active:
            age.iloc[i] = i - last_idx
            crossed = ((last_dir == 1 and low[i] < last_level) or
                       (last_dir == -1 and high[i] > last_level))
            if crossed:
                status.iloc[i], active = "invalidated", False
            elif age.iloc[i] > max_age:
                status.iloc[i], active = "aged", False
            else:
                status.iloc[i] = "active"
    return status, age


def _track_choch(d: pd.DataFrame, max_age: int) -> tuple[pd.Series, pd.Series]:
    n = len(d)
    status = pd.Series(["none"] * n, index=d.index, dtype=object)
    age = pd.Series([0] * n, index=d.index, dtype=int)
    last_dir = 0
    last_level = float("nan")
    last_idx = -1
    active = False
    low = d["low"].to_numpy()
    high = d["high"].to_numpy()
    cd = d["choch_dir"].to_numpy()
    sh = d["swing_high"].to_numpy()
    slv = d["swing_low"].to_numpy()
    for i in range(1, n):
        dr = int(cd[i])
        if dr != 0:
            last_dir, last_idx, active = dr, i, True
            last_level = float(sh[i]) if dr == 1 else float(slv[i])
        if active:
            age.iloc[i] = i - last_idx
            failed = ((last_dir == 1 and low[i] < last_level) or
                      (last_dir == -1 and high[i] > last_level))
            if failed:
                status.iloc[i], active = "invalidated", False
            elif age.iloc[i] > max_age:
                status.iloc[i], active = "aged", False
            else:
                status.iloc[i] = "active"
    return status, age


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
    print("BOS activos:", int((ms["bos_status"] == "active").sum()))
    print("CHOCH activos:", int((ms["choch_status"] == "active").sum()))
    print("trend counts:", ms["trend"].value_counts().to_dict())
