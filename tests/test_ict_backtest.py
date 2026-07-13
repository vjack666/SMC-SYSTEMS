"""Tests unitarios de ict_backtest/ (hallazgo #3, auditoría 2026-07-11).

Usan datos SINTÉTICOS (no el parquet de 50k velas) => corren en milisegundos
y son deterministas. Atrapan los bugs #1 (look-ahead), #2 (CHOCH=BOS), #4
(costos) y #5 (split walk-forward).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ict_backtest.market_structure import _swing_points, detect_market_structure, StructureConfig
from ict_backtest.engine import simulate_trade, ICTSignal
from ict_backtest.optimize import _split_windows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _flat(n=40, pico_idx=10, pico_val=101.0, base=100.0, low_base=99.0):
    high = [base] * n
    high[pico_idx] = pico_val
    low = [low_base] * n
    close = [base] * n
    open_ = [base] * n
    t = pd.date_range("2024-01-01", periods=n, freq="15min")
    return pd.DataFrame({"high": high, "low": low, "close": close,
                         "open": open_, "time": t})


# ---------------------------------------------------------------------------
# R1 — look-ahead bias en swing points
# ---------------------------------------------------------------------------
def test_swing_no_lookahead():
    df = _flat(n=40, pico_idx=10, pico_val=101.0)
    sh, sl = _swing_points(df, lookback=5)
    fi = sh.first_valid_index()
    # El pico en idx 10 solo debe exponerse en idx 10+5 = 15 (confirmación).
    assert fi == 15, f"swing_high expuesto en idx {fi}, esperado 15 (look-ahead)"
    assert abs(sh.iloc[fi] - 101.0) < 1e-9


def test_swing_planos_no_marcan():
    # Serie 100% plana: ningún swing debe marcarse como pico estricto.
    df = _flat(n=40, pico_idx=0, pico_val=100.0)
    sh, sl = _swing_points(df, lookback=5)
    assert sh.isna().all(), "serie plana no debe producir swing highs"


# ---------------------------------------------------------------------------
# R2 — CHOCH real distinto de BOS
# ---------------------------------------------------------------------------
def test_choch_differs_from_bos():
    # Serie con BOS alcista (pico en idx 10, break en 22, confirmado por
    # confirm_bars velas) seguido de CHOCH bajista (valle en 30, break en 42).
    # Usa el confirm_bars REAL del motor (default 2): el break necesita N velas
    # posteriores que NO reviertan para que el BOS se valide (ver AUDIT_CONFIRM_BARS_R4.md).
    from ict_backtest.market_structure import StructureConfig
    cb = StructureConfig().confirm_bars
    n = 60
    close = [100.0] * n
    high = [100.0] * n
    low = [100.0] * n
    # pico alto (swing high) en idx 10
    high[10] = 101.0
    # break alcista del swing high en idx 22 (sh.shift(1) ya poblado)
    close[22] = 101.5
    high[22] = 102.0
    # confirmacion: cb velas posteriores mantienen el break (no revierten)
    for k in range(1, cb + 1):
        close[22 + k] = 101.6
        high[22 + k] = 102.1
    # valle (swing low) en idx 30 -> disponible en 35
    low[30] = 99.0
    # break bajista del swing opuesto (CHOCH) en idx 42
    close[42] = 98.5
    low[42] = 98.0
    df = pd.DataFrame({"high": high, "low": low, "close": close,
                       "open": close, "atr": [0.5] * n,
                       "time": pd.date_range("2024-01-01", periods=n, freq="15min")})
    ms = detect_market_structure(df)
    diff = int((ms["bos_dir"] != ms["choch_dir"]).sum())
    # Al menos un BOS debe ocurrir y el CHOCH debe diferir en algún punto.
    assert int((ms["bos_dir"] != 0).sum()) > 0, "no se produjo ningun BOS"
    assert diff > 0, "CHOCH nunca difiere de BOS (sigue siendo copia)"


# ---------------------------------------------------------------------------
# R4 — costos reducen el pnl y SL antes que TP en empate
# ---------------------------------------------------------------------------
def test_engine_spread_reduces_pnl():
    df = pd.DataFrame({
        "time": ["2024-01-01 00:00:00", "2024-01-01 00:15:00", "2024-01-01 00:30:00"],
        "high": [1.1001, 1.1030, 1.1025],
        "low": [1.0999, 1.0995, 1.1010],
        "close": [1.1000, 1.1025, 1.1015],
        "open": [1.1000, 1.1000, 1.1025],
    })
    sig = ICTSignal(symbol="EURUSD", time="2024-01-01 00:00:00", direction=1,
                    entry=1.1000, stop_loss=1.0990, take_profit=1.1020, model="sequence")
    t0, _ = simulate_trade(df, sig, 96)
    t1, _ = simulate_trade(df, sig, 96, cost={"spread_pips": 1.0,
                                              "commission_pips": 0.5, "slippage_pips": 0.5})
    assert t1.pnl_r < t0.pnl_r, "los costos deben reducir el pnl_r"


def test_engine_sl_before_tp_on_tie():
    # Vela donde SL y TP se cruzan juntos => debe salir por SL (conservador).
    df = pd.DataFrame({
        "time": ["2024-01-01 00:00:00", "2024-01-01 00:15:00"],
        "high": [1.1000, 1.1020],   # toca TP
        "low": [1.1000, 1.0990],    # toca SL en la misma vela
        "close": [1.1000, 1.0990],
        "open": [1.1000, 1.1000],
    })
    sig = ICTSignal(symbol="EURUSD", time="2024-01-01 00:00:00", direction=1,
                    entry=1.1000, stop_loss=1.0990, take_profit=1.1020, model="sequence")
    t, meta = simulate_trade(df, sig, 96)
    assert meta["exit_reason"] == "SL", f"en empate debe salir por SL, salio {meta['exit_reason']}"


# ---------------------------------------------------------------------------
# R5 — split walk-forward multi-fold
# ---------------------------------------------------------------------------
def test_walkforward_multi_fold():
    n = 1000
    windows = _split_windows(n, n_windows=4, min_train=200)
    # Debe haber 4 folds y el test de cada uno avanza en el tiempo.
    assert len(windows) == 4, f"se esperaban 4 folds, hubo {len(windows)}"
    prev_te_s = -1
    for (tr_s, tr_e, te_s, te_e) in windows:
        assert te_s > prev_te_s, "los folds deben avanzar en el tiempo"
        assert tr_s == 0 and tr_e == te_s, "train debe ser [0, te_s)"
        prev_te_s = te_s


def test_walkforward_no_inverted():
    # El fold 0 (in-sample) debe ser el tramo MÁS VIEJO (pasado), no el final.
    n = 1000
    windows = _split_windows(n, n_windows=3, min_train=200)
    tr_s0, tr_e0, te_s0, te_e0 = windows[0]
    assert tr_s0 == 0 and te_e0 < n, "el in-sample debe ser el pasado, no el final"
