"""Tests §5D del SDD: run_cycle two-pass (latencia M5/SMT aparte).

Verifican que:
  - El cache se escribe INMEDIATAMENTE tras el veredicto CORE (D1/H4/H1/M15,
    sin M5/SMT) = pass 1. El dashboard ve sesgo+POI+trigger rápido.
  - M5/SMT/canonical son enriquecimiento que RE-ESCRIBE el cache después.
  - Si M5/SMT fallan, el pass 1 produce veredicto honesto (trigger PENDING, sin inventar).
  - Si M5/SMT cargan, el veredicto final es el ENRIQUECIDO.
  - No rompe 5C: canonical acotado, cache siempre presente, 'EN CONSTRUCCIÓN'.

Aísla los pasos 1-5 mockeando engine._import_script + run_pipeline con fakes
mínimos, y redirige CACHE_PATH a tmp_path. No requiere MT5 ni ict_backtest reales.
"""
from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest

from app_observador.core import engine


# --- Fakes mínimos --------------------------------------------------------

class _FakeRutina:
    """Rutina que puede hacer fallar TFs específicos vía fail_tfs."""

    def __init__(self, fail_tfs=()):
        self.fail_tfs = set(fail_tfs)

    def _load(self, symbol, tf):
        if tf in self.fail_tfs:
            raise RuntimeError(f"sin datos {tf}")
        return SimpleNamespace(tf=tf)

    def analyze_timeframe(self, df, tf):
        return {
            "trend": "alcista", "bos_dir": 1, "bos_status": "confirmado",
            "bos_level": 1.1, "sweep_up": False, "sweep_down": False,
            "ote_long": (1.0, 1.05), "ote_short": (1.1, 1.15),
            "ob_dir": "bull", "fvg_state": "open", "choch_status": "-",
            "tf": tf,
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


def _make_modules(fail_tfs=()):
    return {
        "rutina_eurusd": _FakeRutina(fail_tfs),
        "news_report": _FakeNews(),
        "semaforo_fundednext": _FakeSemaforo(),
        "mapa_precio": _FakeMapa(),
        "fase_wyckoff_m15": _FakeWyckoff(),
    }


def _make_pipeline():
    """Pipeline fake que refleja si recibió M5/SMT en el veredicto.

    Pass 1 (core): m5=None, smt_b=None → trigger PENDING honesto.
    Pass 2 (enriquecido): m5 y smt presentes → trigger CONFIRMED + smt en veredicto.
    """
    def _pipe(d1, h4, h1, m15, m5=None, smt_a=None, smt_b=None, **kwargs):
        has_m5 = m5 is not None
        has_smt = smt_b is not None
        return {
            "bias": "LONG (comprar)",
            "votes": {"D1": 1, "H4": 1, "M15": 1},
            "context_alignment": {
                "macro": "ok", "intraday": "ok", "poi": "ok",
                "trigger": "CONFIRMED" if has_m5 else "PENDING",
                "confidence": 0.7,
            },
            "smt": "divergencia" if has_smt else None,
            "m5_used": has_m5,
        }
    return _pipe


@pytest.fixture
def patched_engine(tmp_path, monkeypatch):
    """Aísla pasos con fakes y redirige CACHE_PATH a tmp_path."""
    cache = tmp_path / "last_cycle.json"
    monkeypatch.setattr(engine, "CACHE_PATH", cache)
    monkeypatch.setattr(engine, "_import_script", lambda name: _MODS[name])
    monkeypatch.setattr(engine.decision_pipeline, "run_pipeline", _make_pipeline())
    # canonical vacío por defecto (rápido, honesto)
    monkeypatch.setattr(engine, "_canonical_plan", lambda s: None)
    return cache


# _MODS se reasigna por test para controlar fallos de M5/SMT
_MODS = _make_modules()


def _spy_writes(monkeypatch):
    """Intercepta _write_cache_atomic capturando snapshots de cada escritura."""
    snapshots = []
    orig = engine._write_cache_atomic

    def _spy(result):
        snapshots.append(json.loads(json.dumps(result, default=str)))
        orig(result)

    monkeypatch.setattr(engine, "_write_cache_atomic", _spy)
    return snapshots


# --- Tests §5D ------------------------------------------------------------

def test_pass1_escribe_cache_sin_m5(patched_engine, monkeypatch):
    """M5 falla, D1/H4/H1/M15 OK → pass 1 escribe cache con trigger PENDING
    honesto (no inventa M5). El cache existe al final."""
    global _MODS
    _MODS = _make_modules(fail_tfs=("M5",))
    snapshots = _spy_writes(monkeypatch)

    result = engine.run_cycle()

    # primera escritura (pass 1) = veredicto CORE, trigger PENDING (sin M5)
    assert snapshots, "no hubo escritura de cache"
    first = snapshots[0]
    assert first["veredicto"]["context_alignment"]["trigger"] == "PENDING"
    assert first["veredicto"].get("m5_used") is False  # no se inventó M5
    # cache final existe
    assert patched_engine.exists()
    # error M5 registrado (honesto)
    assert any("M5" in e for e in result["errores"])


def test_enriquecimiento_m5_reescribe(patched_engine, monkeypatch):
    """M5 y SMT cargan OK → el cache final tiene veredicto enriquecido
    (trigger CONFIRMED + smt). Debe haber 2+ escrituras atómicas."""
    global _MODS
    _MODS = _make_modules()  # nada falla
    snapshots = _spy_writes(monkeypatch)

    result = engine.run_cycle()

    # pass 1 = core (trigger PENDING); pass 2 = enriquecido (CONFIRMED)
    assert len(snapshots) >= 2, "esperaba >=2 escrituras (pass1 + enriquecimiento)"
    assert snapshots[0]["veredicto"]["context_alignment"]["trigger"] == "PENDING"
    # veredicto final enriquecido
    assert result["veredicto"]["context_alignment"]["trigger"] == "CONFIRMED"
    assert result["veredicto"]["smt"] == "divergencia"
    assert result["veredicto"]["m5_used"] is True


@pytest.mark.parametrize("modo", ["m5_falla", "m5_ok", "canonical_lento"])
def test_cache_siempre_presente_twopass(patched_engine, monkeypatch, modo):
    """Siempre CACHE_PATH.exists() y JSON parseable con 'veredicto'."""
    global _MODS
    if modo == "m5_falla":
        _MODS = _make_modules(fail_tfs=("M5",))
    else:
        _MODS = _make_modules()

    if modo == "canonical_lento":
        monkeypatch.setattr(engine, "CANONICAL_TIMEOUT_S", 1)

        def _slow(s):
            time.sleep(30)
            return None
        monkeypatch.setattr(engine, "_canonical_plan", _slow)

    engine.run_cycle()

    assert patched_engine.exists()
    data = json.loads(patched_engine.read_text(encoding="utf-8"))
    assert "veredicto" in data


def test_pass1_no_espera_canonical(patched_engine, monkeypatch):
    """El pass 1 ocurre ANTES del paso 6 (canonical). Con _canonical_plan lento,
    la primera escritura ya tiene veredicto core y canonical no está poblado."""
    global _MODS
    _MODS = _make_modules()
    monkeypatch.setattr(engine, "CANONICAL_TIMEOUT_S", 1)

    def _slow(s):
        time.sleep(30)
        return {"side": "long", "entry": 1, "sl": 1, "tp": 1, "rr": 1, "engine": "x"}
    monkeypatch.setattr(engine, "_canonical_plan", _slow)

    snapshots = _spy_writes(monkeypatch)

    t0 = time.time()
    result = engine.run_cycle()
    elapsed = time.time() - t0

    # pass 1 no espera canonical → primera escritura sin canonical poblado
    assert snapshots[0].get("canonical") in (None, "EN CONSTRUCCIÓN", "")
    # veredicto core presente en la primera escritura
    assert snapshots[0]["veredicto"]
    # canonical lento no bloquea (5C)
    assert elapsed < 6, f"run_cycle tardó {elapsed:.1f}s"
    assert result["canonical"] == "EN CONSTRUCCIÓN"


def test_regresion_5c(patched_engine, monkeypatch):
    """Canonical lento (5C) → run_cycle no se bloquea, cache presente,
    canonical 'EN CONSTRUCCIÓN'."""
    global _MODS
    _MODS = _make_modules()
    monkeypatch.setattr(engine, "CANONICAL_TIMEOUT_S", 1)

    def _slow(s):
        time.sleep(30)
        return {"side": "long", "entry": 1, "sl": 1, "tp": 1, "rr": 1, "engine": "x"}
    monkeypatch.setattr(engine, "_canonical_plan", _slow)

    t0 = time.time()
    result = engine.run_cycle()
    elapsed = time.time() - t0

    assert elapsed < 6
    assert patched_engine.exists()
    assert result["canonical"] == "EN CONSTRUCCIÓN"
    assert any("canonical" in e for e in result["errores"])


def test_sin_datos_core_return_temprano(patched_engine, monkeypatch):
    """D1 falla → run_cycle retorna temprano con error (comportamiento actual).
    No rompe (el 5D no cambia esto)."""
    global _MODS
    _MODS = _make_modules(fail_tfs=("D1",))

    result = engine.run_cycle()

    assert result["bias"] == "SIN DATOS MT5"
    assert any("D1" in e for e in result["errores"])
    assert result["veredicto"] == {}  # nunca llegó al pipeline
