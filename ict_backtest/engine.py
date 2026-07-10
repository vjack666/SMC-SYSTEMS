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


@dataclass
class ICTTrade:
    symbol: str
    entry_time: str
    exit_time: str
    direction: int
    entry: float
    exit: float
    pnl_r: float            # PnL en unidades de riesgo (RR)


def build_signals_from_frames(
    symbol: str,
    frames: dict[str, pd.DataFrame],
    bias_by_tf: dict[str, str],
    votes: dict | None = None,
    model: str = "intradia",
    min_confidence: float = 0.0,
    htf: str = "H4",
    ltf: str = "M15",
    counter_trend: bool = False,
    tp_mode: str = "fixed2r",
    require_displacement: bool = False,
) -> list[ICTSignal]:
    """Construye senales ICT evaluando el mini-check del dashboard por vela.

    frames: {"D1": df, "H4": df, "M15": df, ...} alineados por indice/tiempo.
    Recorre el LTF barra por barra (event-driven). En cada vela, arma el dict
    `estructura` por TF y llama a ict_backtest.rules.evaluate. Si el check pasa
    (ready) y la direccion es LONG/SHORT, genera ICTSignal con SL/TP.

    counter_trend: setup opera contra la marea del HTF.
    tp_mode: "fixed2r" (entry +/- 2R) | "liquidity" (BSL/SSL mas cercano).
    require_displacement: exige vela de displacement fuerte en el exec TF.

    SL  = nivel de invalidacion (structural) o ATR si no hay.
    TP  = entry +/- 2*ATR (RR 1:2) o liquidez opuesta (tp_mode).
    """
    from ict_backtest.rules import evaluate

    ltf_df = frames.get(ltf)
    if ltf_df is None or len(ltf_df) == 0:
        return []

    atr_col = "atr" if "atr" in ltf_df.columns else None
    results: list[ICTSignal] = []

    for i in range(len(ltf_df)):
        row = ltf_df.iloc[i]
        ts = _coerce_ts(row.get("time"))
        estructura = _build_estructura(frames, i, ltf)
        # Sesgo POR VELA desde la tendencia del HTF (backtest honesto, sin mirar futuro).
        htf_trend = str(estructura.get(htf, {}).get("trend", "NEUTRAL"))
        bias = htf_trend if htf_trend in ("BULLISH", "BEARISH") else "NEUTRAL"
        if bias_by_tf.get(htf) in ("BULLISH", "BEARISH") and htf not in frames:
            bias = bias_by_tf[htf]

        verdict = evaluate(model, estructura, bias, votes, ts, exec_tf=ltf,
                           htf=htf, counter_trend=counter_trend)
        if not verdict["ready"]:
            continue
        direction = 1 if verdict["direction"] == "LONG" else -1 if verdict["direction"] == "SHORT" else 0
        if direction == 0:
            continue
        if require_displacement:
            disp_ok = bool(row.get("displacement_bullish", False)) if direction == 1 \
                else bool(row.get("displacement_bearish", False))
            if not disp_ok:
                continue

        entry = float(row["close"])
        atr = float(row[atr_col]) if atr_col else 0.0
        if not np.isfinite(atr) or atr <= 0:
            continue

        sl_level = _invalidation_level(estructura, direction, ltf)
        sl = sl_level if sl_level is not None else (entry - atr if direction == 1 else entry + atr)
        risk = abs(entry - sl)
        if risk <= 0:
            continue

        if tp_mode == "liquidity":
            liq = _tp_liquidity(row, direction)
            if liq is not None:
                tp = liq
            else:
                tp = entry + 2.0 * risk if direction == 1 else entry - 2.0 * risk
        else:
            tp = entry + 2.0 * risk if direction == 1 else entry - 2.0 * risk
        # Garantizar RR >= 1 (TP mas alla del SL en la direccion correcta)
        if direction == 1 and tp <= entry:
            tp = entry + 2.0 * risk
        if direction == -1 and tp >= entry:
            tp = entry - 2.0 * risk

        results.append(ICTSignal(
            symbol=symbol, time=str(row["time"]), direction=direction,
            entry=entry, stop_loss=sl, take_profit=tp,
            model=model, confidence=verdict["passed"] / max(1, verdict["total"]),
        ))
    return results


def simulate_trade(frame: pd.DataFrame, signal: ICTSignal,
                  max_hold_bars: int) -> tuple[ICTTrade | None, dict[str, Any]]:
    """Simula UN trade vela a vela hasta SL/TP/hold_limit. (Rescatado legacy.)"""
    times = frame["time"].astype(str)
    matches = list(frame.index[times == signal.time])
    if len(matches) == 0:
        return None, {"exit_reason": "time_not_found", "mfe_r": 0.0, "mae_r": 0.0, "hold_bars": 0}

    idx = int(matches[0])
    sl, tp = signal.stop_loss, signal.take_profit
    risk = abs(signal.entry - sl)
    if risk <= 0.0:
        return None, {"exit_reason": "invalid_risk", "mfe_r": 0.0, "mae_r": 0.0, "hold_bars": 0}

    exit_idx, exit_price, exit_reason = idx, signal.entry, "hold_limit"
    mfe_r, mae_r = -1e9, 1e9

    for step in range(1, max_hold_bars + 1):
        j = idx + step
        if j >= len(frame):
            break
        row = frame.iloc[j]
        high, low = float(row["high"]), float(row["low"])

        if signal.direction == 1:
            step_mfe = (high - signal.entry) / risk
            step_mae = (low - signal.entry) / risk
            if low <= sl:
                exit_idx, exit_price, exit_reason = j, sl, "SL"
                mfe_r, mae_r = max(mfe_r, step_mfe), min(mae_r, step_mae)
                break
            if high >= tp:
                exit_idx, exit_price, exit_reason = j, tp, "TP"
                mfe_r, mae_r = max(mfe_r, step_mfe), min(mae_r, step_mae)
                break
        else:
            step_mfe = (signal.entry - low) / risk
            step_mae = (signal.entry - high) / risk
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

    pnl_r = (exit_price - signal.entry) / risk if signal.direction == 1 else (signal.entry - exit_price) / risk
    trade = ICTTrade(
        symbol=signal.symbol, entry_time=signal.time,
        exit_time=str(frame.iloc[exit_idx]["time"]), direction=signal.direction,
        entry=signal.entry, exit=exit_price, pnl_r=float(pnl_r),
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
    for tf, df in frames.items():
        if tf == ltf or len(df) == 0:
            pass
        # indice por tiempo si es posible
        row = _row_at_time(df, ltf_time) if ltf_time is not None else (df.iloc[i] if i < len(df) else None)
        if row is None:
            est[tf] = {}
            continue
        est[tf] = {
            "trend": str(row.get("macro_direction", row.get("trend", "RANGING"))),
            "bos_dir": int(row.get("bos_direction", 0) or 0),
            "bos_status": str(row.get("bos_status", "")),
            "sweep_up": bool(row.get("liquidity_sweep_up", row.get("sweep_up", False))),
            "sweep_down": bool(row.get("liquidity_sweep_down", row.get("sweep_down", False))),
            "fvg_state": str(row.get("fvg_state", row.get("fvg_bullish", "-"))),
            "ob_dir": str(row.get("ob_direction", row.get("ob_dir", "-"))),
        }
    if ltf in frames:
        est[ltf] = est.get(ltf, {})
    return est


def _row_at_time(df: pd.DataFrame, t: Any) -> Any:
    """Fila cuyo tiempo es == t; si no existe, la ULTIMA con tiempo <= t (asof).

    El asof evita mirar el futuro: para una vela LTF en tiempo t, el contexto
    HTF es la ultima vela HTF ya cerrada (<= t).
    """
    try:
        tt = pd.to_datetime(t, utc=True, errors="coerce")
        times = pd.to_datetime(df["time"], utc=True, errors="coerce")
        exact = df.index[times == tt]
        if len(exact):
            return df.iloc[int(list(exact)[0])]
        prior = times[times <= tt]
        if len(prior):
            return df.iloc[int(prior.index[-1])]
    except Exception:
        pass
    return None


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


def _invalidation_level(estructura: dict, direction: int, exec_tf: str = "M15") -> float | None:
    """SL = nivel de invalidacion del TF de ejecucion. Si hay, usarlo; sino None."""
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
