"""B3 — Jerarquía de liquidez internal vs external (MDS_B3_LIQUIDEZ_INT_EXT).

RED: define el contrato nuevo de _tp_liquidity.
- Devuelve dict {"internal": float|None, "external": float|None}.
- internal = bsl_price (long) / ssl_price (short) del row (igual que antes).
- external = PDH (long) / PDL (short) del dia previo en df; None si no hay.
- Sin df o sin dia previo -> external=None (regresion cero: usa internal).

NO toca datos reales: usa DataFrames sinteticos.
"""
import pandas as pd
import numpy as np
import pytest

from ict_backtest.engine import _tp_liquidity
from ict_backtest.canonical import evaluate_signals
from ict_backtest.market_structure import detect_market_structure


def _make_df_two_days():
    # Dia 1 (previo): high=1.10 low=1.00
    # Dia 2 (row):    high=1.12 low=1.02  bsl_price=1.13 / ssl_price=0.99
    d1 = pd.Timestamp("2026-01-01", tz="UTC")
    d2 = pd.Timestamp("2026-01-02", tz="UTC")
    rows = [
        {"time": d1 + pd.Timedelta(hours=h), "high": 1.10, "low": 1.00,
         "close": 1.05, "bsl_price": np.nan, "ssl_price": np.nan}
        for h in range(24)
    ] + [
        {"time": d2 + pd.Timedelta(hours=h), "high": 1.12, "low": 1.02,
         "close": 1.06, "bsl_price": 1.13, "ssl_price": 0.99}
        for h in range(24)
    ]
    df = pd.DataFrame(rows)
    # row del dia 2 (la ultima vela del df)
    row = df.iloc[-1]
    return df, row


def test_red_internal_usa_bsl_ssl_igual_que_antes():
    df, row = _make_df_two_days()
    # long -> internal = bsl_price
    out = _tp_liquidity(row, 1, df)
    assert isinstance(out, dict)
    assert out["internal"] == 1.13
    # short -> internal = ssl_price
    out2 = _tp_liquidity(row, -1, df)
    assert out2["internal"] == 0.99


def test_red_external_es_pdh_pdl_dia_previo():
    df, row = _make_df_two_days()
    # long -> external = PDH del dia 1 = 1.10
    out = _tp_liquidity(row, 1, df)
    assert out["external"] == 1.10
    # short -> external = PDL del dia 1 = 1.00
    out2 = _tp_liquidity(row, -1, df)
    assert out2["external"] == 1.00


def test_red_sin_df_o_sin_dia_previo_external_none_regresion():
    df, row = _make_df_two_days()
    # Sin df -> external None, internal sigue funcionando
    out = _tp_liquidity(row, 1)  # df=None
    assert out["internal"] == 1.13
    assert out["external"] is None
    # df de un solo dia (sin previo) -> external None
    df1 = df.iloc[24:].reset_index(drop=True)
    out2 = _tp_liquidity(df1.iloc[-1], 1, df1)
    assert out2["internal"] == 1.13
    assert out2["external"] is None


def test_red_row_sin_bsl_internal_none():
    df, row = _make_df_two_days()
    row_no_bsl = row.copy()
    row_no_bsl["bsl_price"] = np.nan
    out = _tp_liquidity(row_no_bsl, 1, df)
    assert out["internal"] is None


# === ACEPTANCE: call-site REAL de canonical con external_tp poblado ===
# Reusa el stub de senal de B2 (run_sequence -> 1 senal cruda) para no
# depender de que run_sequence detecte el setup en datos sinteticos planos.
from tests.test_b2_exec_tf import _inject_signal, _ohlc  # noqa: E402


def _make_frames_2day():
    """M15 de 2 dias: dia1 (previo) + dia2 (senal)."""
    d1 = pd.Timestamp("2026-01-05 09:00", tz="UTC")  # dia 1
    d2 = pd.Timestamp("2026-01-06 09:00", tz="UTC")  # dia 2 (entry)
    # Dia 1: high 1.1100 / low 1.0900 (PDH=1.1100, PDL=1.0900)
    t1 = pd.date_range(d1, periods=40, freq="15min", tz="UTC")
    m15_d1 = _ohlc(t1, 1.1000, sweep_low=1.0990)
    m15_d1["high"] = 1.1100
    m15_d1["low"] = 1.0900
    m15_d1_d1 = detect_market_structure(m15_d1)
    # Dia 2: entry idx 3 (09:45). bsl_price en ese row = 1.1300 (internal).
    t2 = pd.date_range(d2, periods=40, freq="15min", tz="UTC")
    m15_d2 = _ohlc(t2, 1.1000, sweep_low=1.0990)
    m15_d2["bsl_price"] = np.nan
    m15_d2.loc[3, "bsl_price"] = 1.1300  # internal long
    m15_d2["high"] = 1.1320
    m15_d2["low"] = 1.0980
    m15_d2_s = detect_market_structure(m15_d2)
    # Concatenar ambos dias en UN solo df M15 (canonical lo recibe como ms[ltf]).
    m15 = pd.concat([m15_d1, m15_d2_s], ignore_index=True)
    ms_m15 = detect_market_structure(m15)
    # HTF dummy (no influye en TP).
    d1t = pd.date_range(d1, periods=2, freq="1D", tz="UTC")
    d1df = _ohlc(d1t, 1.1000)
    ms_d1 = detect_market_structure(d1df)
    frames = {"D1": ms_d1, "H4": ms_d1, "H1": ms_d1,
              "M15": ms_m15, "M5": ms_m15, "M1": ms_m15}
    # entry_at en el df concatenado = 40 (inicio dia2) + 3 = 43.
    return frames, 43


def test_acceptance_call_site_external_tp_pdh_prev_day(monkeypatch):
    """evaluate_signals real devuelve TP=internal y external_tp=PDH dia previo."""
    frames, entry_at = _make_frames_2day()
    _inject_signal(monkeypatch, entry_at, sweep_at=0, direction=1)
    sigs = evaluate_signals(
        "SYN", "D1", "M15", frames=frames,
        enable_pd_index=False, exec_tf=None,
        use_semantic=False,
    )
    assert sigs, "no se produjo senal"
    sig = sigs[0]
    # TP primario = internal (bsl_price del row de entry = 1.1300).
    assert sig.take_profit == 1.1300, f"TP no es internal: {sig.take_profit}"
    # external_tp = PDH del dia 1 = 1.1100 (anotado para E1).
    assert sig.external_tp == 1.1100, f"external_tp no es PDH: {sig.external_tp}"

