"""RED — plan_driver.build_confirm_from_tf: confirma M5/M1 desde market_structure.

Dado el DataFrame de market_structure de un TF y el tiempo de entry t,
devuelve {"direction": dir, "confirmed": bool} si hay BOS/CHOCH activo en
esa direccion en barras cerradas <= t (closed-only anti look-ahead).
Funcion pura, testeable. Test FALLA hasta implementar build_confirm_from_tf.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

import pandas as pd


def _ms_df():
    # market_structure emite bos_dir/choch_dir (int: 1 bull / -1 bear / 0 none)
    return pd.DataFrame(
        {
            "time": pd.to_datetime(
                ["2026-01-01 10:00", "2026-01-01 10:05", "2026-01-01 10:10"]
            ),
            "bos_dir": [0, 1, 0],
            "choch_dir": [0, 0, -1],
        }
    )


def test_build_confirm_m5_alcista_en_t():
    from ict_backtest.plan_driver import build_confirm_from_tf

    df = _ms_df()
    # entry en 10:05 -> hay BOS alcista (bos_dir=1) cerrado <= t
    t = pd.to_datetime("2026-01-01 10:05")
    conf = build_confirm_from_tf(df, t, direction=1)
    assert conf["confirmed"] is True
    assert conf["direction"] == 1


def test_build_confirm_m5_sin_direccion_no_confirma():
    from ict_backtest.plan_driver import build_confirm_from_tf

    df = _ms_df()
    t = pd.to_datetime("2026-01-01 10:05")
    # setup bajista pero solo hay BOS alcista -> NO confirma
    conf = build_confirm_from_tf(df, t, direction=-1)
    assert conf["confirmed"] is False


def test_build_confirm_m5_ignora_futuro():
    from ict_backtest.plan_driver import build_confirm_from_tf

    df = _ms_df()
    # entry en 10:00 -> el BOS alcista esta en 10:05 (futuro) -> NO cuenta
    t = pd.to_datetime("2026-01-01 10:00")
    conf = build_confirm_from_tf(df, t, direction=1)
    assert conf["confirmed"] is False
