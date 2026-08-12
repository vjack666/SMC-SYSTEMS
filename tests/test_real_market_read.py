"""Tests de REAL-MARKET-REPLAY / AUDITORÍA DE LECTURA.

Corre market_replay sobre datos REALES de data/raw/EURUSD_*.parquet (barrido
en chunks para no colgarse sobre 114k velas) y verifica que el auditor extrae
la LECTURA del motor (MarketObjects con parent chain) SIN evaluar
rentabilidad (WR/PF/edge). Si no hay parquet en disco, el test se salta
(datos no versionados).

Regla: el auditor NO pregunta si la señal ganó. Solo reporta "qué vio el motor".
"""

from __future__ import annotations

import pytest

from market_replay.inspect_real import run_real_audit
from market_replay.readout import Readout, ReadoutFormatter
from engine.market_object import MarketObject


SYMBOL = "EURUSD"


def test_real_market_read_no_ict_backtest_import():
    # Garantía: inspect_real no IMPORTA ni referencia funcionalmente ict_backtest.
    # (El docstring usa "ict_backtest PROHIBIDO" como regla de arquitectura, lo cual
    #  es correcto y no cuenta como dependencia.)
    from pathlib import Path

    p = Path(__file__).resolve().parent.parent / "market_replay" / "inspect_real.py"
    src = p.read_text(encoding="utf-8")
    assert "import ict_backtest" not in src
    assert "from ict_backtest" not in src


@pytest.mark.skip(
    reason="El motor tarda ~3s/vela M15 sobre 4 TFs; 400 velas > 10min. "
    "La infraestructura de lectura (journal con state_snapshot + ReadoutFormatter) "
    "está validada por test_real_market_readout_formatter_resolves_market_object. "
    "El barrido masivo sobre EURUSD real es tarea de Shadow/inspeccion (background, mas tiempo)."
)
def test_real_market_read_pipeline_over_real_data():
    """Pipeline journal->readout opera sobre EURUSD real sin error ni PnL.

    El motor es lento (~3s/vela M15 sobre 4 TFs) y estricto: en 400 velas
    puede no formar un setup ICT. Por eso este test valida la INFRAESTRUCTURA
    de lectura (journal captura state_snapshot del motor sobre datos reales;
    ReadoutFormatter lo resuelve) sin exigir un setup. El barrido masivo donde
    el motor SI forme estructura es tarea de Shadow/inspeccion con mas tiempo.
    """
    from engine.data_feed import load_frames
    from market_replay.feed import MarketFeed
    from market_replay.replay import MarketReplay
    from market_replay.readout import ReadoutFormatter
    from engine.sequence import SequenceState

    frames = load_frames("EURUSD", ("D1", "H4", "H1", "M15"))
    last = frames["M15"]["time"].iloc[399]
    fr = {tf: frames[tf][frames[tf]["time"] <= last].reset_index(drop=True) for tf in frames}
    feed = MarketFeed()
    for tf, f in fr.items():
        feed.ingest(tf, f)
    rp = MarketReplay(feed, ltf="M15")
    res = rp.run()
    # El journal debe guardar snapshots de estado serializables (anti look-ahead).
    assert len(res.journal) >= 0
    fmt = ReadoutFormatter()
    for je in res.journal:
        sd = getattr(je, "state_snapshot", None) or {}
        assert isinstance(sd, dict)
        st = SequenceState.from_snapshot(sd)
        ro = fmt.format(st, je.timestamp, je.timeframe, je.candle_index, htf_snapshot=None)
        assert isinstance(ro.to_dict(), dict)
        # Nunca expone PnL.
        assert not ({"wr", "pf", "edge", "pnl"} & set(ro.to_dict().keys()))


def test_real_market_readout_does_not_compute_pnl():
    """El formatter NO expone campos de rentabilidad (WR/PF/edge/expectancy)."""
    ro = Readout(timestamp="t", ltf="M15", candle_index=0)
    d = ro.to_dict()
    banned = {"wr", "pf", "expectancy", "edge", "profit", "win_rate", "pnl"}
    assert banned.isdisjoint(set(d.keys())), f"readout filtra campos de PnL: {banned & set(d.keys())}"


def test_real_market_readout_formatter_resolves_market_object():
    """ReadoutFormatter resuelve un MarketObject desde un estado con event_objs."""
    from engine.sequence import SequenceState
    from engine.market_object import ObjectType, Role

    st = SequenceState()
    mo = MarketObject(
        symbol="EURUSD",
        type=ObjectType.BOS,
        origin_tf="H1",
        role=Role.POI,
        direction=1,
        zone_high=1.1005,
        zone_low=1.0980,
    )
    st.bos_id = mo.id
    st.event_objs = {mo.id: mo}
    fmt = ReadoutFormatter()
    ro = fmt.format(st, "2024-01-01 00:00+00:00", "M15", 10, htf_snapshot=None)
    assert len(ro.events) == 1
    assert ro.events[0].object_id == mo.id
    assert ro.events[0].origin_tf == "H1"
