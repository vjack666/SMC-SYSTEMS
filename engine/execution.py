"""engine/execution.py — Ejecucion fina del trader humano (PERMANENTE, B2).

Brecha B2 del roadmap: el motor decidia la zona en M15, pero la TESIS (libro 18)
dice que la ENTRADA siempre va en el TF de ejecucion (M5/M1). Este modulo baja
la decision ya validada por el gate top-down (D1->H4->H1) a la entrada fina:
entry = breakout del ultimo swing en M5/M1, SL = mecha del swing opuesto
(estructural, no arbitrary), TP = RR 1:3 al objetivo de liquidez.

Ley: solo usa el motor (engine.bias._swing_points, engine.bos). NUNCA importa
ict_backtest/. Es geometria pura, sin indicadores. Anti look-ahead: solo velas
con time <= t en el TF de ejecucion.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from engine.bias.narrative import _swing_points


def _closed_df_at_time(df: pd.DataFrame, t: Any) -> pd.DataFrame:
    """Recorta df a velas ya cerradas al tiempo t (time <= t)."""
    times = pd.to_datetime(df["time"], utc=True, errors="coerce")
    tt = pd.to_datetime(t, utc=True, errors="coerce")
    if pd.isna(tt):
        return df.iloc[0:0]
    mask = times <= tt
    return df.loc[mask]


def fine_execution(
    ms: dict[str, pd.DataFrame],
    t: Any,
    direction: int,
    *,
    exec_tf: str = "M5",
    rr: float = 3.0,
) -> dict[str, Any]:
    """Entrada fina en M5/M1 para una direccion ya validada por el gate.

    Args:
        ms: frames por TF (debe incluir exec_tf; fallback a M15).
        t: tiempo de la vela LTF ya cerrada (anti look-ahead).
        direction: +1 long, -1 short.
        exec_tf: TF de ejecucion fina ("M5" por defecto; "M1" permitido).
        rr: ratio take-profit / stop-loss (1:3 ICT).

    Returns:
        dict con keys: ok, exec_tf, entry, sl, tp, rr, reason.
        ok=False si no hay suficiente estructura en el TF de ejecucion.
    """
    df = ms.get(exec_tf)
    if df is None:  # fallback a M15 si no hay TF de ejecucion
        df = ms.get("M15")
    if df is None or len(df) == 0:
        return {"ok": False, "exec_tf": exec_tf, "reason": "no_exec_tf_data"}

    closed = _closed_df_at_time(df, t)
    if len(closed) < 5:
        return {"ok": False, "exec_tf": exec_tf, "reason": "not_enough_bars"}

    sh, sl = _swing_points(closed, lookback=2)
    sh_v = sh.dropna()
    sl_v = sl.dropna()
    if sh_v.empty or sl_v.empty:
        return {"ok": False, "exec_tf": exec_tf, "reason": "no_swings"}

    # Ultimo swing high y low confirmados (closed-only).
    last_sh = float(sh_v.iloc[-1])
    last_sl = float(sl_v.iloc[-1])

    if direction > 0:  # LONG: entry = breakout del ultimo swing high (HH)
        entry = last_sh
        sl_price = last_sl  # mecha del swing low opuesto (estructural)
        if sl_price >= entry:
            return {"ok": False, "exec_tf": exec_tf, "reason": "sl_invalid_long"}
        tp_price = entry + rr * (entry - sl_price)
        tp_ext = float(closed["high"].max())  # liquidez externa = maximo high
    else:  # SHORT: entry = breakout del ultimo swing low (LL)
        entry = last_sl
        sl_price = last_sh  # mecha del swing high opuesto
        if sl_price <= entry:
            return {"ok": False, "exec_tf": exec_tf, "reason": "sl_invalid_short"}
        tp_price = entry - rr * (sl_price - entry)
        tp_ext = float(closed["low"].min())  # liquidez externa = minimo low

    # rng_exec: rango promedio de vela del exec TF (matematica pura, sin
    # indicadores). Fuente unica de volatilidad del SL estructural fino.
    _rng = (closed["high"] - closed["low"])
    rng_exec = float(_rng.tail(50).mean()) if len(_rng) >= 50 else float(_rng.mean())

    return {
        "ok": True,
        "exec_tf": exec_tf,
        "entry": round(entry, 5),
        "sl": round(sl_price, 5),
        "tp": round(tp_price, 5),
        "tp_ext": round(tp_ext, 5),
        "rng_exec": rng_exec,
        "rr": rr,
        "reason": "fine_exec_structural",
    }
