"""Diagnóstico estructural del bias HTF en datos reales.

Imprime:
- Swings detectados por TF
- Etiquetas HH/HL/LH/LL
- Bias resultante por TF
- Coverage de bias direccional
- Posibles causas de 0 coverage
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

import pandas as pd

from engine.bias.narrative import (
    _swing_points,
    _label_swings,
    _bias_from_swings,
    _bias_for_frame,
    compute_htf_bias,
    compute_htf_bias_series,
)


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    o = df["open"].resample(rule, label="left", closed="left").first()
    h = df["high"].resample(rule, label="left", closed="left").max()
    l = df["low"].resample(rule, label="left", closed="left").min()
    c = df["close"].resample(rule, label="left", closed="left").last()
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}).dropna()


def load_real_data(symbol: str = "EURUSD", max_bars: int = 30000):
    from ict_backtest.sesgo.reloj.datos import validate_m15_parquet

    validated = validate_m15_parquet(symbol)
    m15 = validated.df.sort_index().iloc[:max_bars]
    h1 = _resample(m15, "1h")
    h4 = _resample(m15, "4h")
    d1 = _resample(m15, "1d")
    return d1, h4, h1, m15


def diagnose_frame(name: str, frame: pd.DataFrame, lookback: int = 5):
    print(f"\n=== {name} ({len(frame)} bars) ===")
    sh, sl = _swing_points(frame, lookback)
    sh_count = int(sh.notna().sum())
    sl_count = int(sl.notna().sum())
    print(f"swing_high count: {sh_count}")
    print(f"swing_low  count: {sl_count}")

    labels = _label_swings(sh, sl)
    label_counts = labels.value_counts()
    print(f"labels: {label_counts.to_dict()}")

    bias = _bias_for_frame(frame, lookback)
    print(f"frame bias: {bias}")

    # Show last few swings
    events = labels[labels != "NONE"]
    if len(events) > 0:
        print(f"last 5 labels: {events.tail(5).tolist()}")


def diagnose_htf(d1: pd.DataFrame, h4: pd.DataFrame, h1: pd.DataFrame, lookback: int = 5):
    print("\n=== HTF Bias ===")
    htf = compute_htf_bias(d1, h4, h1, swing_lookback=lookback)
    print(f"D1={htf.d1}, H4={htf.h4}, H1={htf.h1}")
    print(f"aligned={htf.aligned}, direction={htf.direction}")


def diagnose_series(d1: pd.DataFrame, h4: pd.DataFrame, h1: pd.DataFrame, m15: pd.DataFrame, lookback: int = 5):
    print("\n=== HTF Bias Series ===")
    series = compute_htf_bias_series(d1, h4, h1, m15, swing_lookback=lookback)
    print(f"series length: {len(series)}")
    if len(series) == 0:
        print("EMPTY SERIES")
        return

    dir_counts = series["direction"].value_counts()
    print(f"direction counts: {dir_counts.to_dict()}")
    aligned_counts = series["aligned"].value_counts()
    print(f"aligned counts: {aligned_counts.to_dict()}")

    coverage = float((series["direction"].isin(["BULLISH", "BEARISH"])).mean())
    print(f"bias_coverage: {coverage:.4f}")

    # Show first non-NEUTRAL if any
    non_neutral = series[series["direction"] != "NEUTRAL"]
    if len(non_neutral) > 0:
        print(f"first non-NEUTRAL: {non_neutral.iloc[0].to_dict()}")
    else:
        print("NO non-NEUTRAL found")


def main():
    print("Cargando datos reales EURUSD M15...")
    d1, h4, h1, m15 = load_real_data(max_bars=30000)
    print(f"D1={len(d1)}, H4={len(h4)}, H1={len(h1)}, M15={len(m15)}")
    print(f"D1 range: {d1.index[0]} -> {d1.index[-1]}")
    print(f"H4 range: {h4.index[0]} -> {h4.index[-1]}")
    print(f"H1 range: {h1.index[0]} -> {h1.index[-1]}")

    lookback = 5
    for name, frame in [("D1", d1), ("H4", h4), ("H1", h1)]:
        diagnose_frame(name, frame, lookback)

    diagnose_htf(d1, h4, h1, lookback)
    diagnose_series(d1, h4, h1, m15, lookback)


if __name__ == "__main__":
    raise SystemExit(main())
