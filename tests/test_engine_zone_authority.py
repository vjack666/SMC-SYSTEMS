"""Tests de engine.zone_authority — rescate de la autoridad de POI HTF.

Verifican: peso de confianza deterministico, niveles Alta/Media/Baja, rango [0,1],
y que sin ancla HTF el peso es 0.0 (no gate, solo percepcion).
"""

from __future__ import annotations

import pytest

from engine.htf_pd_index import HtfPdZone
from engine.zone_authority import ZoneAuthority, evaluate_zone_authority


def _zone(tf, tier, direction, hi=1.105, lo=1.100):
    return HtfPdZone(tf=tf, pd_type="OB", pd_tier=tier, direction=direction,
                     zone_high=hi, zone_low=lo)


def test_authority_no_ltf_zone():
    auth = evaluate_zone_authority(None, [])
    assert auth.has_htf_anchor is False
    assert auth.confidence_weight == 0.0
    assert auth.level == "Baja"


def test_authority_no_anchor():
    ltf = _zone("M15", "T2", 1)
    # anclas en direccion OPUESTA -> no cuenta como ancla
    auth = evaluate_zone_authority(ltf, [_zone("H4", "T2", -1)])
    assert auth.has_htf_anchor is False
    assert auth.confidence_weight == 0.0
    assert auth.level == "Baja"


def test_authority_single_anchor_media():
    ltf = _zone("M15", "T2", 1)
    auth = evaluate_zone_authority(ltf, [_zone("H4", "T2", 1)])
    # 1 ancla T2 (sin stacking bonus) => 0.5 + tier_bonus 0.15 = 0.65 -> Media
    assert auth.has_htf_anchor is True
    assert auth.tier == "T2"
    assert auth.stacking_level == 1
    assert auth.confidence_weight == 0.65
    assert auth.level == "Media"


def test_authority_stacking_alta():
    ltf = _zone("M15", "T2", 1)
    # 3 capas (D1/H4/H1) en T2 => 0.5 + tier 0.15 + stacking 0.2 = 0.85 -> Alta (>=0.8)
    auth = evaluate_zone_authority(
        ltf, [_zone("D1", "T2", 1), _zone("H4", "T2", 1), _zone("H1", "T2", 1)]
    )
    assert auth.stacking_level == 3
    assert auth.confidence_weight == 0.85
    assert auth.level == "Alta"


def test_authority_t1_alta():
    ltf = _zone("M15", "T2", 1)
    # 1 ancla T1 => 0.5 + 0.3 = 0.8 -> Alta
    auth = evaluate_zone_authority(ltf, [_zone("H4", "T1", 1)])
    assert auth.tier == "T1"
    assert auth.confidence_weight == 0.8
    assert auth.level == "Alta"


def test_authority_weight_in_range():
    ltf = _zone("M15", "T2", 1)
    auth = evaluate_zone_authority(
        ltf, [_zone("D1", "T1", 1), _zone("H4", "T2", 1), _zone("H1", "T2", 1)]
    )
    assert 0.0 <= auth.confidence_weight <= 1.0


def test_zone_authority_invariants():
    with pytest.raises(ValueError):
        ZoneAuthority(has_htf_anchor=True, tier="T2", stacking_level=1,
                      confidence_weight=1.5, level="Alta")
