"""Tests Fase C4 (TDD) — fidelidad §5 del diseno: el peso de confianza
ORDENA correctamente zonas de distinta calidad contextual.

La metrica de Fase C NO es PF (no se evalúa por retorno). Se evalua por
FIDELIDAD (ROADMAP_TESIS_DRIVEN §5, regla de oro "se acepta por fidelidad
no PF"): el peso de confianza debe reflejar la jerarquia ICT objetiva
(libro 21 §2): T1 (BPR) > T2 (FVG/OB) > T3 (rejection), y stacking multi-TF
(suben el mismo POI en D1+H4) debe pesar mas que un solo TF.

Este test es el subconjunto etiquetado del plan §5: zonas con ancla HTF
conocida (Alta/Media/Baja) y verificacion de monotonicidad del peso.
"""

import pandas as pd
import pytest

from ict_backtest.htf_pd_index import HtfPdZone
from ict_backtest.zone_authority import evaluate_zone_authority


def _zone(pd_type, pd_tier, direction=1, high=1.0, low=0.9):
    return HtfPdZone(tf="H4", pd_type=pd_type, pd_tier=pd_tier,
                     direction=direction, zone_high=high, zone_low=low)


def test_tier_ordering_t1_above_t2_above_t3():
    """Jerarquia ICT objetiva: BPR (T1) > FVG (T2) > REJECTION (T3).

    Misma zona LTF, mismo ancla unico HTF: el peso debe respetar T1>T2>T3.
    """
    base = _zone("FVG", "T2")
    t1 = _zone("BPR", "T1")          # mismo ancla pero BPR (maxima autoridad)
    t3 = _zone("REJECTION_BLOCK", "T3")

    w_base = evaluate_zone_authority(base, [base]).confidence_weight
    w_t1 = evaluate_zone_authority(t1, [t1]).confidence_weight
    w_t3 = evaluate_zone_authority(t3, [t3]).confidence_weight

    assert w_t1 > w_base, "T1 (BPR) debe pesar mas que T2 base"
    assert w_base > w_t3, "T2 debe pesar mas que T3 (rejection)"


def test_stacking_multi_tf_outranks_single():
    """Stacking: mismo POI anclado en D1 Y H4 pesa mas que solo H4.

    Esto valida que C captura la 'autoridad de multiples marcos' (tesis 18:
    capas HTF+ITF), no solo la presencia aislada en un TF.
    """
    single = [_zone("FVG", "T2", high=1.0, low=0.9)]  # ancla solo en H4
    stacked = [
        _zone("FVG", "T2", high=1.0, low=0.9),                       # H4
        HtfPdZone("D1", "FVG", "T2", 1, 1.0, 0.9),                   # D1 mismo POI
    ]
    w_single = evaluate_zone_authority(single[0], single).confidence_weight
    w_stack = evaluate_zone_authority(stacked[0], stacked).confidence_weight
    assert w_stack > w_single, "stacking multi-TF debe pesar mas que un solo TF"


def test_labeled_quality_monotonicity():
    """Subconjunto etiquetado §5: Zona Alta > Media > Baja en peso.

    Etiquetas objetivas (no subjetivas): Alta = BPR + stacking D1/H4;
    Media = FVG unico HTF; Baja = sin ancla HTF.
    """
    zona_baja = _zone("FVG", "T2")
    autoridad_baja = evaluate_zone_authority(zona_baja, []).confidence_weight  # sin ancla

    zona_media = _zone("FVG", "T2")
    autoridad_media = evaluate_zone_authority(zona_media, [zona_media]).confidence_weight

    zona_alta = _zone("BPR", "T1")
    autoridad_alta = evaluate_zone_authority(zona_alta, [
        zona_alta,
        HtfPdZone("D1", "BPR", "T1", 1, 1.0, 0.9),
    ]).confidence_weight

    assert autoridad_baja < autoridad_media < autoridad_alta, (
        f"orden de calidad roto: baja={autoridad_baja} media={autoridad_media} "
        f"alta={autoridad_alta}"
    )


def test_no_anchor_is_lowest():
    """Sin ancla HTF, el peso es el minimo (Baja) — C no inventa autoridad."""
    z = _zone("FVG", "T2")
    auth = evaluate_zone_authority(z, [])
    assert auth.has_htf_anchor is False
    assert auth.level == "Baja"
    assert auth.confidence_weight == 0.0
