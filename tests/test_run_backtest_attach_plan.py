"""RED->GREEN — --attach-plan cablea AlignmentReport en run_sequence_backtest (OBSERVE).

Valida que con attach_plan=True el backtest adjunta un AlignmentReport por senal
en m["alignments"], SIN cambiar m["trades"] (el bot opera igual).
Se mockea load_frames/structure/sequence/simulate/context_mtf para no tocar datos
reales (el import lazy de context_mtf se suplanta con un module mock).
"""

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(".").resolve()))

import pandas as pd

# Suplanta el modulo context_mtf ANTES de importar run_backtest (evita import real
# pesado que crashea en Windows). El lazy import del loop usara este mock.
_fake_ctx_mod = mock.MagicMock()
sys.modules["ict_backtest.v2.context_mtf"] = _fake_ctx_mod


def _fake_sig():
    sig = mock.MagicMock()
    sig.time = "2024-01-02 10:00:00"
    sig.direction = 1
    sig.phase_log = ["SWEEP_DONE", "DISPLACE_DONE", "BOS_DONE", "ENTRY"]
    sig.entry_at = 10
    return sig


def _fake_stack():
    from ict_backtest.market_object import (
        MarketObject, ObjectState, ObjectType, Role,
    )
    return {
        "frames": {
            "D1": mock.MagicMock(objects=[
                MarketObject(type=ObjectType.LIQUIDITY, direction=1, origin_tf="D1",
                             role=Role.CONTEXT, state=ObjectState.ACTIVE)]),
            "H4": mock.MagicMock(objects=[
                MarketObject(type=ObjectType.BOS, direction=1, origin_tf="H4",
                             role=Role.REFINEMENT, state=ObjectState.ACTIVE)]),
            "H1": mock.MagicMock(objects=[
                MarketObject(type=ObjectType.ORDER_BLOCK, direction=1, origin_tf="H1",
                             role=Role.POI, state=ObjectState.ACTIVE)]),
            "M15": mock.MagicMock(objects=[
                MarketObject(type=ObjectType.FVG, direction=1, origin_tf="M15",
                             role=Role.REFINEMENT, state=ObjectState.ACTIVE)]),
        }
    }


def test_attach_plan_puebla_alignments_sin_cambiar_trades():
    from ict_backtest.run_backtest import run_sequence_backtest

    sig = _fake_sig()
    fake_trade = mock.MagicMock()
    fake_trade.pnl_r = 1.0
    fake_meta = {"exit_reason": "tp"}

    df = pd.DataFrame({"time": pd.date_range("2024-01-01", periods=20, freq="15min")})

    with mock.patch("ict_backtest.run_backtest.load_frames",
                    return_value={"M15": df}), \
         mock.patch("ict_backtest.run_backtest.detect_market_structure",
                    return_value=df), \
         mock.patch("ict_backtest.run_backtest.generate_sequence_signals",
                    return_value=[sig]), \
         mock.patch("ict_backtest.run_backtest.simulate_trade_with_context",
                    return_value=(fake_trade, fake_meta, None)), \
         mock.patch.object(_fake_ctx_mod, "build_context_stack",
                           return_value=_fake_stack()):
        m = run_sequence_backtest(
            "EURUSD", "H4", "M15", max_hold=50,
            attach_plan=True, backtest_id="TEST-ATTACH",
        )

    assert m["trades"] == 1  # NO cambia el conteo
    assert "alignments" in m
    assert len(m["alignments"]) == 1
    rep = m["alignments"][0]
    assert "score" in rep
    assert "d1" in rep


def test_sin_attach_plan_no_puebla_alignments():
    from ict_backtest.run_backtest import run_sequence_backtest

    sig = _fake_sig()
    fake_trade = mock.MagicMock()
    fake_trade.pnl_r = 1.0
    fake_meta = {"exit_reason": "tp"}

    df = pd.DataFrame({"time": pd.date_range("2024-01-01", periods=20, freq="15min")})

    with mock.patch("ict_backtest.run_backtest.load_frames",
                    return_value={"M15": df}), \
         mock.patch("ict_backtest.run_backtest.detect_market_structure",
                    return_value=df), \
         mock.patch("ict_backtest.run_backtest.generate_sequence_signals",
                    return_value=[sig]), \
         mock.patch("ict_backtest.run_backtest.simulate_trade_with_context",
                    return_value=(fake_trade, fake_meta, None)), \
         mock.patch.object(_fake_ctx_mod, "build_context_stack",
                           return_value=_fake_stack()):
        m = run_sequence_backtest(
            "EURUSD", "H4", "M15", max_hold=50,
            attach_plan=False, backtest_id="TEST-NOATTACH",
        )

    assert m["trades"] == 1
    assert "alignments" not in m


def test_window_months_se_pasa_a_run_sequence_backtest():
    """El flag --window-months del CLI debe llegar a run_sequence_backtest."""
    from ict_backtest.run_backtest import run_sequence_backtest

    sig = _fake_sig()
    fake_trade = mock.MagicMock()
    fake_trade.pnl_r = 1.0
    fake_meta = {"exit_reason": "tp"}
    df = pd.DataFrame({"time": pd.date_range("2024-01-01", periods=20, freq="15min")})

    captured = {}

    def _fake_seq(symbol, htf, ltf, counter_trend=False, tp_mode="fixed2r",
                  require_displacement=True, displace_gap=6, bos_gap=10,
                  bos_table=None, frames=None, fill_mode="next_open",
                  enable_pd_index=False, **kwargs):
        captured["called"] = True
        return [sig]

    with mock.patch("ict_backtest.run_backtest.load_frames",
                    return_value={"M15": df}), \
         mock.patch("ict_backtest.run_backtest.detect_market_structure",
                    return_value=df), \
         mock.patch("ict_backtest.run_backtest.generate_sequence_signals",
                    side_effect=_fake_seq), \
         mock.patch("ict_backtest.run_backtest.simulate_trade_with_context",
                    return_value=(fake_trade, fake_meta, None)), \
         mock.patch.object(_fake_ctx_mod, "build_context_stack",
                           return_value=_fake_stack()):
        run_sequence_backtest(
            "EURUSD", "H4", "M15", max_hold=50,
            attach_plan=False, backtest_id="TEST-WIN", window_months=1,
        )

    assert captured.get("called") is True
