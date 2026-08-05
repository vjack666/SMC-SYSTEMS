"""Tests de la memoria de cruce del semáforo (reglas R1-R5).

El semáforo lee el cache del motor (single source of truth para los VALORES)
pero recuerda el EVENTO del cruce K/D entre ticks (el motor es stateless
por ciclo y el cache solo mira la vela actual). Esto evita que el cruce
"se borre de la memoria" cuando el precio sale de la zona.

Reglas:
  R1 EXTREMO  — luz ON si está en zona AHORA o si hubo cruce vigente
                  (memoria) y aún no expira.
  R2 CRUCE    — registrar lado (BULL/BEAR) y mantenerlo vigente.
  R3 TENDENCIA — lado del cruce vs bias del motor -> "a favor" o
                  "retroceso contra tendencia" (se indica en el monitor).
  R5 CADUCIDAD— memoria expira a 12 ticks (~60s).
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from app_observador.ui.autopilot_widget import AutopilotWidget


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def _widget():
    w = AutopilotWidget.__new__(AutopilotWidget)
    w._k_prev = None
    w._d_prev = None
    w._cross_latch = None
    return w


def _cache(cross, extreme, k, d, macro="BULLISH", trigger="READY"):
    return {
        "bias": f"{'LONG' if macro == 'BULLISH' else 'SHORT'} (comprar)",
        "veredicto": {
            "context_alignment": {
                "macro": macro,
                "intraday": macro,
                "trigger": trigger,
                "alignment": "ALIGNED",
            }
        },
        "stoch_m15": {"k": float(k), "d": float(d), "extreme": extreme, "cross": cross},
    }


def test_latch_records_bull_cross():
    w = _widget()
    states, _ = w._build_state(_cache(cross=True, extreme=True, k=25, d=20))
    assert w._cross_latch is not None
    assert w._cross_latch["side"] == "BULL"
    assert states["cross"] is True


def test_latch_keeps_when_price_returns_to_zone():
    w = _widget()
    # tick 1: cruce bull en zona
    w._build_state(_cache(cross=True, extreme=True, k=25, d=20))
    # tick 2: ya no hay cruce nuevo, pero precio sigue en zona (retornó)
    states, _ = w._build_state(_cache(cross=False, extreme=True, k=30, d=28))
    # el cruce NO se borró de la memoria
    assert w._cross_latch is not None
    assert w._cross_latch["side"] == "BULL"
    assert states["cross"] is True
    assert states["extreme"] is True


def test_latch_expires_after_12_ticks():
    w = _widget()
    w._build_state(_cache(cross=True, extreme=True, k=25, d=20))  # age 0
    # 13 ticks sin cruce y sin zona -> expira (age llega a 13 > 12)
    for _ in range(13):
        w._build_state(_cache(cross=False, extreme=False, k=50, d=50))
    assert w._cross_latch is None


def test_retroceso_against_trend_flagged():
    w = _widget()
    # cruce BULL pero el motor dice BEARISH -> retroceso contra tendencia
    w._build_state(_cache(cross=True, extreme=True, k=25, d=20, macro="BEARISH"))
    _, details = w._build_state(_cache(cross=False, extreme=True, k=30, d=28, macro="BEARISH"))
    retro = [(ok, t) for (ok, t) in details["trend"] if "RETROCESO" in t]
    assert retro, "debe indicar retroceso en el monitor"
    assert retro[0][0] is False  # en rojo


def test_favor_trend_when_side_matches_bias():
    w = _widget()
    # cruce BEAR y motor BEARISH -> a favor de tendencia
    w._build_state(_cache(cross=True, extreme=True, k=20, d=25, macro="BEARISH"))
    _, details = w._build_state(_cache(cross=False, extreme=True, k=22, d=26, macro="BEARISH"))
    favor = [(ok, t) for (ok, t) in details["trend"] if "a favor" in t]
    assert favor, "debe indicar a favor de tendencia"
    assert favor[0][0] is True  # en verde
