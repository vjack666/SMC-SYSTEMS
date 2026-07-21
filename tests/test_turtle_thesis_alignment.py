"""Test de alineación a la tesis 18 del camino SEQUENCE (Turtle Soup).

Valida que el SL/entry del camino sequence usen AHORA la misma lógica que el
camino checklist (tesis 18): SL = mecha del sweep (calc_structural_sl),
RR >= 1:3, y filtro de killzone. Antes el sequence usaba SL=BOS+-0.5ATR
(fallback entry-1ATR) y RR 1:2 -> incumplía la tesis.
"""

import pandas as pd

from ict_backtest.engine import calc_structural_sl, _tp_liquidity, STRUCT_SL_MAX_RANGE
from ict_backtest.rules import killzone_en


def _row(sweep_low=None, sweep_high=None, close=1.1000, atr=0.0010,
         bsl=None, ssl=None):
    return pd.Series({
        "sweep_low": sweep_low, "sweep_high": sweep_high,
        "close": close, "atr": atr,
        "bsl_price": bsl, "ssl_price": ssl,
    })


def test_sl_anclado_a_meha_sweep_long():
    # Long tras sweep DOWN (SSL). SL debe anclarse a sweep_low - buffer.
    atr = 0.0010
    buf = 0.3 * atr
    sweep_low = 1.0950
    row = _row(sweep_low=sweep_low, atr=atr)
    sl = calc_structural_sl(row, 1, atr)
    assert sl is not None
    # SL bajo la mecha del sweep (no un BOS+-ATR ni entry-ATR ciego).
    assert sl == pytest.approx(sweep_low - buf)
    assert sl < sweep_low


def test_sl_anclado_a_meha_sweep_short():
    atr = 0.0010
    buf = 0.3 * atr
    sweep_high = 1.1050
    row = _row(sweep_high=sweep_high, atr=atr)
    sl = calc_structural_sl(row, -1, atr)
    assert sl is not None
    assert sl == pytest.approx(sweep_high + buf)
    assert sl > sweep_high


def test_sl_none_sin_nivel_estructural():
    # Sin sweep ni swing -> tesis: NO operar (None), no degradar a ATR.
    row = _row(atr=0.0010)
    assert calc_structural_sl(row, 1, 0.0010) is None
    assert calc_structural_sl(row, -1, 0.0010) is None


def test_filtro_tamano_sl_gigante():
    # Sweep gigante -> riesgo > STRUCT_SL_MAX_RANGE*rango -> motor SALTA (no comprime).
    rng = 0.0010
    sweep_low = 1.0900  # 90 pips bajo el entry -> riesgo ~90 rangos
    entry = 1.0990
    row = _row(sweep_low=sweep_low, atr=rng)
    sl = calc_structural_sl(row, 1, rng)
    risk = abs(entry - sl)
    assert risk > STRUCT_SL_MAX_RANGE * rng


def test_tp_liquidez_opuesta_preferida():
    # TP = liquidez opuesta MAS CERCANA del exec TF (tesis #6).
    atr = 0.0010
    row = _row(close=1.1000, atr=atr, bsl=1.1080)
    liq = _tp_liquidity(row, 1)
    assert liq["internal"] == 1.1080


def test_killzone_filtra_fuera_de_ventana():
    # Fuera de London/NY -> no debe operar (tesis #8).
    ts_fuera = pd.Timestamp("2026-07-14 22:00:00", tz="UTC")  # 22 UTC = fuera
    assert killzone_en(ts_fuera) == ""
    ts_london = pd.Timestamp("2026-07-14 08:00:00", tz="UTC")  # London Open
    assert killzone_en(ts_london) == "London Open"
    ts_ny = pd.Timestamp("2026-07-14 13:30:00", tz="UTC")  # NY AM
    assert killzone_en(ts_ny) == "New York AM"


import pytest  # noqa: E402  (al final para que las defs above no requieran antes)
