"""Tests del cableado --model (fork a, 2026-07-23): el flag NO es engañoso.

Dos niveles:
  1) test unitario rapido de filter_signals_by_model (sin cargar datos):
     verifica que model="po3" deja solo senales con po3_complete is True,
     y que intradia/scalping no filtran.
  2) test de integracion de call-site real (evaluate_signals sobre datos
     EURUSD) marcado @pytest.mark.slow: corre el motor canonico completo y
     confirma que el filtro se aplica en el CALL SITE real. Es lento
     (~minutos, carga todos los TF) -> se salta por defecto; correr con
     `pytest -m slow` o via Runner Monitor.

Regla Ruben: un refactor de produccion se prueba por el CALL SITE real.
El (2) es esa prueba; el (1) da evidencia instantanea del comportamiento
del flag mientras el (2) corre en background.
"""
import types

import pytest

import ict_backtest.canonical as canonical
from ict_backtest.canonical import evaluate_signals, filter_signals_by_model
from ict_backtest.engine import ICTSignal


def _mk(po3_complete):
    # ICTSignal es dataclass; solo necesitamos po3_complete para el filtro.
    return ICTSignal(symbol="X", time="2020-01-01", direction=1, entry=1.0,
                     stop_loss=0.9, take_profit=1.3, po3_complete=po3_complete)


def test_filter_po3_keeps_only_complete():
    sigs = [_mk(True), _mk(False), _mk(True), _mk(None)]
    out = filter_signals_by_model(sigs, "po3")
    assert len(out) == 2
    assert all(s.po3_complete is True for s in out)


def test_filter_intradia_noop():
    sigs = [_mk(True), _mk(False), _mk(None)]
    out = filter_signals_by_model(sigs, "intradia")
    assert out == sigs  # regresion cero: sin filtro


def test_filter_scalping_noop():
    sigs = [_mk(True), _mk(False)]
    out = filter_signals_by_model(sigs, "scalping")
    assert out == sigs  # scalping resuelve exec_tf en el runner, no filtra aqui


def test_filter_unknown_model_noop():
    sigs = [_mk(True), _mk(False)]
    out = filter_signals_by_model(sigs, "desconocido")
    assert out == sigs


# ---------------------------------------------------------------------------
# Integracion: CALL SITE REAL (lento). Se salta por defecto.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def frames():
    from ict_backtest.data_feed import load_frames
    TF = ("D1", "H4", "H1", "M15", "M5", "M1")
    raw = load_frames("EURUSD", TF)
    # Recorte a 1 mes a mano (evita tz-mismatch de load_frames(start=)).
    import pandas as pd
    cutoff = None
    for tf in TF:
        t = raw[tf]["time"].iloc[-1]
        if getattr(t, "tzinfo", None) is not None:
            t = t.tz_localize(None)
        cutoff = t - pd.DateOffset(days=10)
        break
    out = {}
    for tf, df in raw.items():
        col = df["time"]
        if getattr(col.iloc[0], "tzinfo", None) is not None:
            out[tf] = df[df["time"] <= cutoff.tz_localize("UTC")]
        else:
            out[tf] = df[df["time"] <= cutoff]
    return out


def _run(model, frames):
    return evaluate_signals(
        "EURUSD", "H4", "M15",
        counter_trend=True, tp_mode="fixed2r",
        require_displacement=True, enable_pd_index=True,
        use_semantic=False, model=model,
        frames=frames,
    )


@pytest.mark.slow
def test_call_site_po3_filters_real(frames):
    intradia = _run("intradia", frames)
    po3 = _run("po3", frames)
    assert len(intradia) > 0
    assert len(po3) <= len(intradia)
    for s in po3:
        assert getattr(s, "po3_complete", None) is True


# ---------------------------------------------------------------------------
# Call-site REAL instantáneo: verifica que evaluate_signals propaga `model`
# hasta filter_signals_by_model SIN cargar el motor legacy (lento en HW).
# Monkeypatcheamos el motor/detectores para que el camino completo de
# evaluate_signals corra en <1s y confirmamos que el filtro se invoca
# con el modelo correcto (eslabón que faltaba cerrar empíricamente).
# ---------------------------------------------------------------------------
def test_evaluate_signals_propagates_model_to_filter(monkeypatch):
    import pandas as pd

    calls = []
    def _fake_filter(signals, model):
        calls.append((len(signals), model))
        return signals
    monkeypatch.setattr(canonical, "filter_signals_by_model", _fake_filter)
    # Motor legacy y detectors: no cargan datos reales (evita 40k barras).
    monkeypatch.setattr(canonical, "run_sequence", lambda *a, **k: ([], None))
    monkeypatch.setattr(canonical, "detect_market_structure", lambda df, *a, **k: df)
    monkeypatch.setattr(canonical, "extract_htf_layer", lambda *a, **k: {})
    # rng fake: avg_candle_range se llama temprano para STRUCT_SL_MAX_RANGE.
    monkeypatch.setattr(canonical, "avg_candle_range", lambda *a, **k: 0.001)

    df = pd.DataFrame({"time": pd.to_datetime(["2020-01-01"])})

    canonical.evaluate_signals("X", "M15", "M15", model="po3",
                              use_semantic=False, enable_pd_index=False,
                              frames={"M15": df})
    canonical.evaluate_signals("X", "M15", "M15", model="intradia",
                              use_semantic=False, enable_pd_index=False,
                              frames={"M15": df})

    models = [m for _, m in calls]
    assert models == ["po3", "intradia"], f"model no propagó al filtro: {models}"
