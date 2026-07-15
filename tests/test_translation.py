import pandas as pd
import pytest

from ict_backtest.market_object import (
    MarketObject,
    ObjectType,
    Role,
    ObjectState,
)
from ict_backtest.translation import objects_to_legacy_df


def test_reconstruye_columnas_clave():
    objs = [
        MarketObject(
            type=ObjectType.BOS,
            origin_tf="H4",
            role=Role.CONTEXT,
            direction=1,
            state=ObjectState.ACTIVE,
        ),
        MarketObject(
            type=ObjectType.FVG,
            origin_tf="M15",
            role=Role.REFINEMENT,
            direction=1,
            zone_high=1.1,
            zone_low=1.09,
            state=ObjectState.ACTIVE,
        ),
    ]
    df = objects_to_legacy_df(objs)
    assert "bos_direction" in df.columns
    assert "fvg_state" in df.columns
    assert int(df["bos_direction"].iloc[0]) == 1
    assert df["fvg_state"].iloc[1] == "FVG"


def test_invalidated_mapea_a_none_para_bos_alive():
    # INVALIDATED -> "none" para que signals/pipeline.py:177-189 (bos_alive)
    # siga filtrando igual que antes de la migracion.
    inv = MarketObject(
        type=ObjectType.BOS,
        origin_tf="H4",
        role=Role.CONTEXT,
        state=ObjectState.INVALIDATED,
    )
    df = objects_to_legacy_df([inv])
    assert df["bos_status"].iloc[0] == "none"


def test_fvg_bullish_bearish_flags():
    objs = [
        MarketObject(type=ObjectType.FVG, origin_tf="M15", direction=1,
                     state=ObjectState.ACTIVE),
        MarketObject(type=ObjectType.FVG, origin_tf="M15", direction=-1,
                     state=ObjectState.ACTIVE),
    ]
    df = objects_to_legacy_df(objs)
    assert bool(df["fvg_bullish"].iloc[0]) is True
    assert bool(df["fvg_bearish"].iloc[1]) is True


def test_df_to_objects_sella_capa():
    # Desde un df H4 con FVG alcista + BOS -> objetos con origin_tf sellado
    # y role por regla (H4 FVG = POI; H4 BOS = CONTEXT).
    from ict_backtest.translation import df_to_objects

    h4 = pd.DataFrame({
        "close": [1.0, 2.0], "high": [1.1, 2.1], "low": [0.9, 1.9],
        "bos_direction": [1, 0], "fvg_bullish": [True, False],
        "fvg_bearish": [False, False],
    })
    objs = df_to_objects({"H4": h4}, symbol="EURUSD")
    fvgs = [o for o in objs if o.type.value == "FVG"]
    boses = [o for o in objs if o.type.value == "BOS"]
    assert fvgs and fvgs[0].origin_tf == "H4" and fvgs[0].role.value == "POI"
    assert boses and boses[0].role.value == "CONTEXT"
    # Todo objeto tiene id unico (identidad)
    ids = {o.id for o in objs}
    assert len(ids) == len(objs)
