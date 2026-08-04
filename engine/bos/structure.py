"""engine/bos/structure.py — Market Structure BOS / CHOCH (CAPA 2 del motor).

Contrato (docs/ict/02_MSS_CHOCH.md §0 — MSS, CHoCH y BOS, OBLIGATORIO):
  ENT: velas cerradas de un TF (high/low/open/close), sin look-ahead.
  SAL: por vela — swings etiquetados, bos_dir/bos_level/bos_status,
       choch_dir/choch_status, trend derivado.
  BOS  = ruptura de swing A FAVOR de la tendencia, validada por cierre de
         cuerpo (close), no por mecha.
  CHoCH = ruptura del swing que produjo el ULTIMO BOS, en direccion OPUESTA
         a ese BOS (aviso de giro; no es una copia de BOS).
  MSS  = CHoCH + desplazamiento + (ideal) BOS de confirmacion en la nueva
         direccion. Secuencia canonica: BOS^ -> CHoCHv -> BOSv.
  PRE: velas cerradas (sin look-ahead): swing expuesto solo tras
       `swing_lookback` velas de confirmacion (ventana NO centrada).
  POST: estructura disponible para POI/exec (filtro HTF del setup).
  CRIT: un BOS/CHoCH es valido SOLO con `confirm_bars` cierres consecutivos
        rompiendo el nivel (LuxAlgo: 2 cuerpos; filtra fakeouts/Turtle Soups).
  CASOS LIMITE: rango -> bos_dir=0, trend=RANGING; sin swings suficientes
        -> estados "none".
  AMBIG: swing_lookback / confirm_bars son decisiones de ingenieria
        (defaults del canon: 5 / 2).

Reglas de implementacion:
  - Sin look-ahead: swings con ventana NO centrada + exposicion diferida
    (shift(lookback) + ffill), mismo patron que el canon y que la capa 1.
  - Confirmacion por cuerpo: close (nunca mecha) + `confirm_bars` cierres
    consecutivos.
  - Estado EVENT-DRIVEN: un BOS/CHoCH vive hasta que el close cruza de vuelta
    el nivel roto (invalidated). No caduca por tiempo ni volatilidad.
  - Sin indicadores: ni ATR ni medias moviles (volatilidad = rango high-low).
  - Primitivos de swings importados de `engine.bias.narrative` (misma logica
    en todo el motor, sin duplicar).
  - API pura, sin estado mutable global.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from engine.bias.narrative import _label_swings, _swing_points

BULLISH = "BULLISH"
BEARISH = "BEARISH"
RANGING = "RANGING"

_STRUCTURE_STATUS = ("none", "active", "invalidated")

# M6 — Causas de descarte emitidas por el motor.
BOS_DISCARD_REASONS = ("NO_HIT_IN_K", "INVALIDATED", "UNRESOLVED")
CHOCH_DISCARD_REASONS = ("NO_CONFIRMATION", "INVALIDATED", "UNRESOLVED")


@dataclass(frozen=True)
class StructureConfig:
    """Opciones de deteccion de estructura (defaults del canon)."""

    swing_lookback: int = 5
    followthrough_bars: int = 8
    # Cuantos cierres CONSECUTIVOS deben romper el nivel para confirmar.
    # 1 = vela unica; 2 = filtra fakeouts (LuxAlgo Market Structure, feb 2026).
    confirm_bars: int = 2
    k: int = 5


@dataclass(frozen=True)
class MarketStructure:
    """Resultado de la deteccion: frame anotado + vista de estado.

    `frame` contiene las columnas:
      swing_high, swing_low, swing_label
      bos_dir (1/-1/0), bos_level, bos_status (active/invalidated/none),
      bos_discard_reason (INVALIDATED/UNRESOLVED)
      choch_dir (1/-1/0), choch_status (active/invalidated/none),
      choch_discard_reason (INVALIDATED/UNRESOLVED)
      mss_dir (1/-1/0)   # secuencia canonica BOS -> CHOCH -> BOS
      trend (BULLISH/BEARISH/RANGING)
    """

    frame: pd.DataFrame

    @property
    def last_bos_dir(self) -> int:
        """Direccion del ultimo BOS emitido (1 alcista, -1 bajista, 0 sin BOS)."""
        bos = self.frame["bos_dir"]
        nonzero = bos[bos != 0]
        return int(nonzero.iloc[-1]) if len(nonzero) else 0

    @property
    def last_bos_level(self) -> float:
        """Nivel del ultimo BOS emitido (NaN si no hubo)."""
        levels = self.frame["bos_level"]
        valid = levels[~levels.isna()]
        return float(valid.iloc[-1]) if len(valid) else float("nan")

    @property
    def last_choch_dir(self) -> int:
        """Direccion del ultimo CHoCH emitido (1/-1/0)."""
        choch = self.frame["choch_dir"]
        nonzero = choch[choch != 0]
        return int(nonzero.iloc[-1]) if len(nonzero) else 0

    @property
    def counts(self) -> dict[str, int]:
        """Conteos de estado por vela (diagnostico rapido)."""
        return {
            "bos_active": int((self.frame["bos_status"] == "active").sum()),
            "bos_invalidated": int((self.frame["bos_status"] == "invalidated").sum()),
            "choch_active": int((self.frame["choch_status"] == "active").sum()),
            "trend": self.frame["trend"].value_counts().to_dict(),
        }


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


def _track_structure(
    d: pd.DataFrame,
    config: StructureConfig,
    is_choch: bool = False,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Sigue validez de BOS o CHoCH vela a vela (estado event-driven).

    Invalidacion: el cierre CRUZA de vuelta el nivel roto (por cuerpo).
    No hay caducidad por tiempo ni volatilidad: la estructura vive por
    EVENTO (cruce del nivel = invalidated), nunca muere por contador de velas.

    Returns:
        status: Serie con estados por vela.
        age: Edad del evento activo en velas.
        discard_reason: Causa de descarte cuando aplica.
    """
    n = len(d)
    status = pd.Series(["none"] * n, index=d.index, dtype=object)
    age = pd.Series([0] * n, index=d.index, dtype=int)
    discard_reason = pd.Series([pd.NA] * n, index=d.index, dtype=object)
    last_dir = 0
    last_level = float("nan")
    last_idx = -1
    active = False
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
            if is_choch:
                last_level = float(sh[i]) if dr == 1 else float(slv[i])
            else:
                last_level = float(bos_level[i]) if pd.notna(bos_level[i]) else last_level
        if active:
            age.iloc[i] = i - last_idx
            crossed = (last_dir == 1 and close[i] < last_level) or (
                last_dir == -1 and close[i] > last_level
            )
            if crossed:
                status.iloc[i] = "invalidated"
                active = False
                discard_reason.iloc[last_idx] = "INVALIDATED"
            else:
                status.iloc[i] = "active"
        last_dir_col[i] = last_dir
        last_level_col[i] = last_level

    if not is_choch:
        d["_last_bos_dir"] = last_dir_col
        d["_last_bos_level"] = last_level_col
    return status, age, discard_reason


def _derive_trend(d: pd.DataFrame) -> pd.Series:
    """Tendencia por pendiente de swings: HH/HL -> BULLISH; LH/LL -> BEARISH; sino RANGING."""
    lab = d["swing_label"].fillna("NONE")
    bull = (lab == "HH") | (lab == "HL")
    bear = (lab == "LH") | (lab == "LL")
    return np.select([bull, bear], [BULLISH, BEARISH], default=RANGING)


def _label_bos_discard(
    d: pd.DataFrame,
    config: StructureConfig,
    bos_discard: pd.Series,
) -> pd.Series:
    """Etiqueta causa de descarte para BOS sin hit en `k` velas.

    Causas:
      NO_HIT_IN_K: evento emitido pero el nivel no fue roto en `k` velas.
      INVALIDATED: evento activo invalidado por cruce del nivel.
      UNRESOLVED: evento al final del dataset sin datos suficientes.
    """
    n = len(d)
    reasons = pd.Series([pd.NA] * n, index=d.index, dtype=object)
    highs = d["high"].to_numpy()
    lows = d["low"].to_numpy()
    bos_levels = d["bos_level"].to_numpy()
    bos_status = d["bos_status"].to_numpy()

    # Marcar invalidaciones ya capturadas en tracking.
    invalidated_mask = bos_status == "invalidated"
    reasons[bos_discard == "INVALIDATED"] = "INVALIDATED"

    # Eventos con estado activo pero sin validación posterior.
    active_mask = bos_status == "active"
    for i in np.where(active_mask)[0]:
        if pd.notna(reasons.iloc[i]):
            continue
        end = min(i + config.k, n)
        future_highs = highs[i + 1 : end] if i + 1 < n else np.array([], dtype=float)
        future_lows = lows[i + 1 : end] if i + 1 < n else np.array([], dtype=float)
        level = float(bos_levels[i])
        direction = int(d["bos_dir"].iat[i])
        hit = False
        if direction == 1 and len(future_highs) > 0:
            hit = bool(np.nanmax(future_highs) > level)
        elif direction == -1 and len(future_lows) > 0:
            hit = bool(np.nanmin(future_lows) < level)
        if not hit:
            reasons.iloc[i] = "NO_HIT_IN_K" if end < n else "UNRESOLVED"
    return reasons


def _label_choch_discard(
    d: pd.DataFrame,
    config: StructureConfig,
    choch_discard: pd.Series,
) -> pd.Series:
    """Etiqueta causa de descarte para CHOCH.

    Causas:
      NO_CONFIRMATION: evento emitido pero no hubo BOS confirmado en `confirm_bars`.
      INVALIDATED: evento activo invalidado por cruce del nivel.
      UNRESOLVED: evento al final del dataset sin datos suficientes.
    """
    n = len(d)
    reasons = pd.Series([pd.NA] * n, index=d.index, dtype=object)
    choch_status = d["choch_status"].to_numpy()

    reasons[choch_discard == "INVALIDATED"] = "INVALIDATED"
    active_mask = choch_status == "active"
    for i in np.where(active_mask)[0]:
        end = min(i + config.confirm_bars + 1, n)
        if end < n:
            reasons.iloc[i] = "NO_CONFIRMATION"
        else:
            reasons.iloc[i] = "UNRESOLVED"
    return reasons


def detect_market_structure(
    frame: pd.DataFrame,
    config: StructureConfig | None = None,
) -> MarketStructure:
    """Aplica las reglas canonicas BOS/CHoCH con memoria de estado (secuencial).

    Args:
        frame: DataFrame con columnas `high`/`low`/`open`/`close`, SOLO velas
               cerradas (sin look-ahead).
        config: opciones de deteccion (defaults del canon).

    Returns:
        MarketStructure con el frame anotado (swings, bos, choch, trend) y
        vista de estado.
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
    d["bos_level"] = np.where(
        d["bos_dir"] == 1,
        sh.shift(1),
        np.where(d["bos_dir"] == -1, sl.shift(1), np.nan),
    )

    d["bos_status"], _, bos_discard = _track_structure(d, config, is_choch=False)
    # CHoCH real: rompe el swing que produjo el ULTIMO BOS, en direccion
    # OPUESTA a ese BOS. No es una copia de BOS.
    last_bos_dir = d["_last_bos_dir"].to_numpy()
    last_bos_level = d["_last_bos_level"].to_numpy()
    up_choch = (d["close"].to_numpy() > last_bos_level) & (last_bos_dir == -1)
    dn_choch = (d["close"].to_numpy() < last_bos_level) & (last_bos_dir == 1)
    choch_raw = np.select([up_choch, dn_choch], [1, -1], default=0)
    # CHoCH tambien requiere confirmacion por cuerpo consecutivo.
    d["choch_dir"] = _consecutive_break(
        pd.Series(choch_raw != 0, index=d.index), config.confirm_bars
    ).astype(int) * choch_raw
    d = d.drop(columns=["_last_bos_dir", "_last_bos_level"])
    d["choch_status"], _, choch_discard = _track_structure(d, config, is_choch=True)
    d["trend"] = _derive_trend(d)

    n = len(d)
    # MSS = secuencia canonica BOS -> CHOCH -> BOS.
    # Se marca solo cuando aparece un BOS en direccion opuesta al ultimo CHOCH,
    # sin depender del estado activo/invalidado del CHOCH (el CHOCH es un
    # evento puntual, no un estado persistente).
    last_choch_idx = -1
    last_choch_dir = 0
    mss_dir = np.zeros(n, dtype=int)
    for i in range(n):
        if d["choch_dir"].iat[i] != 0:
            last_choch_idx = i
            last_choch_dir = d["choch_dir"].iat[i]
        if (
            d["bos_dir"].iat[i] != 0
            and last_choch_idx != -1
            and d["bos_dir"].iat[i] == -last_choch_dir
        ):
            mss_dir[i] = d["bos_dir"].iat[i]
    d["mss_dir"] = mss_dir

    # M6 — Etiquetado de descarte desde el motor.
    d["bos_discard_reason"] = _label_bos_discard(d, config, bos_discard)
    d["choch_discard_reason"] = _label_choch_discard(d, config, choch_discard)

    return MarketStructure(frame=d)
