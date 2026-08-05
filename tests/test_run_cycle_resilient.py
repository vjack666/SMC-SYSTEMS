"""Tests §5C del SDD: run_cycle resiliente.

Verifican que:
  - last_cycle.json SIEMPRE se escribe (cache atómico) con veredicto honesto.
  - el paso 6 (canonical R7) está acotado en tiempo (ThreadPoolExecutor + timeout).
  - los 3 estados honestos de canonical: 'EN CONSTRUCCIÓN' / None / dict.
  - el veredicto (votos D1/H4/M15) NUNCA se reescribe con canonical.

Aísla los pasos 1-5 mockeando engine._import_script + run_pipeline con fakes
mínimos, y mockea engine._canonical_plan para dirigir el comportamiento del paso 6.
No requiere MT5 ni ict_backtest reales.
"""
from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest

from app_observador.core import engine


# --- Fakes mínimos para los pasos 1-5 -------------------------------------

class _FakeRutina:
    def _load(self, symbol, tf):
        return SimpleNamespace(tf=tf)  # "df" opaco; analyze no lo usa de verdad

    def analyze_timeframe(self, df, tf):
        return {
            "trend": "alcista", "bos_dir": 1, "bos_status": "confirmado",
            "bos_level": 1.1, "sweep_up": False, "sweep_down": False,
            "ote_long": (1.0, 1.05), "ote_short": (1.1, 1.15),
            "ob_dir": "bull", "fvg_state": "open", "choch_status": "-",
        }

    def compute_trade_plan(self, verdict, m15):
        return {"entry": 1.10, "sl": 1.09, "tp": 1.12}


class _FakeNews:
    def load_events(self, no_fetch=True):
        return ([], "cache")


class _FakeSemaforo:
    def evaluate(self, bias, noticias, trade_plan):
        return ("VERDE", ["ok"])


class _FakeMapa:
    def save_tf_png(self, symbol, tf, df, info, maps_dir):
        return f"/tmp/{symbol}_{tf}.png"


class _FakeWyckoff:
    def fase_actual(self, symbol, tf):
        return {"phase_es": "acumulacion", "bias": "alcista"}


_FAKE_MODULES = {
    "rutina_eurusd": _FakeRutina(),
    "news_report": _FakeNews(),
    "semaforo_fundednext": _FakeSemaforo(),
    "mapa_precio": _FakeMapa(),
    "fase_wyckoff_m15": _FakeWyckoff(),
}

# Veredicto de referencia: votos que NO deben cambiar por canonical.
_BASE_VERDICT = {
    "bias": "LONG (comprar)",
    "votes": {"D1": 1, "H4": 1, "M15": 1},
    "context_alignment": {"macro": "ok", "intraday": "ok",
                          "poi": "ok", "trigger": "ok", "confidence": 0.7},
}


@pytest.fixture
def patched_engine(tmp_path, monkeypatch):
    """Aísla pasos 1-5 con fakes y redirige CACHE_PATH a tmp_path."""
    cache = tmp_path / "last_cycle.json"
    monkeypatch.setattr(engine, "CACHE_PATH", cache)

    monkeypatch.setattr(engine, "_import_script",
                        lambda name: _FAKE_MODULES[name])

    def _fake_pipeline(*a, **k):
        return dict(_BASE_VERDICT)

    monkeypatch.setattr(engine.decision_pipeline, "run_pipeline", _fake_pipeline)
    return cache


# --- Tests §5C ------------------------------------------------------------

def test_canonical_lento_no_bloquea_cache(patched_engine, monkeypatch):
    """Mock sleep(30), CANONICAL_TIMEOUT_S=1 → retorna ~rápido, cache vivo,
    veredicto poblado, canonical == 'EN CONSTRUCCIÓN', error registrado."""
    cache = patched_engine
    monkeypatch.setattr(engine, "CANONICAL_TIMEOUT_S", 1)

    def _slow(symbol):
        time.sleep(30)
        return {"side": "long", "entry": 1, "sl": 1, "tp": 1, "rr": 1, "engine": "x"}

    monkeypatch.setattr(engine, "_canonical_plan", _slow)

    t0 = time.time()
    result = engine.run_cycle()
    elapsed = time.time() - t0

    assert elapsed < 5, f"run_cycle tardó {elapsed:.1f}s (debía cortar ~1s)"
    assert cache.exists()
    assert result["veredicto"]  # veredicto honesto poblado
    assert result["canonical"] == "EN CONSTRUCCIÓN"
    assert any("canonical" in e for e in result["errores"])


def test_canonical_excepcion_deja_en_construccion(patched_engine, monkeypatch):
    cache = patched_engine

    def _boom(symbol):
        raise RuntimeError("boom canonical")

    monkeypatch.setattr(engine, "_canonical_plan", _boom)

    result = engine.run_cycle()

    assert cache.exists()
    assert result["canonical"] == "EN CONSTRUCCIÓN"
    # veredicto intacto: votos originales
    assert result["veredicto"]["votes"] == _BASE_VERDICT["votes"]
    assert any("canonical" in e for e in result["errores"])


def test_canonical_ok_enriquece(patched_engine, monkeypatch):
    plan = {"side": "long", "entry": 1.10, "sl": 1.09, "tp": 1.13,
            "rr": 3.0, "engine": "R7"}
    monkeypatch.setattr(engine, "_canonical_plan", lambda s: dict(plan))

    result = engine.run_cycle()

    assert result["canonical"] == plan
    assert result["veredicto"]["invalidation"] == plan["sl"]
    assert result["veredicto"]["target"] == plan["tp"]
    assert result["veredicto"]["canonical_entry"] == plan["entry"]
    # votos SIN cambios
    assert result["veredicto"]["votes"] == _BASE_VERDICT["votes"]


def test_canonical_none_honesto(patched_engine, monkeypatch):
    monkeypatch.setattr(engine, "_canonical_plan", lambda s: None)
    result = engine.run_cycle()
    assert result["canonical"] is None


@pytest.mark.parametrize("modo", ["lento", "excepcion", "none", "ok"])
def test_cache_siempre_presente(patched_engine, monkeypatch, modo):
    cache = patched_engine
    monkeypatch.setattr(engine, "CANONICAL_TIMEOUT_S", 1)

    if modo == "lento":
        def _f(s):
            time.sleep(30)
            return None
    elif modo == "excepcion":
        def _f(s):
            raise RuntimeError("x")
    elif modo == "none":
        def _f(s):
            return None
    else:  # ok
        def _f(s):
            return {"side": "long", "entry": 1.1, "sl": 1.0,
                    "tp": 1.2, "rr": 2.0, "engine": "R7"}

    monkeypatch.setattr(engine, "_canonical_plan", _f)

    engine.run_cycle()

    assert cache.exists()
    data = json.loads(cache.read_text(encoding="utf-8"))
    assert "veredicto" in data


def test_write_atomico_sin_json_parcial(patched_engine, monkeypatch):
    cache = patched_engine
    monkeypatch.setattr(engine, "_canonical_plan",
                        lambda s: {"side": "long", "entry": 1.1, "sl": 1.0,
                                   "tp": 1.2, "rr": 2.0, "engine": "R7"})

    engine.run_cycle()

    # nunca queda el .tmp
    tmp = cache.with_suffix(".json.tmp")
    assert not tmp.exists()
    # el JSON final siempre parsea
    json.loads(cache.read_text(encoding="utf-8"))
