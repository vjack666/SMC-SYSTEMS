"""ict_backtest/data_feed.py — Conector datos -> features -> motor.

Carga OHLC (parquet en data/raw), corre los detectores ICT del repo
(detect_bos, detect_trend, detect_fvg, detect_order_blocks) y produce
las columnas que el motor (engine._build_estructura) espera:

  trend/macro_direction, bos_direction, bos_status,
  liquidity_sweep_up/down, fvg_state, ob_direction, atr, time, ohlc

Todo se calcula por TF (D1, H4, ...). NO usa reloj de PC: la killzone
la deriva el motor del timestamp de cada vela.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from detectors import detect_bos, detect_choch, detect_displacement, detect_fvg, detect_liquidity, detect_order_blocks
from detectors.trend import detect_trend

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "raw"


def _fvg_state(row: pd.Series) -> str:
    if bool(row.get("fvg_bullish", False)):
        return "bullish"
    if bool(row.get("fvg_bearish", False)):
        return "bearish"
    return "-"


def _ob_dir(row: pd.Series) -> str:
    if bool(row.get("ob_bullish", False)):
        return "bullish"
    if bool(row.get("ob_bearish", False)):
        return "bearish"
    return "-"


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Corre detectores ICT sobre un frame OHLC y devuelve columnas del contrato."""
    d = df.copy().reset_index(drop=True)
    d = detect_bos(d)          # atr, swing_label, liquidity_sweep_*, bos_direction, bos_status
    t = detect_trend(d)        # trend, trend_int
    d["trend"] = t["trend"].values
    d["macro_direction"] = t["trend"].values
    f = detect_fvg(d)          # fvg_bullish, fvg_bearish, fvg_mid, ...
    d = f                      # PRESERVA las booleanas (antes se descartaban)
    d["fvg_state"] = d.apply(_fvg_state, axis=1).values
    o = detect_order_blocks(d)  # ob_bullish, ob_bearish, ob_top/bottom, ...
    d = o                      # PRESERVA las booleanas (antes se descartaban)
    d["ob_direction"] = d.apply(_ob_dir, axis=1).values
    # --- Fase B1 (SPEC §4/§5): cruce FVG+OB y etiquetas de tipo/tier ---
    # BPR (T1): FVG y OB caen en la MISMA zona de precio (tolerancia = 0.3 ATR).
    # BREAKER: OB cuya estructura adyacente se rompió (bos_dir opuesto a ob_direction).
    # MITIGATION_BLOCK (T3): OB que mitiga un FVG previo (fvg_mid entre ob_top/ob_bottom).
    _atr = d["atr"] if "atr" in d.columns else pd.Series(0.0, index=d.index)
    tol = 0.3 * _atr.clip(lower=1e-9)
    fvg_b = d["fvg_bullish"].fillna(False).values
    fvg_be = d["fvg_bearish"].fillna(False).values
    # FVG activo mas reciente (persiste varias barras hasta llenarse): ffill del mid.
    fvg_mid_active = d["fvg_mid"].where(fvg_b | fvg_be).ffill()
    fvg_mid = fvg_mid_active.fillna(np.nan).values
    ob_up = d["ob_bullish"].fillna(False).values
    ob_dn = d["ob_bearish"].fillna(False).values
    ob_top = d["ob_top"].fillna(np.nan).values
    ob_bot = d["ob_bottom"].fillna(np.nan).values
    ob_dir = d["ob_direction"].values  # +1 bull, -1 bear
    bos_dir = d.get("bos_dir", pd.Series(0, index=d.index)).fillna(0).values
    for i in range(len(d)):
        if ob_up[i] or ob_dn[i]:
            t = ob_top[i]
            b = ob_bot[i]
            if pd.isna(t) or pd.isna(b):
                continue
            in_ob = (not pd.isna(fvg_mid[i])) and (b <= fvg_mid[i] <= t)
            near_ob = (not pd.isna(fvg_mid[i])) and (
                abs(fvg_mid[i] - (t + b) / 2.0) <= tol[i])
            # BPR (T1, maxima autoridad libro 21 §2): FVG y OB comparten zona.
            # Tiene prioridad sobre MITIGATION/BREAKER.
            if in_ob or near_ob:
                d.at[i, "pd_tier"] = "T1"
            # BREAKER: estructura rota en dirección opuesta al OB
            if (ob_dir[i] == 1 and bos_dir[i] == -1) or (ob_dir[i] == -1 and bos_dir[i] == 1):
                d.at[i, "pd_type"] = "BREAKER"
                if d.at[i, "pd_tier"] == "T2":
                    d.at[i, "pd_tier"] = "T1"
            # MITIGATION_BLOCK (T3): OB tapa un FVG previo que NO es su zona
            # exacta (si fuera su zona exacta ya es BPR/T1 arriba).
            if (not in_ob) and near_ob and d.at[i, "pd_type"] != "BREAKER":
                d.at[i, "pd_type"] = "MITIGATION_BLOCK"
                d.at[i, "pd_tier"] = "T3"
    c = detect_choch(d)          # choch_signal, choch_status, choch_age
    d["choch_signal"] = c["choch_signal"].values
    # Mapear choch_signal -> choch_dir (int) que el motor de secuencia espera.
    # CHOCH_BULLISH = +1 (giro alcista), CHOCH_BEARISH = -1, NONE = 0.
    d["choch_dir"] = c["choch_signal"].replace(
        {"CHOCH_BULLISH": 1, "CHOCH_BEARISH": -1, "NONE": 0}
    ).fillna(0).astype(int).values
    # Mapear bos_direction -> bos_dir (int) que _has_bos espera (BOS clasico).
    d["bos_dir"] = d["bos_direction"].replace(
        {"BULLISH": 1, "BEARISH": -1}
    ).fillna(0).astype(int).values
    disp = detect_displacement(d)  # displacement_bullish/bearish, magnitude
    d["displacement_bullish"] = disp["displacement_bullish"].values
    d["displacement_bearish"] = disp["displacement_bearish"].values
    d["displacement_mag"] = disp["displacement_magnitude"].values
    liq = detect_liquidity(d)  # bsl_price, ssl_price (pools de liquidez)
    d["bsl_price"] = liq["bsl_price"].values
    d["ssl_price"] = liq["ssl_price"].values
    # Niveles de la MECHA del sweep (libro 14_STOP_LOSS_ESTRUCTURAL).
    # canonical_sweep ya existe en detectors/liquidity_context.py; exponemos
    # el low/high de la vela que barrio la liquidez, con .shift(1) -> sin
    # look-ahead (la vela ya cerro). El motor los usa como ancla del SL
    # estructural en lugar del ATR.
    from detectors.liquidity_context import canonical_sweep, DEFAULT_SWEEP_LOOKBACK
    from typing import cast
    swept = canonical_sweep(d, lookback=DEFAULT_SWEEP_LOOKBACK)
    d["sweep_low"] = _sweep_level(cast(pd.Series, swept["liquidity_sweep_down"]),
                                  cast(pd.Series, d["low"]))
    d["sweep_high"] = _sweep_level(cast(pd.Series, swept["liquidity_sweep_up"]),
                                   cast(pd.Series, d["high"]))
    return d


def _sweep_level(flag: pd.Series, price: pd.Series) -> pd.Series:
    """Devuelve el nivel (low/high) de la vela que barrio la liquidez.

    flag: booleano de sweep (ya con logica canonica, sin look-ahead en si
    mismo, pero la señal vive EN la vela del sweep). Aplicamos .shift(1)
    para que el nivel que el motor lea en la vela de entrada sea el del
    sweep YA CERRADO (no la vela en formacion). Donde no hubo sweep -> NaN.
    """
    return price.where(flag).shift(1)


def load_tf(symbol: str, timeframe: str, data_dir: Path | str = DATA_DIR) -> pd.DataFrame:
    """Carga un parquet OHLC y le agrega las features ICT."""
    path = Path(data_dir) / f"{symbol}_{timeframe}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"No existe {path}")
    df = pd.read_parquet(path)
    return build_features(df)


def load_frames(symbol: str, timeframes: tuple[str, ...],
                data_dir: Path | str = DATA_DIR) -> dict[str, pd.DataFrame]:
    """Carga varios TF con features. Devuelve {tf: df}."""
    return {tf: load_tf(symbol, tf, data_dir) for tf in timeframes}


def bias_from_trend(frames: dict[str, pd.DataFrame], htf: str) -> str:
    """Sesgo global = ultima tendencia del HTF (para el backtest completo).

    NOTA: esto es un sesgo estatico de fin de serie; para backtest honesto el
    motor lee la tendencia POR VELA via _build_estructura. Este helper solo da
    un default. El sesgo real por vela sale de la columna 'trend' de cada TF.
    """
    df = frames.get(htf)
    if df is None or len(df) == 0 or "trend" not in df.columns:
        return "NEUTRAL"
    return str(df["trend"].iloc[-1])


def build_objects(frames: dict[str, pd.DataFrame],
                 symbol: str = "") -> list:
    """Produce MarketObjects desde {tf: df} sellando la capa (origen + rol).

    NO borra columnas: build_features sigue devolviendo el df con las columnas
    que leen sequence/rules/engine/pipeline/ML/UI. Solo AGREGA la vista de
    objetos como fuente canonica, via translation.df_to_objects.

    Garantiza NO-ROMPER: los consumidores existentes siguen recibiendo las
    columnas de siempre (ver tests/test_compat_consumidores.py).
    """
    feature_frames: dict[str, pd.DataFrame] = {}
    for tf, df in frames.items():
        # Si ya trae features (columna bos_direction), no las recalcula.
        if "bos_direction" in df.columns:
            feature_frames[tf] = df
        else:
            feature_frames[tf] = build_features(df.copy())
    from ict_backtest.translation import df_to_objects
    return df_to_objects(feature_frames, symbol=symbol)


if __name__ == "__main__":
    fr = load_frames("XAUUSD", ("H4",))
    h4 = fr["H4"]
    print("H4 filas:", len(h4))
    print("cols clave:", [c for c in ("trend", "bos_direction", "bos_status",
          "liquidity_sweep_up", "liquidity_sweep_down", "fvg_state",
          "ob_direction", "atr") if c in h4.columns])
    print(h4[["time", "trend", "bos_direction", "bos_status", "fvg_state", "ob_direction"]].tail(3).to_string())
