"""Tests SDD §5B — poi_engine anclado y rankeado (libro 21).

POI = BONUS de calidad (cap 20), NUNCA filtro duro. Dicts sintéticos.
El test 3 es la GUARDIA anti A'' PF 0.900 (filtro duro).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app_observador"))

from app_observador.core.pipeline import poi_engine, run_pipeline


# --- helpers sintéticos ------------------------------------------------------
def _m15_long_ob_fvg(zone_low=1.0800, zone_high=1.0820):
    """M15 LONG con OB+FVG, OTE válido, BOS activo alcista."""
    return {
        "ob_dir": "bullish",
        "fvg_state": "bullish",
        "ote_long": (1.0805, 1.0815),
        "ote_short": (0.0, 0.0),
        "bos_dir": 1,
        "bos_status": "active",
        "zone_low": zone_low,
        "zone_high": zone_high,
    }


def _d1_discount():
    """D1 cuyo mid está por encima del POI M15 (POI en DISCOUNT)."""
    return {"zone_low": 1.0700, "zone_high": 1.1000}


def _d1_premium():
    """D1 cuyo mid está por debajo del POI M15 (POI en PREMIUM)."""
    return {"zone_low": 1.0600, "zone_high": 1.0700}


def _h4_bos_long():
    return {"bos_dir": 1, "bos_status": "active"}


def _h1_stack_long():
    """H1 alcista con zona que contiene la mid de la zona M15."""
    return {"bos_dir": 1, "trend": "BULLISH", "zone_low": 1.0790, "zone_high": 1.0830}


# --- 1 -----------------------------------------------------------------------
def test_t1_apilado_anclado():
    out = poi_engine(_m15_long_ob_fvg(), d1=_d1_discount(),
                     h4=_h4_bos_long(), h1=_h1_stack_long(), bias_side="LONG")
    assert out["valid"] is True
    assert out["tier"] == "T1"
    assert out["anchored"] is True
    assert out["stacked"] is True
    assert out["quality_bonus"] == 20


# --- 2 -----------------------------------------------------------------------
def test_sin_ancla_es_t2():
    # mismo caso pero sin BOS H4 (h4=None) y sin stacking (h1=None)
    out = poi_engine(_m15_long_ob_fvg(), d1=_d1_discount(),
                     h4=None, h1=None, bias_side="LONG")
    assert out["valid"] is True
    assert out["anchored"] is False
    # T1 (OB+FVG+displacement) → bonus 10 + 5 (zona+sesgo) = 12? No: +10+5=15.
    # El caso del SDD dice bonus=12 con FVG standalone (T2). Ajustamos a T2 standalone:
    # ver test dedicado. Aquí OB+FVG => T1 sin ancla => 10+5 = 15.
    assert out["quality_bonus"] == 15


def test_sin_ancla_fvg_standalone_es_t2():
    m15 = _m15_long_ob_fvg()
    m15["ob_dir"] = "-"  # solo FVG
    out = poi_engine(m15, d1=_d1_discount(), h4=None, h1=None, bias_side="LONG")
    assert out["valid"] is True
    assert out["tier"] == "T2"
    assert out["anchored"] is False
    assert out["quality_bonus"] == 12  # 7 (T2) + 5 (zona+sesgo)


# --- 3 (GUARDIA anti-filtro-duro) --------------------------------------------
def test_wrong_side_skip_no_gate():
    # OB LONG pero en PREMIUM con bias LONG → wrong-side
    out = poi_engine(_m15_long_ob_fvg(), d1=_d1_premium(),
                     h4=_h4_bos_long(), h1=None, bias_side="LONG")
    assert out["tier"] == "SKIP"
    assert out["quality_bonus"] == 0
    assert out["valid"] is True  # NUNCA anula la señal


# --- 4 -----------------------------------------------------------------------
def test_sin_d1_pending():
    out = poi_engine(_m15_long_ob_fvg(), d1=None,
                     h4=_h4_bos_long(), h1=None, bias_side="LONG")
    assert out["premium_discount"] == "PENDING"
    assert out["tier"] != "SKIP"
    # sin +5 de zona (cond_zona no evaluable): T1 (10) + 5 anchored = 15
    assert out["quality_bonus"] == 15


# --- 5 -----------------------------------------------------------------------
def test_sin_m15_pending():
    m15 = {
        "ob_dir": "-", "fvg_state": "-",
        "ote_long": (0.0, 0.0), "ote_short": (0.0, 0.0),
        "bos_dir": 0, "bos_status": "-",
        "zone_low": 0.0, "zone_high": 0.0,
    }
    out = poi_engine(m15, d1=_d1_discount(), bias_side="LONG")
    assert out["valid"] is False
    assert out["tier"] == "PENDING"
    assert out["quality_bonus"] == 0


# --- 6 -----------------------------------------------------------------------
def test_stacking_eleva_tier():
    # FVG standalone con displacement = T2; con stacking H1 → T1
    m15 = _m15_long_ob_fvg()
    m15["ob_dir"] = "-"  # solo FVG → T2 base
    out = poi_engine(m15, d1=_d1_discount(), h4=None,
                     h1=_h1_stack_long(), bias_side="LONG")
    assert out["stacked"] is True
    assert out["tier"] == "T1"  # T2 elevado por stacking


# --- 7 -----------------------------------------------------------------------
def test_confidence_suma_bonus_y_no_doble_pd():
    d1 = {"trend": "BULLISH", "zone_low": 1.0700, "zone_high": 1.1000}
    h4 = {"trend": "BULLISH", "bos_dir": 1, "bos_status": "active"}
    h1 = {"trend": "BULLISH", "bos_dir": 1, "zone_low": 1.0790, "zone_high": 1.0830}
    m15 = _m15_long_ob_fvg()

    out = run_pipeline(d1, h4, h1, m15)
    poi = out["poi"]
    assert poi["quality_bonus"] == 20
    ca = out["context_alignment"]
    # base: macro25+ctx25+intraday20+poi20 = 90; trigger 0; smt aligned +5 → 95; +20 bonus = 115
    from app_observador.core.pipeline import _confidence
    base = _confidence(True, True, True, True, False)
    # smt PENDING (sin smt_b) => smt_conf 0
    assert ca["confidence"] == base + 0 + 20
    # campos hermanos
    assert ca["poi_tier"] == "T1"
    assert ca["poi_quality_bonus"] == 20
    assert ca["poi_anchored"] is True
    assert ca["poi_stacked"] is True
    # string legado intacto
    assert ca["poi"] == "VALID"


def test_string_legado_poi_intacto_invalid():
    d1 = {"trend": "RANGING", "zone_low": 0, "zone_high": 0}
    h4 = {"trend": "RANGING"}
    h1 = {"trend": "RANGING"}
    m15 = {"ob_dir": "-", "fvg_state": "-", "ote_long": (0.0, 0.0),
           "ote_short": (0.0, 0.0), "bos_dir": 0, "bos_status": "-",
           "zone_low": 0.0, "zone_high": 0.0}
    out = run_pipeline(d1, h4, h1, m15)
    assert out["context_alignment"]["poi"] == "INVALID"
