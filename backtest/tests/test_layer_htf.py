"""TDD tests for layer_htf: HTF structure from M5 aggregation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytest

from backtest.layers.layer_htf import (
    build_htf_chain,
    compute_htf_bias,
    HTFBar,
    OHLCVBar,
)


def _make_m5_bar(ts: datetime, o: float, h: float, l: float, c: float, v: float = 1000) -> OHLCVBar:
    return OHLCVBar(
        timestamp=ts,
        open=o,
        high=h,
        low=l,
        close=c,
        volume=v,
    )


def test_h1_aggregation_12_bars():
    """H1 = 12 velas M5. Verifica que la agregacion sea correcta."""
    base = datetime(2026, 1, 1, 0, 0, 0)
    bars = []
    for i in range(12):
        ts = base + timedelta(minutes=5 * i)
        bars.append(_make_m5_bar(ts, 1.0 + i * 0.001, 1.0 + i * 0.002, 1.0, 1.0 + i * 0.0015, 1000))

    htf_chain = {}
    htf_chain = build_htf_chain(htf_chain, bars, bar_index_m5=11)

    assert "H1" in htf_chain
    h1 = htf_chain["H1"]
    assert h1["open"] == 1.0
    assert h1["high"] == pytest.approx(1.0 + 11 * 0.002)
    assert h1["low"] == 1.0
    assert h1["close"] == pytest.approx(1.0 + 11 * 0.0015)
    assert h1["volume"] == 12000


def test_h4_aggregation_48_bars():
    """H4 = 48 velas M5. Verifica max/min/sum correctos."""
    base = datetime(2026, 1, 1, 0, 0, 0)
    bars = []
    for i in range(48):
        ts = base + timedelta(minutes=5 * i)
        o = 1.0 + (i // 12) * 0.01
        h = o + 0.005
        l = o - 0.005
        c = o + 0.002
        bars.append(_make_m5_bar(ts, o, h, l, c, 1000))

    htf_chain = {}
    htf_chain = build_htf_chain(htf_chain, bars, bar_index_m5=47)

    assert "H4" in htf_chain
    h4 = htf_chain["H4"]
    assert h4["open"] == pytest.approx(1.0)
    assert h4["high"] == pytest.approx(1.0 + 3 * 0.01 + 0.005)
    assert h4["low"] == pytest.approx(1.0 - 0.005)
    assert h4["close"] == pytest.approx(1.0 + 3 * 0.01 + 0.002)
    assert h4["volume"] == 48000


def test_d1_aggregation_288_bars():
    """D1 = 288 velas M5. Solo dias naturales completos."""
    base = datetime(2026, 1, 1, 0, 0, 0)
    bars = []
    for i in range(288):
        ts = base + timedelta(minutes=5 * i)
        bars.append(_make_m5_bar(ts, 1.0, 1.01, 0.99, 1.005, 1000))

    htf_chain = {}
    htf_chain = build_htf_chain(htf_chain, bars, bar_index_m5=287)

    assert "D1" in htf_chain
    d1 = htf_chain["D1"]
    assert d1["open"] == 1.0
    assert d1["high"] == 1.01
    assert d1["low"] == 0.99
    assert d1["close"] == 1.005
    assert d1["volume"] == 288000


def test_htf_bias_bullish():
    """Bias BULLISH: close > open de hace 5 periodos HTF."""
    # Construir 6 barras H1 donde la ultima cierra arriba de la open de hace 5
    base = datetime(2026, 1, 1, 0, 0, 0)
    h1_bars = []
    for i in range(6):
        o = 1.0
        c = 1.01  # siempre alcista
        h = max(o, c) + 0.005
        l = min(o, c) - 0.005
        h1_bars.append({
            "timestamp": base + timedelta(hours=i),
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": 12000,
        })

    bias = compute_htf_bias(h1_bars, lookback=5)
    assert bias == "BULLISH"


def test_htf_bias_bearish():
    """Bias BEARISH: close < open de hace 5 periodos HTF."""
    base = datetime(2026, 1, 1, 0, 0, 0)
    h1_bars = []
    for i in range(6):
        o = 1.01
        c = 1.0
        h = max(o, c) + 0.005
        l = min(o, c) - 0.005
        h1_bars.append({
            "timestamp": base + timedelta(hours=i),
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": 12000,
        })

    bias = compute_htf_bias(h1_bars, lookback=5)
    assert bias == "BEARISH"


def test_htf_bias_range():
    """Bias RANGE cuando close == open de hace 5 periodos."""
    base = datetime(2026, 1, 1, 0, 0, 0)
    h1_bars = []
    for i in range(6):
        h1_bars.append({
            "timestamp": base + timedelta(hours=i),
            "open": 1.0,
            "high": 1.01,
            "low": 0.99,
            "close": 1.0,
            "volume": 12000,
        })

    bias = compute_htf_bias(h1_bars, lookback=5)
    assert bias == "RANGE"


def test_htf_chain_no_interpolation():
    """Si faltan velas, no se inventa. No se actualiza la capa si no hay 12 velas."""
    base = datetime(2026, 1, 1, 0, 0, 0)
    bars = []
    for i in range(10):  # solo 10, faltan 2 para H1
        ts = base + timedelta(minutes=5 * i)
        bars.append(_make_m5_bar(ts, 1.0, 1.01, 0.99, 1.005, 1000))

    htf_chain = build_htf_chain({}, bars, bar_index_m5=9)
    assert "H1" not in htf_chain  # no se forma H1 hasta tener 12
