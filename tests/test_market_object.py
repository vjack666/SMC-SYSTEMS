import pytest

from ict_backtest.market_object import (
    MarketObject,
    ObjectType,
    Role,
    ObjectState,
)


def test_origin_tf_obligatorio():
    with pytest.raises(TypeError):
        MarketObject(type=ObjectType.FVG, role=Role.REFINEMENT)


def test_poi_solo_en_htf():
    with pytest.raises(ValueError):
        MarketObject(type=ObjectType.FVG, origin_tf="M15", role=Role.POI)


def test_estado_inicial():
    o = MarketObject(
        type=ObjectType.BOS, origin_tf="H4", role=Role.CONTEXT, direction=1
    )
    assert o.state == ObjectState.CREATED
    assert o.parent_object is None
    assert o.related_objects == []
    assert o.quality_score is None


def test_bos_h4_es_context_no_poi():
    # HTF BOS es CONTEXT; POI solo para zonas (FVG/OB) en HTF.
    o = MarketObject(
        type=ObjectType.BOS, origin_tf="H4", role=Role.CONTEXT, direction=1
    )
    assert o.role == Role.CONTEXT
