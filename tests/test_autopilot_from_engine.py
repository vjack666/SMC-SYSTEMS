"""RED: el semáforo de la pestaña Auto debe reflejar el motor grande
(engine.run_cycle) leyendo su cache, NO recalcular MT5/stochastic_signal.

Mapeo de las 4 luces al veredicto del motor:
  - extreme/cross/confirm  <- stoch_m15 (que el motor ya calcula)
  - trend (TENDENCIA A FAVOR) <- context_alignment ALIGNED del motor
  - confirm (SEÑAL FIRME)  <- trigger == READY + confidence alta
"""
import pytest
from PySide6.QtWidgets import QApplication
import app_observador.ui.autopilot_widget as aw


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def _fake_cache(extreme, cross, confirm, aligned, trigger, side="BUY", conf=0.7):
    return {
        "bias": "LONG (comprar)" if side == "BUY" else "SHORT (vender)",
        "veredicto": {
            "context_alignment": {
                "macro": "BULLISH" if side == "BUY" else "BEARISH",
                "intraday": "BULLISH" if side == "BUY" else "BEARISH",
                "poi": "OK",
                "trigger": trigger,
                "confidence": conf,
                "alignment": "ALIGNED" if aligned else "DIVERGENT",
            },
            "canonical_side": side,
        },
        "stoch_m15": {
            "k": 15.0 if extreme else 50.0,
            "d": 18.0 if extreme else 50.0,
            "extreme": extreme,
            "cross": cross,
            "confirm": confirm,
        },
    }


def test_all_green_when_engine_says_ready():
    w = aw.AutopilotWidget()
    cache = _fake_cache(
        extreme=True, cross=True, confirm=True,
        aligned=True, trigger="READY", side="BUY", conf=0.8,
    )
    states = w._lights_from_cache(cache)
    assert states == {"extreme": True, "cross": True, "confirm": True, "trend": True}


def test_trend_red_when_context_divergent():
    w = aw.AutopilotWidget()
    cache = _fake_cache(
        extreme=True, cross=True, confirm=True,
        aligned=False, trigger="READY", side="BUY", conf=0.8,
    )
    states = w._lights_from_cache(cache)
    assert states["trend"] is False
    assert states["extreme"] is True


def test_confirm_red_when_trigger_not_ready():
    w = aw.AutopilotWidget()
    cache = _fake_cache(
        extreme=True, cross=True, confirm=True,
        aligned=True, trigger="PENDING", side="BUY", conf=0.8,
    )
    states = w._lights_from_cache(cache)
    # SEÑAL FIRME (confirm) exige trigger READY del motor
    assert states["confirm"] is False


def test_extreme_red_when_stoch_not_in_zone():
    w = aw.AutopilotWidget()
    cache = _fake_cache(
        extreme=False, cross=False, confirm=False,
        aligned=True, trigger="READY", side="BUY", conf=0.8,
    )
    states = w._lights_from_cache(cache)
    assert states["extreme"] is False
    assert states["cross"] is False


def _details(cache):
    w = aw.AutopilotWidget()
    return w._phase_details(cache)


def test_phase_details_extreme_single_check():
    d = _details(_fake_cache(True, True, True, True, "READY", "BUY"))
    # Fase 1: 1 solo check (el motor solo expone el bool)
    assert d["extreme"] == [(True, "en zona (sobrecompra/sobreventa)")]


def test_phase_details_confirm_two_checks():
    # trigger PENDING -> segundo check en False (motor no autoriza)
    d = _details(_fake_cache(True, True, True, True, "PENDING", "BUY"))
    assert d["confirm"] == [
        (True, "cruce confirmado"),
        (False, "motor en READY"),
    ]


def test_phase_details_trend_two_checks():
    d = _details(_fake_cache(True, True, True, True, "READY", "BUY"))
    assert d["trend"] == [
        (True, "macro alineado (BULLISH)"),
        (True, "intraday alineado (BULLISH)"),
    ]


def test_phase_details_trend_divergent_shows_bearish():
    # contexto divergente (alignment != ALIGNED): ambos checks en False,
    # pero muestran el lado real que el motor reportó.
    d = _details(_fake_cache(True, True, True, False, "READY", "BUY"))
    assert d["trend"][0][0] is False
    assert d["trend"][1][0] is False
    assert "BULLISH" in d["trend"][0][1]
