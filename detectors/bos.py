from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BosConfig:
    swing_lookback: int = 5
    atr_period: int = 14
    followthrough_bars: int = 8
    liquidity_lookback: int = 20
    # NOTE (Fase D, event-driven): se ELIMINO max_age. El BOS vive por
    # EVENTO (cruce del nivel = invalidated), no por contador de velas.


def _compute_atr(frame: pd.DataFrame, period: int) -> pd.Series:
    high_low = frame["high"] - frame["low"]
    high_prev_close = (frame["high"] - frame["close"].shift(1)).abs()
    low_prev_close = (frame["low"] - frame["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _swing_points(frame: pd.DataFrame, lookback: int) -> tuple[pd.Series, pd.Series]:
    """Detecta swing high/low SIN look-ahead.

    CORREGIDO (hallazgo #2, 2026-07-12): el codigo original usaba ventana
    CENTRADA (center=True) + ffill() sin delay, lo que exponia el swing en la
    misma vela del pico -> look-ahead. Ahora usa ventana NO centrada (solo
    hacia atras) + descarte de empates planos, y desplaza `lookback` antes del
    ffill: el valor solo se expone desde la vela de confirmacion (igual que en
    ict_backtest/market_structure._swing_points). Esto elimina la fuga que
    inflaba el PF ~30% en Capa 2.
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
    label_series = labels.where(new_high | new_low, pd.NA).ffill().fillna("NONE")
    return label_series


def detect_bos(frame: pd.DataFrame, config: BosConfig | None = None) -> pd.DataFrame:
    if config is None:
        config = BosConfig()

    data = frame.copy()
    data["atr"] = _compute_atr(data, config.atr_period)
    data["swing_high"], data["swing_low"] = _swing_points(data, config.swing_lookback)
    data["swing_label"] = _label_swings(data["swing_high"], data["swing_low"])

    # Sweep canonico compartido (libro 05 §0 #3) via detectors.liquidity_context.
    # detect_bos delega en la UNICA fuente de verdad del repo.
    from detectors.liquidity_context import canonical_sweep

    swept = canonical_sweep(data, lookback=config.liquidity_lookback, min_periods=None)
    data["liquidity_sweep_down"] = swept["liquidity_sweep_down"]
    data["liquidity_sweep_up"] = swept["liquidity_sweep_up"]

    data["recent_sweep_down"] = (
        data["liquidity_sweep_down"].astype(int).rolling(config.followthrough_bars, min_periods=1).max().astype(bool)
    )
    data["recent_sweep_up"] = (
        data["liquidity_sweep_up"].astype(int).rolling(config.followthrough_bars, min_periods=1).max().astype(bool)
    )

    bullish_break = data["close"] > data["swing_high"].shift(1)
    bearish_break = data["close"] < data["swing_low"].shift(1)

    data["bos_direction"] = np.select(
        [bullish_break, bearish_break],
        [1, -1],
        default=0,
    )

    data["bos_level"] = np.where(
        data["bos_direction"] == 1,
        data["swing_high"].shift(1),
        np.where(data["bos_direction"] == -1, data["swing_low"].shift(1), np.nan),
    )

    # --- Item E: invalidacion por EVENTO (sin envejecimiento) ---
    data["bos_status"], data["bos_age"] = _track_bos_validity(data)

    return data


def _track_bos_validity(data: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    n = len(data)
    status = pd.Series(["none"] * n, index=data.index, dtype=object)
    age = pd.Series([0] * n, index=data.index, dtype=int)
    last_dir = 0
    last_level = float("nan")
    last_idx = -1
    active = False
    low = data["low"].to_numpy()
    high = data["high"].to_numpy()
    bos_dir = data["bos_direction"].to_numpy()
    bos_lvl = data["bos_level"].to_numpy()
    for i in range(1, n):
        d = int(bos_dir[i])
        lvl = bos_lvl[i]
        if d != 0 and pd.notna(lvl):
            last_dir, last_level, last_idx, active = d, float(lvl), i, True
        if active:
            age.iloc[i] = i - last_idx
            crossed = (
                (last_dir == 1 and low[i] < last_level)   # BOS alcista roto por abajo
                or (last_dir == -1 and high[i] > last_level)  # BOS bajista roto por arriba
            )
            if crossed:
                status.iloc[i], active = "invalidated", False
            else:
                # EVENT-DRIVEN: vive por EVENTO (cruce), no por tiempo.
                # Sin aged: nunca muere por contador de velas.
                status.iloc[i] = "active"
    return status, age
