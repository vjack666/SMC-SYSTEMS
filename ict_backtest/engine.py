"""ict_backtest/engine.py — Motor event-driven (vela a vela) rescatado.

Rescata la simulacion de legacy/backtest/engine.py (_build_signals_from_context
+ _simulate_trade_with_stats), SIN ML ni dependencias del legacy. El bucle de
simulacion es barra por barra: por cada senal, avanza vela a vela hasta SL/TP/
limite de hold. Eso es lo que pediste: no procesar todo de golpe.

Para ICT no usamos ScalpingSignal del legacy; definimos ICTSignal propio con
SL/TP derivados de la regla (structural SL + TP en liquidez opuesta, RR>=1:2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class ICTSignal:
    symbol: str
    time: str
    direction: int          # +1 long, -1 short
    entry: float
    stop_loss: float
    take_profit: float
    model: str = ""         # "intradia" | "scalping"
    confidence: float = 0.0
    # Metadatos de indices de la secuencia canonica (R7 T3.1): permiten
    # trazabilidad de la senal sin alterar la simulacion (entry/SL/TP).
    sweep_at: int | None = None
    bos_at: int | None = None
    entry_at: int | None = None
    # Fase C (C2/C3): ZoneAuthority anotada (peso de confianza de zona).
    # Metadato de percepcion; NO altera entry/SL/TP ni el conteo de senales.
    zone_authority: Any = None


@dataclass
class ICTTrade:
    symbol: str
    entry_time: str
    exit_time: str
    direction: int
    entry: float
    exit: float
    pnl_r: float            # PnL en unidades de riesgo (RR)

def fill_entry_price(frame: pd.DataFrame, entry_at: int, fill_mode: str) -> float:
    """Precio de ENTRADA segun el modo de fill (R6.2 / G2).

    - 'next_open'  (default produccion): open de la vela SIGUIENTE a la senal.
      Es el fill realista: no puedes entrar al close de la vela que acaba de
      cerrar; la orden se ejecuta al abrir la siguiente.
    - 'signal_close' (theory/paper): close de la vela de senal. Sobre-estima el
      fill (la trampa del R4). Solo para modo teoria con --no-cost.

    Levanta ValueError si el modo es desconocido (contrato cerrado, no 'modo
    abierto' silencioso).
    """
    if fill_mode == "next_open":
        nxt = entry_at + 1
        if nxt >= len(frame):
            raise ValueError("fill next_open: no hay vela siguiente al entry_at")
        return float(frame.iloc[nxt]["open"])
    if fill_mode == "signal_close":
        return float(frame.iloc[entry_at]["close"])
    raise ValueError(f"fill_mode desconocido: {fill_mode!r} (use 'next_open'|'signal_close')")


def simulate_trade(frame: pd.DataFrame, signal: ICTSignal,
                  max_hold_bars: int, cost: dict | None = None) -> tuple[ICTTrade | None, dict[str, Any]]:
    """Simula UN trade vela a vela hasta SL/TP/hold_limit. (Rescatado legacy.)

    cost: dict opcional con costos de transaccion realistas:
      - spread_pips:   medio spread en pips (EURUSD~1.0, XAUUSD~2-3)
      - commission_pips: comision ida+vuelta en pips
      - slippage_pips: slippage promedio en pips (adverso al trade)
    Sin cost (cost=None) se conserva el comportamiento teorico anterior.
    """
    # tamaño de pip segun el rango de precios (FX 4 dec => 0.0001; XAU ~0.01)
    ref_price = float(signal.entry)
    pip = 0.01 if ref_price >= 10 else 0.0001

    spread = (cost or {}).get("spread_pips", 0.0) * pip
    comm = (cost or {}).get("commission_pips", 0.0) * pip
    slip = (cost or {}).get("slippage_pips", 0.0) * pip

    times = frame["time"].astype(str)
    matches = list(frame.index[times == signal.time])
    if len(matches) == 0:
        return None, {"exit_reason": "time_not_found", "mfe_r": 0.0, "mae_r": 0.0, "hold_bars": 0}

    idx = int(matches[0])
    sl, tp = signal.stop_loss, signal.take_profit
    # Entrada con slippage ADVERSO + medio spread (peor para el trader).
    dirn = 1 if signal.direction == 1 else -1
    entry_fill = signal.entry + dirn * (slip + spread / 2.0)
    # Risk respecto al entry REAL (antes del empuje de costo): si el SL queda
    # a <1 pip del entry, el trade es invalido (SL mal ubicado del motor:
    # evita R absurdos por division por risk ~0 en hold_limit lejano).
    risk_real = abs(signal.entry - sl)
    min_risk = 1.0 * pip
    if risk_real <= min_risk:
        return None, {"exit_reason": "invalid_risk", "mfe_r": 0.0, "mae_r": 0.0, "hold_bars": 0}
    risk = abs(entry_fill - sl)

    exit_idx, exit_price, exit_reason = idx, entry_fill, "hold_limit"
    mfe_r, mae_r = -1e9, 1e9

    for step in range(1, max_hold_bars + 1):
        j = idx + step
        if j >= len(frame):
            break
        row = frame.iloc[j]
        high, low = float(row["high"]), float(row["low"])

        if signal.direction == 1:
            step_mfe = (high - entry_fill) / risk
            step_mae = (low - entry_fill) / risk
            if low <= sl:
                exit_idx, exit_price, exit_reason = j, sl, "SL"
                mfe_r, mae_r = max(mfe_r, step_mfe), min(mae_r, step_mae)
                break
            if high >= tp:
                exit_idx, exit_price, exit_reason = j, tp, "TP"
                mfe_r, mae_r = max(mfe_r, step_mfe), min(mae_r, step_mae)
                break
        else:
            step_mfe = (entry_fill - low) / risk
            step_mae = (entry_fill - high) / risk
            if high >= sl:
                exit_idx, exit_price, exit_reason = j, sl, "SL"
                mfe_r, mae_r = max(mfe_r, step_mfe), min(mae_r, step_mae)
                break
            if low <= tp:
                exit_idx, exit_price, exit_reason = j, tp, "TP"
                mfe_r, mae_r = max(mfe_r, step_mfe), min(mae_r, step_mae)
                break
        exit_idx, exit_price = j, float(row["close"])
        mfe_r, mae_r = max(mfe_r, step_mfe), min(mae_r, step_mae)
    # Salida: pnl en R. El costo de comision se resta en PRECIO (no /risk),
    # para no inflar pnl_r cuando risk es pequeño (FIX R6.3).
    pnl_price = (exit_price - entry_fill) if signal.direction == 1 else (entry_fill - exit_price)
    pnl_r = (pnl_price - comm) / risk
    trade = ICTTrade(
        symbol=signal.symbol, entry_time=signal.time,
        exit_time=str(frame.iloc[exit_idx]["time"]), direction=signal.direction,
        entry=entry_fill, exit=exit_price, pnl_r=float(pnl_r),
    )
    hold_bars = max(0, int(exit_idx - idx))
    if mfe_r < -1e8:
        mfe_r = 0.0
    if mae_r > 1e8:
        mae_r = 0.0
    return trade, {"exit_reason": exit_reason, "mfe_r": float(mfe_r), "mae_r": float(mae_r), "hold_bars": hold_bars}


# ---- helpers ----

def _coerce_ts(value: Any) -> pd.Timestamp | None:
    if value is None:
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.tz_convert("UTC") if ts.tz else ts.tz_localize("UTC")


def _build_estructura(frames: dict[str, pd.DataFrame], i: int,
                      ltf: str) -> dict[str, dict]:
    """Arma el dict estructura[tf] = {trend, bos_dir, bos_status, sweep_up, sweep_down, ...}
    leyendo la fila i de cada TF (o la mas cercana en tiempo)."""
    est: dict[str, dict] = {}
    ltf_time = frames[ltf].iloc[i]["time"] if ltf in frames else None
    # Frecuencia de cada TF para exigir cierre de la barra al hacer join
    # cross-timeframe (evita look-ahead: ver AUDIT_LOOKAHEAD_HTF.md).
    TF_FREQ = {
        "M1": pd.Timedelta(minutes=1), "M5": pd.Timedelta(minutes=5),
        "M15": pd.Timedelta(minutes=15), "H1": pd.Timedelta(hours=1),
        "H4": pd.Timedelta(hours=4), "D1": pd.Timedelta(days=1),
    }
    for tf, df in frames.items():
        if tf == ltf or len(df) == 0:
            pass
        # indice por tiempo si es posible. El TF != LTF exige barra ya cerrada
        # (freq) para no leer indicadores de una barra HTF aun en formacion.
        freq = TF_FREQ.get(tf) if tf != ltf else None
        row = _row_at_time(df, ltf_time, freq=freq) if ltf_time is not None else (df.iloc[i] if i < len(df) else None)
        if row is None:
            est[tf] = {}
            continue
        est[tf] = {
            "trend": str(row.get("macro_direction", row.get("trend", "RANGING"))),
            "bos_dir": int(row.get("bos_direction", 0) or 0),
            "bos_status": str(row.get("bos_status", "")),
            "choch_status": str(row.get("choch_signal", row.get("choch_status", ""))),
            "sweep_up": bool(row.get("liquidity_sweep_up", row.get("sweep_up", False))),
            "sweep_down": bool(row.get("liquidity_sweep_down", row.get("sweep_down", False))),
            "fvg_state": str(row.get("fvg_state", row.get("fvg_bullish", "-"))),
            "ob_dir": str(row.get("ob_direction", row.get("ob_dir", "-"))),
        }
    if ltf in frames:
        est[ltf] = est.get(ltf, {})
    return est


from ict_backtest._util import row_at_time as _row_at_time  # noqa: E402


def _tp_liquidity(row: pd.Series, direction: int) -> float | None:
    """TP = pool de liquidez opuesto mas cercano (BSL si long / SSL si short).

    Usa bsl_price/ssl_price del detect_liquidity en el TF de ejecucion.
    """
    try:
        if direction == 1:
            bsl = float(row.get("bsl_price"))
            if pd.notna(bsl) and bsl > float(row["close"]):
                return bsl
        else:
            ssl = float(row.get("ssl_price"))
            if pd.notna(ssl) and ssl < float(row["close"]):
                return ssl
    except (TypeError, ValueError, KeyError):
        pass
    return None


def _coerce_ts(value: Any) -> pd.Timestamp | None:
    if value is None:
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.tz_convert("UTC") if ts.tz else ts.tz_localize("UTC")


# Maximo ancho del SL estructural en ATR. Si el sweep fue gigante y el SL
# queda mas alla de esto, el RR se rompe -> el motor SALTA el trade (P5).
STRUCT_SL_MAX_ATR = 6.0


def calc_structural_sl(row: pd.Series, direction: int, atr: float) -> float | None:
    """Stop-loss estructural ICT (libro 14_STOP_LOSS_ESTRUCTURAL).

    Ancla el SL al NIVEL donde la tesis del trade se cae, NO a la volatilidad.
    Prioridad (ICT mistake #4: usar buffer, no 1 pip):
      1. Mechas del sweep (sweep_low/sweep_high) +- buffer (la fuente madre).
      2. Si no hay sweep: swing roto (swing_low/swing_high de BOS/CHOCH).
      3. Si tampoco: None -> el motor NO opera (no degrada a ATR).
    El buffer evita que el spike post-sweep toque el stop por 1 pip.
    """
    from typing import cast
    buf = STRUCT_SL_BUFFER_ATR * atr

    def _lvl(col: str) -> float | None:
        v = row.get(col, np.nan)
        fv = cast(float, v)
        if pd.isna(fv) or fv <= 0:
            return None
        return float(fv)

    if direction == 1:  # long: SL bajo la mecha que barrio la SSL
        sweep = _lvl("sweep_low")
        if sweep is not None:
            return sweep - buf
        swing = _lvl("swing_low")
        if swing is not None:
            return swing - buf
    else:  # short: SL sobre la mecha que barrio la BSL
        sweep = _lvl("sweep_high")
        if sweep is not None:
            return sweep + buf
        swing = _lvl("swing_high")
        if swing is not None:
            return swing + buf
    return None


# Buffer del SL estructural en ATR (ICT mistake #4: stops 1 pip past the
# level get tagged on the spike). 0.3 ATR da aire sin romper el RR.
STRUCT_SL_BUFFER_ATR = 0.3


def _invalidation_level(estructura: dict, direction: int, exec_tf: str = "M15") -> float | None:
    """DEPRECADO: usado antes de calc_structural_sl. Conservado para
    referencia; el motor ya no lo llama (columna 'invalidation' nunca
    existio en el pipeline)."""
    m15 = estructura.get(exec_tf, {})
    inv = m15.get("invalidation") if isinstance(m15, dict) else None
    if inv is not None:
        try:
            v = float(inv)
            if np.isfinite(v) and v > 0:
                return v
        except (TypeError, ValueError):
            pass
    return None


if __name__ == "__main__":
    print("ict_backtest.engine cargado OK")
