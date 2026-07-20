"""tests/test_po3_motor.py — Brecha E (Opción 2): tests de compute_po3_complete.

Patrón Brecha B (tests/test_fase_c*.py): funciones PURAS, datos sintéticos,
SIN leer data/raw/*.parquet. Verifica el contrato del motor:

  - ciclo PO3/AMD COMPLETO           -> True
  - ciclo INCOMPLETO / judas        -> False
  - sin datos de estructura         -> None  (comportamiento histórico intacto)

Principio Brecha D: compute_po3_complete es ANOTACIÓN (no filtra), por eso
los tres casos devuelven bool|None sin tocar el conteo de señales de nadie.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from ict_backtest.po3_motor import Po3MotorConfig, compute_po3_complete


# --- Estructuras sintéticas (misma forma que consume signals.po3.build_po3_state) ---

def _complete_bullish_po3() -> dict:
    """Ciclo PO3 BULLISH COMPLETO: A (sesgo) + M (sweep down) + D (BOS+FVG) alineado."""
    return {
        "H4": {"trend": "BULLISH", "sweep_up": False, "sweep_down": False},
        "M15": {
            "trend": "BULLISH",
            "sweep_up": False,
            "sweep_down": True,              # M: manipulación en contra del sesgo
            "bos_dir": 1,
            "bos_status": "active",           # D: BOS alcista activo (a favor)
            "choch_status": "-",
            "fvg_state": "FVG",               # D: zona FVG presente
            "ob_dir": "-",
        },
    }


def _incomplete_judas_po3() -> dict:
    """Ciclo INCOMPLETO: hay sesgo y sweep (M) pero NO hay D (sin BOS/FVG a favor)."""
    return {
        "H4": {"trend": "BULLISH", "sweep_up": False, "sweep_down": False},
        "M15": {
            "trend": "BULLISH",
            "sweep_up": False,
            "sweep_down": True,              # M ok
            "bos_dir": 0,
            "bos_status": "no",              # D: sin BOS
            "choch_status": "-",
            "fvg_state": "-",                # D: sin FVG/OB
            "ob_dir": "-",
        },
    }


def _neutral_no_bias() -> dict:
    """Sin sesgo HTF: fase A ni siquiera arranca -> judas / incompleto -> False."""
    return {
        "H4": {"trend": "RANGING", "sweep_up": False, "sweep_down": False},
        "M15": {
            "trend": "RANGING",
            "sweep_up": True,
            "sweep_down": True,
            "bos_dir": 1,
            "bos_status": "active",
            "choch_status": "-",
            "fvg_state": "FVG",
            "ob_dir": "-",
        },
    }


# --- Tests del contrato ---

def test_po3_complete_ciclo_amd_completo_devuelve_true():
    cfg = Po3MotorConfig(bias="BULLISH", exec_tf="M15", htf="H4")
    out = compute_po3_complete(_complete_bullish_po3(), config=cfg)
    assert out is True, f"esperado True para ciclo PO3 completo, got {out}"


def test_po3_incompleto_judas_devuelve_false():
    cfg = Po3MotorConfig(bias="BULLISH", exec_tf="M15", htf="H4")
    out = compute_po3_complete(_incomplete_judas_po3(), config=cfg)
    assert out is False, f"esperado False para ciclo incompleto/judas, got {out}"


def test_po3_sin_bias_devuelve_false():
    cfg = Po3MotorConfig(bias="NEUTRAL", exec_tf="M15", htf="H4")
    out = compute_po3_complete(_neutral_no_bias(), config=cfg)
    assert out is False, f"esperado False sin sesgo HTF, got {out}"


def test_po3_sin_datos_devuelve_none():
    # Sin estructura -> None (modo histórico intacto, no se anota ni filtra).
    assert compute_po3_complete(None) is None
    assert compute_po3_complete({}) is None


def test_po3_config_por_defecto_funciona():
    # Con config None usa defaults; el dict completo sigue dando True vía bias del dict.
    # (build_po3_state usa bias que pasamos; si no lo pasamos, A≠True => False)
    out = compute_po3_complete(_complete_bullish_po3(), config=None)
    # Sin bias explícito en config, _phase_a da False -> complete False.
    assert out is False, f"sin bias en config, PO3 no puede completarse: got {out}"


def test_po3_delega_en_build_po3_state(monkeypatch):
    """Aisla el motor: con build_po3_state mockeado, delega y devuelve lo que diga."""
    from ict_backtest.po3_motor import build_po3_state as _real

    calls = {}

    def _fake(structure_data, bias, votes=None, exec_tf="M15", htf="H4"):
        calls["called"] = True
        calls["bias"] = bias
        # State fake con complete=True
        class _S:
            complete = True
        return _S()

    monkeypatch.setattr("ict_backtest.po3_motor.build_po3_state", _fake)
    cfg = Po3MotorConfig(bias="BULLISH")
    out = compute_po3_complete({"M15": {}}, config=cfg)
    assert calls.get("called") is True, "el motor no delegó en build_po3_state"
    assert calls["bias"] == "BULLISH"
    assert out is True
