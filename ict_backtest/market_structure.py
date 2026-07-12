"""ict_backtest/market_structure.py — Reglas canonicas BOS / CHOCH (ICT/SMC).

Documenta y APLICA cuando un BOS o CHOCH se considera activo/valido/
invalidado, segun la teoria ICT (innercircletrader) y SMC (dailypriceaction):

  BOS (Break of Structure):
    - Alcista: el close (cuerpo) supera el ULTIMO swing high.
    - Bajista: el close (cuerpo) perfora el ULTIMO swing low.
    - Si el swing roto es HH/HL (en tendencia), es continuacion.
    - Si el swing roto es LH/LL (en correccion), es BOS de correccion (no cambia tendencia).
    - ACTIVO desde el break hasta que el precio CRUZA de nuevo el nivel roto
      (invalidacion) o se aleja menos de max_age_atr*ATR sin follow-through (aged).

  CHOCH (Change of Character):
    - Es el BOS que rompe el swing que DEFINE la tendencia opuesta.
    - Alcista (HH -> LH -> LL luego sube y rompe el LH/estructura): confirma giro a alcista.
    - Bajista (LL -> HL -> HH luego baja y rompe el HL): confirma giro a bajista.
    - REGLA CLAVE (dailypriceaction): un CHOCH valido debe romper el swing que
      produjo el ULTIMO BOS. Si rompe un swing equivocado, no cuenta.
    - ACTIVO hasta invalidacion (precio rompe en sentido contrario el swing del CHOCH)
      o envejecimiento por volatilidad.

Confirmacion y caducidad ORIENTADAS A LA REALIDAD DEL MERCADO (no velas fijas):
  - CONFIRMACION: la ruptura se marca solo con el CUERPO (close), nunca la mecha
    (wick = liquidity sweep, no estructura — TradingStrategyGuides 2026). Para
    reducir fakeouts (Turtle Soups) se exige `confirm_bars` cierres CONSECUTIVOS
    rompiendo el nivel (LuxAlgo Market Structure ICT, feb 2026: "two consecutive
    candle bodies close beyond a previous swing level").
  - CADUCIDAD: en lugar de un numero fijo de velas (max_age), la estructura
    "envejece" (aged) si el precio NO se aleja al menos `max_age_atr` * ATR del
    nivel roto. Asi la validez se adapta a la volatilidad real del par/TF
    (EURUSD M15 != XAUUSD H4), no a una constante magica.

El detector de este modulo es EVENT-DRIVEN y SECUENCIAL: no evalua todo de
golpe, sino que va marcando el estado de estructura vela a vela (memoria de
estado), que es justo lo que necesita el motor para la Capa 2 (event-sequence).

Fuentes (verificadas 2026-07-12):
  - LuxAlgo — Market Structure & ICT Concepts: confirmacion por 2 cuerpos consecutivos.
  - TradingStrategyGuides — "a wick alone does not confirm a structure break;
    price must close (full candle body) beyond the previous swing point".
  - Strike.money — BOS: estructura -> break -> confirmation (cierre decisivo) -> continuation.
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
    # Confirmacion: cuantos cierres CONSECUTIVOS deben romper el nivel.
    # 1 = una sola vela (comportamiento original); 2 = filtra fakeouts (LuxAlgo).
    confirm_bars: int = 2
    # Caducidad por volatilidad: la estructura "aged" si el precio lleva
    # `max_age_bars` velas SEGUIDAS sin alejarse `max_age_atr` * ATR del nivel
    # roto. Reemplaza el max_age fijo. 24 = paridad con el comportamiento
    # previo a la caducidad ATR (bos_max_age=24 / choch_max_age=20).
    max_age_atr: float = 1.5
    max_age_bars: int = 24


def _atr(frame: pd.DataFrame, period: int) -> pd.Series:
    """ATR clasico (Wilder) sobre high/low/close."""
    high = frame["high"].to_numpy()
    low = frame["low"].to_numpy()
    close = frame["close"].to_numpy()
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum.reduce([
        high - low,
        np.abs(high - prev_close),
        np.abs(low - prev_close),
    ])
    tr_series = pd.Series(tr, index=frame.index)
    atr_series = tr_series.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    return pd.Series(atr_series.to_numpy(), index=frame.index)


def _swing_points(frame: pd.DataFrame, lookback: int) -> tuple[pd.Series, pd.Series]:
    """Detecta swing high/low SIN look-ahead.

    El swing en la fila i se confirma recien en i+lookback (hay que ver que
    nada lo supere en las siguientes `lookback` velas). Ventana NO centrada
    (solo hacia atras) + descarte de empates planos, luego shift(lookback)+ffill
    para exponer el valor solo desde la vela de confirmacion (hallazgo #1).
    """
    window = lookback + 1
    roll_h = frame["high"].rolling(window=window, center=False, min_periods=window)
    roll_l = frame["low"].rolling(window=window, center=False, min_periods=window)
    max_h = roll_h.max()
    min_l = roll_l.min()
    sh_raw = frame["high"].where(
        (frame["high"] == max_h) & (max_h > max_h.shift(1).fillna(max_h)))
    sl_raw = frame["low"].where(
        (frame["low"] == min_l) & (min_l < min_l.shift(1).fillna(min_l)))
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
    """True donde hay `confirm_bars` rupturas CONSECUTIVAS del nivel.

    Una sola ruptura puede ser un wick/fakeout; exigir N cierres seguidos
    filtra los Turtle Soups (LuxAlgo: 2 cuerpos consecutivos).
    """
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
    atr = _atr(d, config.atr_period)
    d["_atr"] = atr.to_numpy()

    # BOS: close (cuerpo) rompe el swing previo, CONFIRMADO por `confirm_bars`
    # cierres consecutivos (filtra fakeouts).
    bull_break = d["close"] > sh.shift(1)
    bear_break = d["close"] < sl.shift(1)
    bull_conf = _consecutive_break(bull_break, config.confirm_bars)
    bear_conf = _consecutive_break(bear_break, config.confirm_bars)
    d["bos_dir"] = np.select([bull_conf, bear_conf], [1, -1], default=0)
    d["bos_level"] = np.where(d["bos_dir"] == 1, sh.shift(1),
                      np.where(d["bos_dir"] == -1, sl.shift(1), np.nan))

    d["bos_status"], d["bos_age"] = _track_structure(d, config, is_choch=False)
    # CHOCH real (hallazgo #2): rompe el swing que produjo el ULTIMO BOS,
    # en direccion OPUESTA a ese BOS. No es una copia de BOS.
    last_bos_dir = d["_last_bos_dir"].to_numpy()
    last_bos_level = d["_last_bos_level"].to_numpy()
    up_choch = (d["close"].to_numpy() > last_bos_level) & (last_bos_dir == -1)
    dn_choch = (d["close"].to_numpy() < last_bos_level) & (last_bos_dir == 1)
    choch_raw = np.select([up_choch, dn_choch], [1, -1], default=0)
    # CHOCH tambien requiere confirmacion por cuerpo consecutivo.
    d["choch_dir"] = _consecutive_break(
        pd.Series(choch_raw != 0, index=d.index), config.confirm_bars
    ).astype(int) * choch_raw
    d = d.drop(columns=["_last_bos_dir", "_last_bos_level", "_atr"])
    d["choch_status"], d["choch_age"] = _track_structure(d, config, is_choch=True)
    d["trend"] = _derive_trend(d)
    return d


def _track_structure(d: pd.DataFrame, config: StructureConfig, is_choch: bool = False) -> tuple[pd.Series, pd.Series]:
    """Sigue validez de BOS o CHOCH vela a vela.

    Invalidacion: el cierre CRUZA de nuevo el nivel roto (por cuerpo).
    Envejecimiento (aged): el precio lleva `max_age_bars` velas SEGUIDAS sin
    alejarse al menos `max_age_atr` * ATR del nivel roto. Es decir: la
    estructura "muere" solo tras un periodo de no-progress medido en volatilidad
    real, no por un numero ciego de velas. Si en cualquier vela el precio se
    aleja el umbral ATR, el contador de descanso se resetea.
    """
    n = len(d)
    status = pd.Series(["none"] * n, index=d.index, dtype=object)
    age = pd.Series([0] * n, index=d.index, dtype=int)
    last_dir = 0
    last_level = float("nan")
    last_idx = -1
    active = False
    rest_bars = 0  # velas seguidas sin alejarse el umbral ATR
    low = d["low"].to_numpy()
    high = d["high"].to_numpy()
    close = d["close"].to_numpy()
    atr = d["_atr"].to_numpy() if "_atr" in d.columns else np.zeros(n)
    dir_col = d["choch_dir"].to_numpy() if is_choch else d["bos_dir"].to_numpy()
    sh = d["swing_high"].to_numpy()
    slv = d["swing_low"].to_numpy()
    bos_level = d["bos_level"].to_numpy() if "bos_level" in d.columns else np.full(n, np.nan)
    last_dir_col = np.zeros(n, dtype=int)
    last_level_col = np.full(n, np.nan)

    for i in range(1, n):
        dr = int(dir_col[i])
        if dr != 0:
            last_dir, last_idx, active = dr, i, True
            rest_bars = 0
            if is_choch:
                last_level = float(sh[i]) if dr == 1 else float(slv[i])
            else:
                last_level = float(bos_level[i]) if pd.notna(bos_level[i]) else last_level
        if active:
            age.iloc[i] = i - last_idx
            crossed = ((last_dir == 1 and close[i] < last_level) or
                       (last_dir == -1 and close[i] > last_level))
            dist = (close[i] - last_level) if last_dir == 1 else (last_level - close[i])
            threshold = config.max_age_atr * atr[i] if atr[i] > 0 else 0.0
            progressed = dist >= threshold
            if progressed:
                rest_bars = 0
            else:
                rest_bars += 1
            if crossed:
                status.iloc[i], active = "invalidated", False
            # Envejecimiento por volatilidad REAL: la estructura muere solo tras
            # `max_age_bars` velas SEGUIDAS sin alejarse `max_age_atr`*ATR del
            # nivel roto (no por una sola vela lenta). `rest_bars` acumula las
            # velas de no-progress y se resetea en cuanto el precio progresa.
            elif rest_bars > config.max_age_bars:
                status.iloc[i], active = "aged", False
            else:
                status.iloc[i] = "active"
        last_dir_col[i] = last_dir
        last_level_col[i] = last_level

    if not is_choch:
        # Columnas temporales para que el CHOCH real use el ultimo BOS (hallazgo #2).
        d["_last_bos_dir"] = last_dir_col
        d["_last_bos_level"] = last_level_col
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
