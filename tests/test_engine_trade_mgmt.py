"""Tests engine.trade_mgmt — BE/parcial/trailing (geometria, sin indicadores)."""
import pandas as pd
from engine.trade_mgmt import apply_trade_management, to_breakeven, partial_exit


def _df_seq():
    # entry 1.1000 sl 1.0900 tp 1.1300; sube a tp1(1.1100=+1R) y cae -> parcial+BE
    rows = [
        (1.1000, 1.1001, 1.0950, 1.1000),
        (1.1005, 1.1110, 1.1000, 1.1105),  # toca tp1 (>=1.1100) -> parcial + BE
        (1.1100, 1.1111, 1.1080, 1.1090),
        (1.1085, 1.1090, 1.0990, 1.1000),  # revierte cerca de BE -> sale en BE
    ]
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"])


def test_partial_and_be():
    df = _df_seq()
    res = apply_trade_management(1.1000, 1.0900, 1.1300, 1, df, partial_pct=0.5, tp1_r=1.0)
    assert res["partial_done"] is True
    assert res["exit_reason"] in ("be", "sl")
    assert res["pnl_r"] >= 0.0  # parcial +1R protege


def test_to_breakeven_trigger():
    # valores no-limite: risk=0.01 advance=0.01 claro
    assert to_breakeven(1.1000, 1.0900, 1, 1.1100, be_trigger_r=1.0) == 1.1000
    assert to_breakeven(1.1000, 1.0900, 1, 1.1050, be_trigger_r=1.0) is None


def test_partial_exit_touch():
    assert partial_exit(1.1000, 1.1100, 1, 1.1100) is True
    assert partial_exit(1.1000, 1.1100, 1, 1.1050) is False
