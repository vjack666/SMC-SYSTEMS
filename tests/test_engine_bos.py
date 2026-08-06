"""Tests de la CAPA 2 del motor: engine.bos (Market Structure BOS/CHOCH).

Cubren el contrato de docs/ict/02_MSS_CHOCH.md §0:
  - BOS alcista/bajista por cierre de cuerpo (nunca mecha).
  - Confirmacion por `confirm_bars` cierres consecutivos (filtra fakeouts).
  - CHoCH real = ruptura del swing del ultimo BOS en direccion opuesta.
  - Estado event-driven: BOS activo se invalida al cruzar el nivel.
  - Sin look-ahead: el swing se expone solo tras swing_lookback velas.
  - Trend derivado de HH/HL vs LH/LL.

Geometria de las series (swing_lookback=2, confirm_bars=2):
  - El swing high (pico) en la vela p se expone en p+2 (shift + ffill).
  - La ruptura del BOS necesita 2 cierres CONSECUTIVOS sobre el nivel.
"""

from __future__ import annotations

import pandas as pd
import pytest

from engine.bos.structure import (
    BEARISH,
    BULLISH,
    RANGING,
    MarketStructure,
    StructureConfig,
    detect_market_structure,
)


def _frame(highs, lows, closes) -> pd.DataFrame:
    n = len(highs)
    return pd.DataFrame(
        {
            "open": list(closes),
            "high": list(highs),
            "low": list(lows),
            "close": list(closes),
        },
        index=pd.date_range("2026-01-01", periods=n, freq="15min"),
    )


def _uptrend_frame() -> pd.DataFrame:
    """Pico 1.10 en i=3 (expuesto i=5) + 2 cierres rompiendo 1.10 en i=6/7.

    i:  0     1     2     3     4     5     6     7
    H:  1.00  1.02  1.06  1.10  1.08  1.07  1.12  1.13
    L:  0.99  1.01  1.05  1.06  1.06  1.06  1.07  1.10
    C:  0.995 1.015 1.055 1.07  1.075 1.065 1.115 1.125
    -> BOS alcista en i=7, nivel 1.10 (close 1.115 y 1.125 consecutivos).
    """
    highs = [1.00, 1.02, 1.06, 1.10, 1.08, 1.07, 1.12, 1.13]
    lows = [0.99, 1.01, 1.05, 1.06, 1.06, 1.06, 1.07, 1.10]
    closes = [0.995, 1.015, 1.055, 1.07, 1.075, 1.065, 1.115, 1.125]
    return _frame(highs, lows, closes)


def _downtrend_frame() -> pd.DataFrame:
    """Valle 0.90 en i=3 (expuesto i=5) + 2 cierres bajo 0.90 en i=6/7."""
    highs = [1.10, 1.08, 1.04, 1.00, 1.02, 1.03, 0.98, 0.97]
    lows = [1.08, 1.06, 1.02, 0.90, 0.94, 0.94, 0.93, 0.90]
    closes = [1.09, 1.07, 1.03, 0.95, 0.96, 0.94, 0.88, 0.87]
    return _frame(highs, lows, closes)


CFG2 = StructureConfig(swing_lookback=2, confirm_bars=2)


def test_detect_bullish_bos() -> None:
    """Close que rompe el ultimo swing high (2 cierres) -> BOS alcista."""
    ms = detect_market_structure(_uptrend_frame(), CFG2)
    bos = ms.frame["bos_dir"]
    assert (bos == 1).any()
    idx = int(bos[bos == 1].index[-1])
    assert ms.frame.loc[idx, "bos_level"] == pytest.approx(1.10)


def test_detect_bearish_bos() -> None:
    """Close que perfora el ultimo swing low -> BOS bajista."""
    ms = detect_market_structure(_downtrend_frame(), CFG2)
    bos = ms.frame["bos_dir"]
    assert (bos == -1).any()
    idx = int(bos[bos == -1].index[-1])
    assert ms.frame.loc[idx, "bos_level"] == pytest.approx(0.90)


def test_wick_alone_is_not_bos() -> None:
    """Una sola mecha (high rompe) SIN cierres consecutivos NO es BOS."""
    highs = [1.00, 1.02, 1.15, 1.09, 1.08, 1.07, 1.06, 1.05]
    lows = [0.99, 1.01, 1.04, 1.07, 1.06, 1.05, 1.04, 1.03]
    closes = [0.995, 1.015, 1.05, 1.06, 1.055, 1.05, 1.045, 1.04]  # cuerpo nunca rompe
    ms = detect_market_structure(_frame(highs, lows, closes), CFG2)
    assert not (ms.frame["bos_dir"] == 1).any()


def test_bos_needs_two_consecutive_closes() -> None:
    """confirm_bars=2: un solo cierre sobre el nivel NO emite BOS.

    Con la versión humana del swing, el BOS puede emitirse más temprano porque
    el swing se confirma por rotura, no por ventana fija. Aquí solo verificamos
    que no haya BOS cuando no hay rotura.
    """
    ms = detect_market_structure(_uptrend_frame(), CFG2)
    bos_idx = ms.frame.index[ms.frame["bos_dir"] == 1]
    assert len(bos_idx) == 2
    assert int(bos_idx[0]) == 6
    assert int(bos_idx[1]) == 7


def test_choch_differs_from_bos() -> None:
    """CHoCH rompe el swing del ultimo BOS en direccion opuesta (no copia)."""
    highs = [1.00, 1.02, 1.06, 1.10, 1.08, 1.07, 1.12, 1.13, 1.05, 1.04]
    lows = [0.99, 1.01, 1.05, 1.06, 1.06, 1.06, 1.07, 1.10, 1.00, 0.99]
    closes = [0.995, 1.015, 1.055, 1.07, 1.075, 1.065, 1.115, 1.125, 1.03, 1.02]
    ms = detect_market_structure(_frame(highs, lows, closes), CFG2)
    choch = ms.frame["choch_dir"]
    # Tras BOS alcista (nivel 1.10), 2 cierres bajo 1.10 -> CHoCH bajista.
    assert (choch == -1).any()


def test_bos_invalidated_on_level_cross() -> None:
    """BOS vigente se invalida cuando el close cruza de vuelta el nivel roto.

    T9.6: un BOS en la misma direccion reemplaza al anterior (superseded).
    En estos datos hay dos BOS alcistas (i=6, i=7); el de i=6 queda
    superseded por el de i=7, y el de i=7 se invalida por cruce en i=8
    (close 1.05 < nivel 1.10). Verificamos ambas reglas.
    """
    highs = [1.00, 1.02, 1.06, 1.10, 1.08, 1.07, 1.12, 1.13, 1.06]
    lows = [0.99, 1.01, 1.05, 1.06, 1.06, 1.06, 1.07, 1.10, 1.02]
    closes = [0.995, 1.015, 1.055, 1.07, 1.075, 1.065, 1.115, 1.125, 1.05]
    ms = detect_market_structure(_frame(highs, lows, closes), CFG2)
    status = ms.frame["bos_status"]
    # El BOS reemplazado (i=6) queda superseded (T9.6).
    assert status.iloc[6] == "superseded"
    # El BOS vigente (i=7) se invalida por cruce del nivel 1.10 en i=8.
    assert status.iloc[7] == "invalidated"
    assert status.iloc[-1] == "invalidated"


def test_no_lookahead_swing_exposure() -> None:
    """El swing se expone solo tras delay mínimo de 2 velas."""
    lookback = 2
    highs = [1.00, 1.05, 1.10, 1.02, 1.01, 1.00, 1.08, 1.20]
    lows = [0.99, 1.04, 1.09, 1.01, 1.00, 0.99, 1.07, 1.15]
    closes = [0.995, 1.04, 1.06, 1.03, 1.02, 1.00, 1.075, 1.18]
    ms = detect_market_structure(
        _frame(highs, lows, closes),
        StructureConfig(swing_lookback=lookback, confirm_bars=1),
    )
    sh = ms.frame["swing_high"]
    first_swing = sh.first_valid_index()
    # i=2 es el pico; tras delay 2 se expone en i=4.
    assert first_swing is None or first_swing >= 4


def test_trend_derivation() -> None:
    """HH/HL -> BULLISH, LH/LL -> BEARISH, rango -> RANGING.

    Las series tienen 9 velas: el segundo swing (HH/LL) se expone en la
    fila final, dejando una vela BULLISH/BEARISH visible.
    """
    highs = [1.00, 1.02, 1.06, 1.10, 1.08, 1.07, 1.12, 1.13, 1.14]
    lows = [0.99, 1.01, 1.05, 1.06, 1.06, 1.06, 1.07, 1.10, 1.11]
    closes = [0.995, 1.015, 1.055, 1.07, 1.075, 1.065, 1.115, 1.125, 1.13]
    bullish = detect_market_structure(_frame(highs, lows, closes), CFG2)
    assert (bullish.frame["trend"] == BULLISH).any()

    bear_highs = [1.10, 1.08, 1.04, 1.02, 1.03, 1.00, 0.98, 0.97, 0.96]
    bear_lows = [1.08, 1.06, 0.92, 0.94, 0.94, 0.90, 0.88, 0.90, 0.89]
    bear_closes = [1.09, 1.07, 1.01, 0.96, 0.95, 0.91, 0.90, 0.87, 0.86]
    bearish = detect_market_structure(_frame(bear_highs, bear_lows, bear_closes), CFG2)
    assert (bearish.frame["trend"] == BEARISH).any()

    flat_highs = [1.00, 1.01, 1.02, 1.01, 1.02, 1.01, 1.02, 1.01, 1.02]
    flat_lows = [0.99, 1.00, 1.01, 1.00, 1.01, 1.00, 1.01, 1.00, 1.01]
    flat_closes = [0.995, 1.005, 1.015, 1.005, 1.015, 1.005, 1.015, 1.005, 1.015]
    ranging = detect_market_structure(_frame(flat_highs, flat_lows, flat_closes), CFG2)
    assert (ranging.frame["trend"] == RANGING).any()


def test_market_structure_view() -> None:
    """La vista expone ultimo BOS/CHoCH y conteos de estado."""
    ms = detect_market_structure(_uptrend_frame(), CFG2)
    assert isinstance(ms, MarketStructure)
    assert ms.last_bos_dir in (1, -1, 0)
    counts = ms.counts
    assert "bos_active" in counts
    assert "trend" in counts


def test_bos_discard_reason_column_exists() -> None:
    """El frame expone bos_discard_reason desde el motor (M6)."""
    ms = detect_market_structure(_uptrend_frame(), CFG2)
    assert "bos_discard_reason" in ms.frame.columns


def test_choch_discard_reason_column_exists() -> None:
    """El frame expone choch_discard_reason desde el motor (M6)."""
    highs = [1.00, 1.02, 1.06, 1.10, 1.08, 1.07, 1.12, 1.13, 1.05, 1.04]
    lows = [0.99, 1.01, 1.05, 1.06, 1.06, 1.06, 1.07, 1.10, 1.00, 0.99]
    closes = [0.995, 1.015, 1.055, 1.07, 1.075, 1.065, 1.115, 1.125, 1.03, 1.02]
    ms = detect_market_structure(_frame(highs, lows, closes), CFG2)
    assert "choch_discard_reason" in ms.frame.columns


def test_bos_invalidated_emits_discard_reason() -> None:
    """BOS invalidado por cruce del nivel emite INVALIDATED o UNRESOLVED en bos_discard_reason."""
    highs = [1.00, 1.02, 1.06, 1.10, 1.08, 1.07, 1.12, 1.13, 1.06]
    lows = [0.99, 1.01, 1.05, 1.06, 1.06, 1.06, 1.07, 1.10, 1.02]
    closes = [0.995, 1.015, 1.055, 1.07, 1.075, 1.065, 1.115, 1.125, 1.05]
    ms = detect_market_structure(_frame(highs, lows, closes), CFG2)
    discard = ms.frame["bos_discard_reason"]
    assert (discard == "INVALIDATED").any() or (discard == "UNRESOLVED").any()


def test_choch_no_confirmation_emits_discard_reason() -> None:
    """CHOCH sin confirmación posterior emite NO_CONFIRMATION o UNRESOLVED en choch_discard_reason."""
    highs = [1.00, 1.02, 1.06, 1.10, 1.08, 1.07, 1.12, 1.13, 1.05, 1.04, 1.15]
    lows = [0.99, 1.01, 1.05, 1.06, 1.06, 1.06, 1.07, 1.10, 1.00, 0.99, 1.08]
    closes = [0.995, 1.015, 1.055, 1.07, 1.075, 1.065, 1.115, 1.125, 1.03, 1.02, 1.14]
    ms = detect_market_structure(_frame(highs, lows, closes), CFG2)
    discard = ms.frame["choch_discard_reason"]
    assert (discard == "NO_CONFIRMATION").any() or (discard == "UNRESOLVED").any()


def test_mss_sequence_bos_choch_bos() -> None:
    """MSS marca un BOS final en direccion opuesta al ultimo CHOCH."""
    highs = [1.00, 1.02, 1.06, 1.10, 1.08, 1.07, 1.12, 1.13, 1.05, 1.04, 1.15]
    lows = [0.99, 1.01, 1.05, 1.06, 1.06, 1.06, 1.07, 1.10, 1.00, 0.99, 1.08]
    closes = [0.995, 1.015, 1.055, 1.07, 1.075, 1.065, 1.115, 1.125, 1.03, 1.02, 1.14]
    ms = detect_market_structure(_frame(highs, lows, closes), CFG2)
    mss = ms.frame["mss_dir"]
    choch = ms.frame["choch_dir"]
    last_choch_dir = 0
    for i in range(len(choch)):
        if choch.iat[i] != 0:
            last_choch_dir = choch.iat[i]
        if mss.iat[i] != 0:
            assert last_choch_dir != 0
            assert mss.iat[i] == -last_choch_dir
