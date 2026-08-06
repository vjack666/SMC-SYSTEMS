"""tests/test_engine_execution_b2.py — Test determinista de la brecha B2.

B2 = ejecucion fina del trader humano en TF de ejecucion (M5/M1).
El gate top-down (D1->H4) ya valido la direccion; este modulo la
baja a la entrada fina: entry = breakout del ultimo swing confirmado
(closed-only, anti look-ahead), SL = mecha del swing opuesto (estructural),
TP = RR 1:3 al objetivo de liquidez.

Geometria pura, sin indicadores. Verifica anti look-ahead: solo se usan
velas con time <= t en el TF de ejecucion.

El helper construye velas con picos alternados (par = minimo local,
impar = maximo local) para que engine.bias._swing_points detecte BOTH
swing highs y swing lows de forma deterministica.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.execution import fine_execution, _closed_df_at_time
from engine.bias.narrative import _swing_points


def _make_spikes(times):
    """Velas con picos alternados: par = minimo local (low muy bajo),
    impar = maximo local (high muy alto). Produce swings altos Y bajos."""
    n = len(times)
    highs = np.empty(n)
    lows = np.empty(n)
    opens = np.empty(n)
    closes = np.empty(n)
    for i in range(n):
        if i % 2 == 0:  # vela de minimo local
            lows[i] = -i * 0.5
            highs[i] = 0.2
        else:  # vela de maximo local
            lows[i] = 0.0
            highs[i] = i * 0.5 + 1.0
        opens[i] = (highs[i] + lows[i]) / 2
        closes[i] = highs[i] - 0.05
    df = pd.DataFrame(
        {
            "time": pd.to_datetime(times, utc=True),
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
        }
    )
    return df


def _build_ms():
    # 15 velas M5, 5 min cada una, iniciando 2024-01-01 00:00.
    base = pd.Timestamp("2024-01-01 00:00:00", tz="UTC")
    times = [base + pd.Timedelta(minutes=5 * i) for i in range(15)]
    df = _make_spikes(times)
    return df, times


def _last_swings(df, t):
    closed = _closed_df_at_time(df, t)
    sh, sl = _swing_points(closed, lookback=2)
    return float(sh.dropna().iloc[-1]), float(sl.dropna().iloc[-1])


def test_b2_long_entry_sl_tp_rr13():
    """LONG: entry=ultimo swing high, SL=ultimo swing low,
    TP = entry + 3*(entry - sl)."""
    df, times = _build_ms()
    ms = {"M5": df}
    t = times[-1]

    res = fine_execution(ms, t, direction=+1, exec_tf="M5", rr=3.0)
    assert res["ok"] is True, res
    assert res["exec_tf"] == "M5"
    assert res["rr"] == 3.0

    last_sh, last_sl = _last_swings(df, t)
    assert res["entry"] == round(last_sh, 5)
    assert res["sl"] == round(last_sl, 5)
    expected_tp = last_sh + 3.0 * (last_sh - last_sl)
    assert res["tp"] == round(expected_tp, 5)
    # SL estructuralmente valido: por debajo del entry en long
    assert res["sl"] < res["entry"]


def test_b2_short_entry_sl_tp_rr13():
    """SHORT: entry=ultimo swing low, SL=ultimo swing high (por encima),
    TP = entry - 3*(sl - entry). El modulo solo posiciona la entrada fina;
    el gate ya valido la direccion."""
    df, times = _build_ms()
    ms = {"M5": df}
    t = times[-1]

    res = fine_execution(ms, t, direction=-1, exec_tf="M5", rr=3.0)
    assert res["ok"] is True, res
    last_sh, last_sl = _last_swings(df, t)
    assert res["entry"] == round(last_sl, 5)   # short entry = ultimo swing low
    assert res["sl"] == round(last_sh, 5)      # sl = swing high opuesto
    assert res["sl"] > res["entry"]            # short: SL por encima
    expected_tp = last_sl - 3.0 * (last_sh - last_sl)
    assert res["tp"] == round(expected_tp, 5)


def test_b2_anti_lookahead_uses_only_closed_bars():
    """_closed_df_at_time recorta a time <= t; velas futuras no se usan."""
    df, times = _build_ms()
    t_cut = times[9]  # solo 10 velas cerradas
    closed = _closed_df_at_time(df, t_cut)
    assert len(closed) == 10
    assert closed["time"].max() == t_cut

    # La ejecucion en t_cut usa swings solo de esas 10 velas.
    res = fine_execution({"M5": df}, t_cut, direction=+1, exec_tf="M5")
    last_sh, last_sl = _last_swings(df, t_cut)
    assert res["entry"] == round(last_sh, 5)
    assert res["sl"] == round(last_sl, 5)


def test_b2_not_enough_bars():
    df, times = _build_ms()
    ms = {"M5": df.iloc[:4]}  # menos de 5 velas
    res = fine_execution(ms, times[3], direction=+1, exec_tf="M5")
    assert res["ok"] is False
    assert res["reason"] == "not_enough_bars"


def test_b2_fallback_to_m15_when_exec_missing():
    """Si no hay M5 pero hay M15, usa M15 como fallback."""
    df, times = _build_ms()
    ms = {"M15": df}
    res = fine_execution(ms, times[-1], direction=+1, exec_tf="M5")
    assert res["ok"] is True
    assert res["exec_tf"] == "M5"  # reporta el TF solicitado


def test_b2_no_data():
    res = fine_execution({}, None, direction=+1, exec_tf="M5")
    assert res["ok"] is False
    assert res["reason"] == "no_exec_tf_data"


def test_b2_fallback_sweep_sl_invalid_uses_swing():
    """Fase 1: si la mecha del sweep queda invalida en el TF fino (sl>=entry
    por compresion M5), fine_execution hace FALLBACK al ultimo swing opuesto
    del exec TF (estructura real, libro 18) en vez de descartar la senal.

    Fuerza el caso sobreescribiendo la vela del sweep para que su low quede
    POR ENCIMA del entry -> sl por sweep invalido -> fallback al swing low.
    """
    df, times = _build_ms()  # 15 velas M5 con swings deterministas
    # Sobreescribir la vela del sweep (idx 10) para que su low quede alto
    # (por encima del entry -> sl por sweep >= entry -> invalido).
    df.iloc[10, df.columns.get_loc("low")] = 100.0
    df.iloc[10, df.columns.get_loc("high")] = 100.5
    df.iloc[10, df.columns.get_loc("close")] = 100.4
    ms = {"M5": df}
    t = times[-1]          # entry = ultimo swing high (de _make_spikes)
    sweep_ts = times[10]   # vela del sweep con low=100.0 (por encima del entry)

    res = fine_execution(ms, t, direction=+1, exec_tf="M5", rr=3.0, sweep_ts=sweep_ts)
    assert res["ok"] is True, res
    # El fallback anclo el SL al swing low (estructura real), no a la mecha.
    assert res["sl"] < res["entry"]
    assert res["reason"] == "fine_exec_structural"
