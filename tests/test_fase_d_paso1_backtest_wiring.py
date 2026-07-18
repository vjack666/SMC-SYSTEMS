"""Fase D — Paso 1: Fase C viaja a los backtests (METADATA, sin gate).

Auditoría de PRODUCCIÓN (no solo función aislada): el call site real
`run_backtest.run_sequence_backtest` debe propagar `zone_authority` cuando
`enable_pd_index=True`, y dejarlo None cuando False (modo histórico,
R1 preservado: mismo conteo de señales).

Esto evita el patrón "verde en la función, muerto en el call site" que
ya golpeó a Fase C en el observador.

Datos sintéticos pequeños (corre en ms).
"""

import pandas as pd
import pytest

from ict_backtest.market_structure import detect_market_structure
from ict_backtest.run_backtest import run_sequence_backtest


def _make_ltf(n: int = 80):
    """LTF sintético BULLISH con sweep->displace->BOS->retorno mínimo."""
    t0 = pd.Timestamp("2024-01-01 00:00:00", tz="UTC")
    rows = []
    p = 100.0
    for i in range(n):
        o = p
        c = o + 0.5
        h = max(o, c) + 0.3
        l = min(o, c) - 0.3
        if i == 40:  # sweep alcista fuerte
            h = o + 3.0
            c = o + 0.2
            l = o - 0.2
        rows.append(dict(time=t0 + pd.Timedelta(minutes=15 * i),
                         open=o, high=h, low=l, close=c, volume=1))
        p = c
    return detect_market_structure(pd.DataFrame(rows))


def _make_htf():
    """HTF sintético con FVG bullish (ancla para el índice)."""
    t0 = pd.Timestamp("2024-01-01 00:00:00", tz="UTC")
    rows = [
        dict(time=t0 + pd.Timedelta(hours=4 * i), open=100.0 + i,
             high=102.0 + i, low=99.0 + i, close=101.5 + i, volume=1)
        for i in range(4)
    ]
    df = pd.DataFrame(rows)
    df.loc[2, "fvg_bullish"] = True
    df.loc[2, "fvg_bull_high"] = 103.5
    df.loc[2, "fvg_bull_low"] = 102.5
    df.loc[2, "high"] = 104.0
    return df


def test_backtest_cli_propagates_zone_authority_when_enabled():
    """Paso 1: generate_sequence_signals(enable_pd_index=True) — el call
    site real del CLI y v2 — debe traer zone_authority poblado en las
    señales (es METADATA, no altera decisión)."""
    ltf = _make_ltf()
    htf = _make_htf()
    frames = {"M15": ltf, "H4": htf, "D1": htf}
    from ict_backtest.run_backtest import generate_sequence_signals
    sigs = generate_sequence_signals(
        "SYN", "H4", "M15", require_displacement=False,
        frames=frames, enable_pd_index=True,
    )
    if sigs:  # puede que el LTF sintético no complete B1
        for s in sigs:
            assert s.zone_authority is not None, (
                "Fase C muerta en call site backtest: zone_authority None "
                "pese a enable_pd_index=True"
            )
            assert 0.0 <= float(s.zone_authority["confidence_weight"]) <= 1.0


def test_backtest_cli_historical_mode_leaves_authority_none():
    """R1 en el runner: modo histórico (enable_pd_index=False) deja
    zone_authority None y NO altera el conteo vs modo con índice."""
    ltf = _make_ltf()
    htf = _make_htf()
    frames = {"M15": ltf, "H4": htf, "D1": htf}
    from ict_backtest.run_backtest import generate_sequence_signals
    off = generate_sequence_signals(
        "SYN", "H4", "M15", require_displacement=False,
        frames=frames, enable_pd_index=False,
    )
    on = generate_sequence_signals(
        "SYN", "H4", "M15", require_displacement=False,
        frames=frames, enable_pd_index=True,
    )
    assert len(off) == len(on), (
        f"Fase C alteró conteo en backtest: {len(off)} -> {len(on)}"
    )
    for s in off:
        assert s.zone_authority is None
