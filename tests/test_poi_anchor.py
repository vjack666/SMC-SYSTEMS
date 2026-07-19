"""RED — poi_anchor: ancla narrativa de FVG/OB LTF a BOS/CHOCH del TF padre.

Brecha B (AUDITORIA_TESIS_FASE5.md): el POI real esta anclado a la narrativa
(desplazamiento HTF padre). Hoy el motor acepta FVG/OB sueltos (100% sin ancla
segun auditoria). anchor_objects MARCA (no borra) cada objeto LTF con
meta["anchored"] segun si hay BOS/CHOCH en la MISMA direccion en HTF padre
cerrado (anti look-ahead). Funcion PURA, testeable con datos sinteticos.
Test FALLA hasta implementar ict_backtest/poi_anchor.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

from ict_backtest.market_object import (
    MarketObject,
    ObjectState,
    ObjectType,
    Role,
)


def _fvg_bull(tf, bar_index, anchored_id=None):
    return MarketObject(
        type=ObjectType.FVG, direction=1, origin_tf=tf, role=Role.REFINEMENT,
        state=ObjectState.ACTIVE, bar_index=bar_index,
        id=anchored_id or "fvg1",
    )


def _bos_bull(tf, bar_index, oid="bos1"):
    return MarketObject(
        type=ObjectType.BOS, direction=1, origin_tf=tf, role=Role.CONTEXT,
        state=ObjectState.ACTIVE, bar_index=bar_index, id=oid,
    )


def test_fvg_con_bos_padre_queda_anclado():
    from ict_backtest.poi_anchor import anchor_objects

    fvg = _fvg_bull("M15", bar_index=100)
    bos_h4 = _bos_bull("H4", bar_index=50)  # BOS H4 previo (cerrado) en misma dir
    anchored = anchor_objects([fvg], {"H4": [bos_h4]})
    assert anchored[0].meta.get("anchored") is True
    assert anchored[0].parent_object == bos_h4.id


def test_fvg_sin_bos_padre_queda_suelto():
    from ict_backtest.poi_anchor import anchor_objects

    fvg = _fvg_bull("M15", bar_index=100)
    # sin objetos HTF -> geometria suelta
    anchored = anchor_objects([fvg], {})
    assert anchored[0].meta.get("anchored") is False
    assert anchored[0].parent_object is None


def test_fvg_no_mira_futuro_htf():
    from ict_backtest.poi_anchor import anchor_objects

    fvg = _fvg_bull("M15", bar_index=100)
    # BOS H4 EN EL FUTURO (bar_index 200 > 100) -> no cuenta (anti look-ahead)
    bos_futuro = _bos_bull("H4", bar_index=200)
    anchored = anchor_objects([fvg], {"H4": [bos_futuro]})
    assert anchored[0].meta.get("anchored") is False


def test_fvg_direccion_opuesta_no_ancla():
    from ict_backtest.poi_anchor import anchor_objects

    fvg = _fvg_bull("M15", bar_index=100)  # bullish
    bos_bear = MarketObject(
        type=ObjectType.BOS, direction=-1, origin_tf="H4", role=Role.CONTEXT,
        state=ObjectState.ACTIVE, bar_index=50, id="bosb",
    )
    anchored = anchor_objects([fvg], {"H4": [bos_bear]})
    assert anchored[0].meta.get("anchored") is False
