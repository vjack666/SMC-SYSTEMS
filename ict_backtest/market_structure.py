"""ict_backtest/market_structure.py — Reglas canonicas BOS / CHOCH (ICT/SMC).

Documenta y APLICA cuando un BOS o CHOCH se considera activo/valido/
invalidado, segun la teoria ICT (innercircletrader) y SMC (dailypriceaction):

  BOS (Break of Structure):
    - Alcista: el close (cuerpo) supera el ULTIMO swing high.
    - Bajista: el close (cuerpo) perfora el ULTIMO swing low.
    - Continuacion: ruptura EN LA MISMA direccion del bias de estructura.
    - ACTIVO desde el break hasta que el precio CRUZA de nuevo el nivel roto
      (invalidacion). EVENT-DRIVEN: no hay caducidad por tiempo/volatilidad.

  CHOCH (Change of Character):
    - Primera ruptura EN CONTRA del bias de estructura actual.
    - Alcista: bias era bajista y el close rompe el swing high de esa estructura.
    - Bajista: bias era alcista y el close rompe el swing low de esa estructura.
    - Tras un CHOCH el bias se invierte; las siguientes rupturas a favor son BOS.
    - REGLA CLAVE: BOS y CHOCH son mutuamente excluyentes en la misma vela.
      Un break es O BOS O CHOCH, nunca ambos.

Confirmacion ORIENTADA A LA REALIDAD DEL MERCADO (no velas fijas):
  - CONFIRMACION: la ruptura se marca solo con el CUERPO (close), nunca la mecha
    (wick = liquidity sweep, no estructura — TradingStrategyGuides 2026). Para
    reducir fakeouts (Turtle Soups) se exige `confirm_bars` cierres CONSECUTIVOS
    rompiendo el nivel (LuxAlgo Market Structure ICT, feb 2026: "two consecutive
    candle bodies close beyond a previous swing level").
  - CADUCIDAD: EVENT-DRIVEN (Fase D). La estructura vive hasta el cruce del
    nivel (invalidated). NO hay "aged" por tiempo ni por volatilidad.

El detector es EVENT-DRIVEN y SECUENCIAL: marca estado vela a vela (memoria),
que es lo que necesita el motor Capa 2 (event-sequence).

Fuentes (verificadas 2026-07-12):
  - LuxAlgo — Market Structure & ICT Concepts: confirmacion por 2 cuerpos consecutivos.
  - TradingStrategyGuides — wick alone does not confirm; body close beyond swing.
  - Strike.money — BOS: estructura -> break -> confirmation -> continuation.
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
    # tiempo/volatilidad (max_age_atr / max_age_bars / "aged").
    # NOTE (migracion ATR -> rango, Fase 1): se ELIMINO atr_period.


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
      bos_dir (1/-1/0), bos_level, bos_status, bos_age
      choch_dir (1/-1/0), choch_level, choch_status, choch_age
      structure_label ("BOS" | "CHOCH" | "") — etiqueta mutua excluyente del onset
      trend (BULLISH/BEARISH/RANGING) derivado de HH/HL vs LH/LL

    Regla de etiquetado (ICT):
      - Primera ruptura en CONTRA del bias de estructura → CHOCH
      - Ruptura a FAVOR del bias (o sin bias previo) → BOS
      - Tras CHOCH el bias se invierte; el siguiente break a favor es BOS
    """
    if config is None:
        config = StructureConfig()
    d = frame.copy().reset_index(drop=True)
    sh, sl = _swing_points(d, config.swing_lookback)
    d["swing_high"], d["swing_low"] = sh, sl
    d["swing_label"] = _label_swings(sh, sl)

    n = len(d)
    close = d["close"].to_numpy(dtype=float)
    sh_arr = sh.to_numpy(dtype=float)
    sl_arr = sl.to_numpy(dtype=float)

    # Rupturas confirmadas por cuerpo (sin clasificar aun).
    bull_break = d["close"] > sh.shift(1)
    bear_break = d["close"] < sl.shift(1)
    bull_conf = _consecutive_break(bull_break, config.confirm_bars).to_numpy()
    bear_conf = _consecutive_break(bear_break, config.confirm_bars).to_numpy()

    bos_dir = np.zeros(n, dtype=int)
    choch_dir = np.zeros(n, dtype=int)
    bos_level = np.full(n, np.nan)
    choch_level = np.full(n, np.nan)
    structure_label = np.array([""] * n, dtype=object)

    # bias de estructura: 0=ninguno, 1=alcista, -1=bajista
    bias = 0
    # nivel del ultimo swing ya etiquetado (evita re-disparar el mismo break)
    last_bull_level = float("nan")
    last_bear_level = float("nan")

    for i in range(1, n):
        prev_sh = sh_arr[i - 1] if i > 0 else np.nan
        prev_sl = sl_arr[i - 1] if i > 0 else np.nan

        # --- ruptura alcista confirmada ---
        if bull_conf[i] and np.isfinite(prev_sh):
            # solo onset: no re-etiquetar el mismo nivel ya roto
            if not (np.isfinite(last_bull_level) and abs(prev_sh - last_bull_level) < 1e-12):
                level = float(prev_sh)
                if bias == -1:
                    # primera ruptura EN CONTRA → CHOCH alcista
                    choch_dir[i] = 1
                    choch_level[i] = level
                    structure_label[i] = "CHOCH"
                else:
                    # a favor o sin bias → BOS alcista
                    bos_dir[i] = 1
                    bos_level[i] = level
                    structure_label[i] = "BOS"
                bias = 1
                last_bull_level = level
                # al cambiar de lado, permitir de nuevo el otro lado
                last_bear_level = float("nan")

        # --- ruptura bajista confirmada ---
        if bear_conf[i] and np.isfinite(prev_sl):
            if not (np.isfinite(last_bear_level) and abs(prev_sl - last_bear_level) < 1e-12):
                level = float(prev_sl)
                if bias == 1:
                    # primera ruptura EN CONTRA → CHOCH bajista
                    choch_dir[i] = -1
                    choch_level[i] = level
                    structure_label[i] = "CHOCH"
                else:
                    # a favor o sin bias → BOS bajista
                    bos_dir[i] = -1
                    bos_level[i] = level
                    structure_label[i] = "BOS"
                bias = -1
                last_bear_level = level
                last_bull_level = float("nan")

    d["bos_dir"] = bos_dir
    d["choch_dir"] = choch_dir
    d["bos_level"] = bos_level
    d["choch_level"] = choch_level
    d["structure_label"] = structure_label

    d["bos_status"], d["bos_age"] = _track_structure(d, config, is_choch=False)
    d["choch_status"], d["choch_age"] = _track_structure(d, config, is_choch=True)
    d["trend"] = _derive_trend(d)
    return d


def _track_structure(d: pd.DataFrame, config: StructureConfig, is_choch: bool = False) -> tuple[pd.Series, pd.Series]:
    """Sigue validez de BOS o CHOCH vela a vela.

    Invalidacion: el cierre CRUZA de nuevo el nivel roto (por cuerpo).
    EVENT-DRIVEN (Fase D): la estructura vive por EVENTO (cruce del nivel =
    invalidated). NO hay caducidad por tiempo/volatilidad ("aged").
    """
    n = len(d)
    status = pd.Series(["none"] * n, index=d.index, dtype=object)
    age = pd.Series([0] * n, index=d.index, dtype=int)
    last_dir = 0
    last_level = float("nan")
    last_idx = -1
    active = False
    close = d["close"].to_numpy()
    dir_col = d["choch_dir"].to_numpy() if is_choch else d["bos_dir"].to_numpy()
    level_col = (
        d["choch_level"].to_numpy() if is_choch and "choch_level" in d.columns
        else d["bos_level"].to_numpy() if "bos_level" in d.columns
        else np.full(n, np.nan)
    )

    for i in range(1, n):
        dr = int(dir_col[i])
        if dr != 0:
            last_dir, last_idx, active = dr, i, True
            lvl = level_col[i]
            last_level = float(lvl) if pd.notna(lvl) else last_level
        if active:
            age.iloc[i] = i - last_idx
            crossed = ((last_dir == 1 and close[i] < last_level) or
                       (last_dir == -1 and close[i] > last_level))
            if crossed:
                status.iloc[i], active = "invalidated", False
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
    bos_onsets = int((ms["bos_dir"] != 0).sum())
    choch_onsets = int((ms["choch_dir"] != 0).sum())
    print("BOS onsets:", bos_onsets)
    print("CHOCH onsets:", choch_onsets)
    print("structure_label:", ms["structure_label"].value_counts().to_dict())
    print("BOS activos (bars):", int((ms["bos_status"] == "active").sum()))
    print("CHOCH activos (bars):", int((ms["choch_status"] == "active").sum()))
    print("trend counts:", ms["trend"].value_counts().to_dict())
