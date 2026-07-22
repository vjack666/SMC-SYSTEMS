"""Integration tests for OTE (Optimal Trade Entry) wiring in canonical.evaluate_signals.

TDD RED-first: these tests assert the integration contract BEFORE relying on
implementation details. They cover:
  - OTE math (ote_zone / is_ote_entry).
  - flag_ote behavior on real evaluate_signals output (call-site real).
  - _rr_for_raw_signal OTE branch returning 3.0.
  - Brecha D: OTE does NOT hard-filter signals (signal count preserved).
  - Edge cases: flat data / no swing / empty list.

No ATR / indicators are used.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ict_backtest.canonical import _rr_for_raw_signal, evaluate_signals
from ict_backtest.engine import ICTSignal
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.setups.ote import (
    OTE_FIB_HIGH,
    OTE_FIB_LOW,
    flag_ote,
    is_ote_entry,
    ote_zone,
)

# ---------------------------------------------------------------------------
# Synthetic scenario helpers (independent from test_d1_ote.py)
# ---------------------------------------------------------------------------
_BASE = pd.Timestamp("2026-01-05 07:00", tz="UTC")
_FREQ = "15min"
_N = 40
_ENTRY_AT = 22
_SWEEP_AT = 0
_HI_PAD = 0.0008
_LO_PAD = 0.0008


def _zigzag_closes() -> list[float]:
    closes: list[float] = []
    price = 1.0800
    for _ in range(8):
        for _ in range(5):
            price += 0.0020
            closes.append(round(price, 4))
        for _ in range(5):
            price -= 0.0020
            closes.append(round(price, 4))
    while len(closes) < _N:
        closes.append(closes[-1])
    return closes[:_N]


def _make_frames(sweep_low=None, sweep_high=None) -> dict:
    times = pd.date_range(_BASE, periods=_N, freq=_FREQ, tz="UTC")
    closes = np.array(_zigzag_closes(), dtype=float)
    df = pd.DataFrame(
        {
            "time": times,
            "open": closes,
            "high": closes + _HI_PAD,
            "low": closes - _LO_PAD,
            "close": closes,
            "volume": 100.0,
        }
    )
    df["sweep_low"] = np.nan
    df["sweep_high"] = np.nan
    df["bsl_price"] = np.nan
    df["ssl_price"] = np.nan
    if sweep_low is not None:
        df["sweep_low"] = sweep_low
    if sweep_high is not None:
        df["sweep_high"] = sweep_high
    return {"M15": df}


def _ote_midpoint(df, entry_at, direction):
    ms = detect_market_structure(df["M15"])
    sh = float(ms["swing_high"].iloc[entry_at])
    sl = float(ms["swing_low"].iloc[entry_at])
    r = sh - sl
    if direction == 1:
        return sh - (OTE_FIB_LOW + OTE_FIB_HIGH) / 2.0 * r
    return sl + (OTE_FIB_LOW + OTE_FIB_HIGH) / 2.0 * r


def _inject_signal(monkeypatch, entry_at, sweep_at, direction):
    import ict_backtest.canonical as canon_mod
    import ict_backtest.sequence as seq_mod

    fake_raw = [
        {
            "time": "t",
            "direction": direction,
            "entry": 0.0,
            "sweep_at": sweep_at,
            "displace_at": sweep_at,
            "bos_at": sweep_at,
            "entry_at": entry_at,
            "zone_authority": None,
            "htf_aligned": True,
            "htf_reason": "",
        }
    ]

    def fake_run(ltf_df_or_objs, est_htf_fn, cfg, *args, **kwargs):
        return fake_raw, {
            "SWEEP": 1,
            "DISPLACE": 1,
            "BOS": 1,
            "ENTRY": 1,
        }

    monkeypatch.setattr(seq_mod, "run_sequence", fake_run)
    monkeypatch.setattr(canon_mod, "run_sequence", fake_run)


# ===================================================================
# 1. OTE math unit contract
# ===================================================================
def test_ote_zone_returns_fib_62_79_of_leg():
    sh, sl = 1.1000, 1.0800
    lo, hi = ote_zone(sh, sl)
    r = sh - sl
    assert abs(lo - (sh - OTE_FIB_HIGH * r)) < 1e-12
    assert abs(hi - (sh - OTE_FIB_LOW * r)) < 1e-12
    assert sl < lo < hi < sh


def test_is_ote_entry_rejects_nonpositive_leg():
    ok, meta = is_ote_entry(1.09, 1.08, 1.10, direction=1)
    assert ok is False
    assert meta["ote_confirmed"] is False


# ===================================================================
# 2. Call-site real: evaluate_signals + flag_ote (the wired path)
# ===================================================================
def test_orchestrator_ote_long_entry_confirmed(monkeypatch):
    frames = _make_frames(sweep_low=1.0750, sweep_high=1.1025)
    ltf_df = frames["M15"]
    ote_entry = _ote_midpoint(frames, _ENTRY_AT, direction=1)
    ltf_df.loc[_ENTRY_AT + 1, "open"] = ote_entry

    _inject_signal(monkeypatch, _ENTRY_AT, _SWEEP_AT, direction=1)
    sigs = evaluate_signals(
        "SYN", "D1", "M15", frames=frames, enable_pd_index=False
    )
    assert sigs, "evaluate_signals did not return a signal with run_sequence stubbed"

    flagged = flag_ote(sigs, frames, ltf="M15")
    sig = flagged[0]
    assert sig.ote_confirmed is True
    ms = detect_market_structure(ltf_df)
    sh = float(ms["swing_high"].iloc[_ENTRY_AT])
    sl = float(ms["swing_low"].iloc[_ENTRY_AT])
    _ok, meta = is_ote_entry(sig.entry, sh, sl, sig.direction)
    assert sig.ote_zone == (meta["ote_low"], meta["ote_high"])
    assert meta["ote_low"] <= sig.entry <= meta["ote_high"]


def test_orchestrator_ote_short_entry_confirmed(monkeypatch):
    frames = _make_frames(sweep_low=1.0790, sweep_high=1.0910)
    ltf_df = frames["M15"]
    ote_entry = _ote_midpoint(frames, _ENTRY_AT, direction=-1)
    ltf_df.loc[_ENTRY_AT + 1, "open"] = ote_entry

    _inject_signal(monkeypatch, _ENTRY_AT, _SWEEP_AT, direction=-1)
    sigs = evaluate_signals(
        "SYN", "D1", "M15", frames=frames, enable_pd_index=False
    )
    assert sigs

    flagged = flag_ote(sigs, frames, ltf="M15")
    sig = flagged[0]
    assert sig.ote_confirmed is True
    ms = detect_market_structure(ltf_df)
    sh = float(ms["swing_high"].iloc[_ENTRY_AT])
    sl = float(ms["swing_low"].iloc[_ENTRY_AT])
    _ok, meta = is_ote_entry(sig.entry, sh, sl, sig.direction)
    assert sig.ote_zone == (meta["ote_low"], meta["ote_high"])


def test_orchestrator_ote_outside_band_false(monkeypatch):
    frames = _make_frames(sweep_low=1.0790, sweep_high=1.0910)
    ltf_df = frames["M15"]
    ms = detect_market_structure(ltf_df)
    sh = float(ms["swing_high"].iloc[_ENTRY_AT])
    sl = float(ms["swing_low"].iloc[_ENTRY_AT])
    shallow = sh - 0.30 * (sh - sl)
    ltf_df.loc[_ENTRY_AT + 1, "open"] = shallow

    _inject_signal(monkeypatch, _ENTRY_AT, _SWEEP_AT, direction=1)
    sigs = evaluate_signals(
        "SYN", "D1", "M15", frames=frames, enable_pd_index=False
    )
    assert sigs

    flagged = flag_ote(sigs, frames, ltf="M15")
    assert flagged[0].ote_confirmed is False
    # zona se calcula igual siempre que haya swing_row
    assert flagged[0].ote_zone is not None


# ===================================================================
# 3. Edge cases: no swing / empty list
# ===================================================================
def test_orchestrator_ote_no_swing_row_returns_false_and_none_zone():
    flat_times = pd.date_range(_BASE, periods=_N, freq=_FREQ, tz="UTC")
    flat_df = pd.DataFrame(
        {
            "time": flat_times,
            "open": 1.1000,
            "high": 1.1003,
            "low": 1.0997,
            "close": 1.1000,
            "volume": 100.0,
            "sweep_low": np.nan,
            "sweep_high": np.nan,
            "bsl_price": np.nan,
            "ssl_price": np.nan,
        }
    )
    ms = detect_market_structure(flat_df)
    assert ms["swing_high"].isna().all() and ms["swing_low"].isna().all()

    sig = ICTSignal(
        symbol="SYN",
        time="t",
        direction=1,
        entry=1.1000,
        stop_loss=1.0990,
        take_profit=1.1050,
        entry_at=10,
    )
    out = flag_ote([sig], {"M15": flat_df}, ltf="M15")
    assert out[0].ote_confirmed is False
    assert out[0].ote_zone is None


def test_orchestrator_flag_ote_empty_signals_returns_empty_list():
    frames = _make_frames(sweep_low=1.0750)
    assert flag_ote([], frames, ltf="M15") == []


# ===================================================================
# 4. Brecha D: OTE does NOT hard-filter signals (count preserved)
# ===================================================================
def test_orchestrator_ote_false_does_not_drop_signal(monkeypatch):
    frames = _make_frames(sweep_low=1.0790, sweep_high=1.0910)
    ltf_df = frames["M15"]
    ms = detect_market_structure(ltf_df)
    sh = float(ms["swing_high"].iloc[_ENTRY_AT])
    sl = float(ms["swing_low"].iloc[_ENTRY_AT])
    shallow = sh - 0.30 * (sh - sl)
    ltf_df.loc[_ENTRY_AT + 1, "open"] = shallow

    _inject_signal(monkeypatch, _ENTRY_AT, _SWEEP_AT, direction=1)
    sigs = evaluate_signals(
        "SYN", "D1", "M15", frames=frames, enable_pd_index=False
    )
    assert len(sigs) == 1
    flagged = flag_ote(sigs, frames, ltf="M15")
    assert len(flagged) == 1
    assert flagged[0].ote_confirmed is False


# ===================================================================
# 5. rr_target = 3.0 when OTE confirmed + flag_rr resolution
# ===================================================================
def test_flag_rr_resolves_ote_target_when_ote_confirmed():
    sig = ICTSignal(
        symbol="SYN",
        time="t",
        direction=1,
        entry=1.0867,
        stop_loss=1.0780,
        take_profit=1.1050,
        entry_at=22,
    )
    setattr(sig, "ote_confirmed", True)
    setattr(sig, "sb_confirmed", False)
    setattr(sig, "turtle_confirmed", False)

    from ict_backtest.setups.rr_map import flag_rr

    out = flag_rr([sig])
    assert out[0].rr_target == 3.0


# ===================================================================
# 6. RR precedence on wired signals: OTE wins over default, SB over OTE
# ===================================================================
def test_rr_target_precedence_ote_sb_default():
    from ict_backtest.setups.rr_map import flag_rr

    sb_sig = ICTSignal(symbol="S", time="t", direction=1, entry=1.1, stop_loss=1.09, take_profit=1.13)
    setattr(sb_sig, "sb_confirmed", True)
    setattr(sb_sig, "turtle_confirmed", False)
    setattr(sb_sig, "ote_confirmed", True)

    ote_only = ICTSignal(symbol="S", time="t", direction=1, entry=1.1, stop_loss=1.09, take_profit=1.13)
    setattr(ote_only, "sb_confirmed", False)
    setattr(ote_only, "turtle_confirmed", False)
    setattr(ote_only, "ote_confirmed", True)

    none_sig = ICTSignal(symbol="S", time="t", direction=1, entry=1.1, stop_loss=1.09, take_profit=1.13)

    sigs = flag_rr([sb_sig, ote_only, none_sig])
    assert sigs[0].rr_target == 2.0       # SB > OTE
    assert sigs[1].rr_target == 3.0       # OTE > default
    assert sigs[2].rr_target == 3.0       # default -> 3.0
