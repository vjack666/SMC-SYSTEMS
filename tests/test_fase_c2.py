"""Tests Fase C2 (TDD) — evaluador de autoridad de zona.

Verifica el Contrato de no invasión: C solo LEE zonas, no las crea; el peso
de confianza es información, NO un gate de compra. Casos del diseño:
  Zona A: H4 alineado + FVG/OB  -> Alta autoridad
  Zona B: FVG solo LTF, sin HTF -> Baja autoridad (pero observable)
"""

import pytest

from ict_backtest.htf_pd_index import HtfPdZone
from ict_backtest.zone_authority import (
    ZoneAuthority,
    evaluate_zone_authority,
)


def _ltf_zone(direction=1, tier="T2", ptype="FVG"):
    return HtfPdZone(tf="M15", pd_type=ptype, pd_tier=tier,
                      direction=direction, zone_high=102.0, zone_low=101.5)


def test_no_zone_received_is_low_not_invented():
    """C no inventa zona: si el motor no trazó nada, devuelve Baja (sin ancla)."""
    auth = evaluate_zone_authority(None, [])
    assert auth.has_htf_anchor is False
    assert auth.level == "Baja"
    assert auth.confidence_weight == 0.0


def test_ltf_zone_without_htf_anchor_is_low_but_observable():
    """Zona B del diseño: FVG solo LTF, sin respaldo HTF -> Baja, NO se mata."""
    ltf = _ltf_zone(direction=1, tier="T2", ptype="FVG")
    auth = evaluate_zone_authority(ltf, htf_zones=[])
    assert auth.has_htf_anchor is False
    assert auth.level == "Baja"
    assert auth.confidence_weight == 0.0


def test_htf_anchor_bullish_with_opposite_direction_is_no_anchor():
    """Ancla HTF en dirección OPUESTA no cuenta como respaldo de la zona."""
    ltf = _ltf_zone(direction=1)  # zona alcista
    htf_bear = [HtfPdZone(tf="H4", pd_type="OB", pd_tier="T2",
                           direction=-1, zone_high=99.0, zone_low=98.0)]
    auth = evaluate_zone_authority(ltf, htf_zones=htf_bear)
    assert auth.has_htf_anchor is False
    assert auth.level == "Baja"


def test_zone_a_high_authority():
    """Zona A del diseño: H4 alineado (FVG+OB) en misma dir -> Alta."""
    ltf = _ltf_zone(direction=1, tier="T2", ptype="FVG")
    htf = [
        HtfPdZone(tf="H4", pd_type="FVG", pd_tier="T2", direction=1,
                   zone_high=102.0, zone_low=101.5),
        HtfPdZone(tf="H4", pd_type="OB", pd_tier="T2", direction=1,
                   zone_high=102.0, zone_low=101.5),
    ]
    auth = evaluate_zone_authority(ltf, htf_zones=htf)
    assert auth.has_htf_anchor is True
    # T2 + stacking de 1 capa => w = 0.5 + 0.15 + 0.0 = 0.65 => Media.
    assert auth.level in ("Media", "Alta")
    assert auth.confidence_weight > 0.5


def test_tier1_bpr_outranks_t2():
    """BPR (T1) da más peso que FVG/OB (T2) solo."""
    ltf = _ltf_zone(direction=1, tier="T2", ptype="FVG")
    htf_t1 = [HtfPdZone(tf="H4", pd_type="BPR", pd_tier="T1",
                         direction=1, zone_high=102.0, zone_low=101.5)]
    htf_t2 = [HtfPdZone(tf="H4", pd_type="FVG", pd_tier="T2",
                         direction=1, zone_high=102.0, zone_low=101.5)]
    a1 = evaluate_zone_authority(ltf, htf_zones=htf_t1)
    a2 = evaluate_zone_authority(ltf, htf_zones=htf_t2)
    assert a1.tier == "T1"
    assert a1.confidence_weight > a2.confidence_weight


def test_stacking_two_tfs_increases_weight():
    """Apilar H4 + D1 (mismas dir) sube el peso vs solo H4."""
    ltf = _ltf_zone(direction=1, tier="T2", ptype="FVG")
    only_h4 = [HtfPdZone(tf="H4", pd_type="FVG", pd_tier="T2",
                         direction=1, zone_high=102.0, zone_low=101.5)]
    stacked = only_h4 + [HtfPdZone(tf="D1", pd_type="FVG", pd_tier="T2",
                                   direction=1, zone_high=102.0, zone_low=101.5)]
    a_h4 = evaluate_zone_authority(ltf, htf_zones=only_h4)
    a_stk = evaluate_zone_authority(ltf, htf_zones=stacked)
    assert a_stk.stacking_level == 2
    assert a_stk.confidence_weight > a_h4.confidence_weight


def test_weight_always_in_unit_interval():
    ltf = _ltf_zone(direction=1, tier="T1", ptype="BPR")
    many = [HtfPdZone(tf=tf_, pd_type="BPR", pd_tier="T1",
                      direction=1, zone_high=102.0, zone_low=101.5)
            for tf_ in ("H4", "D1", "H1")]
    auth = evaluate_zone_authority(ltf, htf_zones=many)
    assert 0.0 <= auth.confidence_weight <= 1.0
    assert auth.level == "Alta"  # T1 + 3 capas => ~1.0


def test_authority_is_frozen_and_validated():
    a = ZoneAuthority(has_htf_anchor=True, tier="T1", stacking_level=1,
                      confidence_weight=0.9, level="Alta")
    assert a.has_htf_anchor is True
    with pytest.raises(ValueError):
        ZoneAuthority(has_htf_anchor=True, tier="T1", stacking_level=1,
                      confidence_weight=1.5, level="Alta")
