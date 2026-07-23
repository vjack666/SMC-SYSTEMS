"""Tests de las funciones PURAS de formato de la UI (Fase 5 deuda UI).

NO importa PySide6 — solo app_observador.ui.format_helpers (que a su vez
solo importa constantes de color de theme.py). Corre en headless.
"""
from app_observador.ui.format_helpers import (
    format_poi,
    format_trigger,
    format_canonical,
    canonical_is_ready,
    EN_CONSTRUCCION,
)
from app_observador.ui.theme import GREEN, TEXT_DIM, TEXT_MUTED


# --------------------------------------------------------------- format_poi
def test_format_poi_t1_anclado_apilado_bonus():
    ca = {
        "poi_tier": "T1",
        "poi_anchored": True,
        "poi_stacked": True,
        "poi_quality_bonus": 20,
    }
    out = format_poi(ca)
    assert "T1" in out
    assert "+20" in out
    assert "anclado" in out
    assert "apilado" in out


def test_format_poi_skip_bonus_cero():
    ca = {
        "poi_tier": "SKIP",
        "poi_anchored": False,
        "poi_stacked": False,
        "poi_quality_bonus": 0,
        "poi_tier_note": "SKIP wrong-side",
    }
    out = format_poi(ca)
    assert "SKIP" in out
    assert "+0" in out
    assert "anclado" not in out
    assert "apilado" not in out


def test_format_poi_ausente_en_construccion():
    assert EN_CONSTRUCCION in format_poi({})
    assert EN_CONSTRUCCION in format_poi(None)
    assert EN_CONSTRUCCION in format_poi({"poi": "VALID"})  # sin poi_tier


# ------------------------------------------------------------- format_trigger
def test_format_trigger_todos_los_estados():
    assert format_trigger("PENDING") == "TRIGGER: esperando"
    assert format_trigger("STRUCTURE_READY") == "TRIGGER: estructura lista"
    assert format_trigger("WAITING_PULLBACK") == "TRIGGER: esperando retroceso"
    assert format_trigger("TRIGGER_READY") == "TRIGGER: ✅ LISTO (en killzone)"
    assert format_trigger("TRIGGER_READY_OFF_SESSION") == "TRIGGER: ⏳ listo fuera de killzone"


def test_format_trigger_none_en_construccion():
    assert EN_CONSTRUCCION in format_trigger(None)
    assert EN_CONSTRUCCION in format_trigger("")
    assert EN_CONSTRUCCION in format_trigger("ESTADO_DESCONOCIDO")


# ------------------------------------------------------------ format_canonical
def test_format_canonical_dict_plan_verde():
    can = {"side": "LONG", "entry": 1.08500, "sl": 1.08000, "tp": 1.09500, "rr": 2.0}
    texto, color = format_canonical(can)
    assert "LONG" in texto
    assert "1.08500" in texto
    assert color == GREEN


def test_format_canonical_en_construccion_gris():
    texto, color = format_canonical(EN_CONSTRUCCION)
    assert "calculando" in texto
    assert color == TEXT_MUTED


def test_format_canonical_none_sin_plan_dim():
    texto, color = format_canonical(None)
    assert texto == "sin plan vigente"
    assert color == TEXT_DIM


# ---------------------------------------------------------- canonical_is_ready
def test_canonical_is_ready_dict_true():
    assert canonical_is_ready({"side": "LONG", "entry": 1.085}) is True


def test_canonical_is_ready_dict_sin_entry_false():
    assert canonical_is_ready({"side": "LONG"}) is False


def test_canonical_is_ready_en_construccion_false():
    assert canonical_is_ready(EN_CONSTRUCCION) is False


def test_canonical_is_ready_none_false():
    assert canonical_is_ready(None) is False
