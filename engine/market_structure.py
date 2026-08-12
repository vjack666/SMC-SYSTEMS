"""ict_backtest/market_structure.py — Reglas canonicas BOS / CHOCH (ICT/SMC).

Documenta y APLICA cuando un BOS o CHOCH se considera activo/valido/
invalidado, segun la teoria ICT (innercircletrader) y SMC (dailypriceaction):

  BOS (Break of Structure):
    - Alcista: el close (cuerpo) supera el ULTIMO swing high.
    - Bajista: el close (cuerpo) perfora el ULTIMO swing low.
    - Si el swing roto es HH/HL (en tendencia), es continuacion.
    - Si el swing roto es LH/LL (en correccion), es BOS de correccion (no cambia tendencia).
    - ACTIVO desde el break hasta que el precio CRUZA de nuevo el nivel roto
      (invalidacion). EVENT-DRIVEN: no hay caducidad por tiempo/volatilidad.

  CHOCH (Change of Character):
    - Es el BOS que rompe el swing que DEFINE la tendencia opuesta.
    - Alcista (HH -> LH -> LL luego sube y rompe el LH/estructura): confirma giro a alcista.
    - Bajista (LL -> HL -> HH luego baja y rompe el HL): confirma giro a bajista.
    - REGLA CLAVE (dailypriceaction): un CHOCH valido debe romper el swing que
      produjo el ULTIMO BOS. Si rompe un swing equivocado, no cuenta.
    - ACTIVO hasta invalidacion (precio rompe en sentido contrario el swing del CHOCH)
      o invalidacion por cruce del nivel.

Confirmacion ORIENTADA A LA REALIDAD DEL MERCADO (no velas fijas):
  - CONFIRMACION: la ruptura se marca solo con el CUERPO (close), nunca la mecha
    (wick = liquidity sweep, no estructura — TradingStrategyGuides 2026). Para
    reducir fakeouts (Turtle Soups) se exige `confirm_bars` cierres CONSECUTIVOS
    rompiendo el nivel (LuxAlgo Market Structure ICT, feb 2026: "two consecutive
    candle bodies close beyond a previous swing level").
  - CADUCIDAD: EVENT-DRIVEN (Fase D). La estructura vive hasta el cruce del
    nivel (invalidated). NO hay "aged" por tiempo ni por volatilidad; se ELIMINO
    la dependencia de ATR (migracion ATR -> rango, Fase 1). La unica metrica de
    volatilidad del sistema es avg_candle_range (rango high-low), sin indicadores.

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
    followthrough_bars: int = 8
    # Confirmacion: cuantos cierres CONSECUTIVOS deben romper el nivel.
    # 1 = una sola vela (comportamiento original); 2 = filtra fakeouts (LuxAlgo).
    confirm_bars: int = 2
    # NOTE (migracion event-driven, Fase D): se ELIMINO la caducidad por
    # tiempo/volatilidad (max_age_atr / max_age_bars / "aged"). Las
    # estructuras ahora viven por EVENTO (cruce del nivel = invalidated),
    # no por un contador de velas. Ver docs/plan/MARKET_OBJECT_MODEL.md.
    # NOTE (migracion ATR -> rango, Fase 1): se ELIMINO `atr_period` y el
    # calculo de ATR (Wilder), que era CODIGO MUERTO tras eliminar el "aged".
    # La volatilidad del sistema es UNA sola: avg_candle_range (rango high-low),
    # sin indicadores. Ver _util.avg_candle_range.



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
    d = d.drop(columns=["_last_bos_dir", "_last_bos_level"])
    d["choch_status"], d["choch_age"] = _track_structure(d, config, is_choch=True)
    d["trend"] = _derive_trend(d)
    return d


def _track_structure(d: pd.DataFrame, config: StructureConfig, is_choch: bool = False) -> tuple[pd.Series, pd.Series]:
    """Sigue validez de BOS o CHOCH vela a vela.

    Invalidacion: el cierre CRUZA de nuevo el nivel roto (por cuerpo).
    EVENT-DRIVEN (Fase D): la estructura vive por EVENTO (cruce del nivel =
    invalidated). NO hay caducidad por tiempo/volatilidad ("aged"): nunca muere
    por un contador de velas ni por un umbral de volatilidad.
    """
    n = len(d)
    status = pd.Series(["none"] * n, index=d.index, dtype=object)
    age = pd.Series([0] * n, index=d.index, dtype=int)
    last_dir = 0
    last_level = float("nan")
    last_idx = -1
    active = False
    low = d["low"].to_numpy()
    high = d["high"].to_numpy()
    close = d["close"].to_numpy()
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
            if crossed:
                status.iloc[i], active = "invalidated", False
            # EVENT-DRIVEN (Fase D): la estructura vive por EVENTO (cruce del
            # nivel = invalidated). Se ELIMINO la caducidad por tiempo/volatilidad
            # ("aged"). Nunca muere por contador de velas.
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
