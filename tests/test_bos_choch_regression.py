"""Regression suite for BOS/CHOCH unification (ETAPA 4 PASO 1).

Purpose (Ruben, 2026-07-17): before unifying the two structure engines
(`detectors/bos.py` + `detectors/choch.py` vs `ict_backtest/market_structure.py`)
into a single source of truth, LOCK the expected behaviour so the unification
cannot silently change semantics.

CONTRACT (post-unification, PASO 1 parte 2):
  A. Swing detection is IDENTICAL between both engines (same algorithm copy).
  B. Event-driven invalidation (cross of broken level) is IDENTICAL and on the
     SAME bar.
  C. BOTH engines now require `confirm_bars=2` consecutive body closes (filters
     fakeouts). Legacy detectors.bos no longer fires on a single bar.
  D. CHOCH is ALIGNED: detectors.choch now follows the canonical rule (breaks the
     LAST BOS level opposite to its direction, 2-body confirmation). choch_signal
     equals the string form of canonical choch_dir.

Synthetic deterministic data only (no MT5, no network) -> fast + reproducible.

Timing note: with swing_lookback=5 the swing at bar 10 is EXPOSED (via
shift(5)+ffill) only from bar 15 onward. All breaks/crosses below occur at
bar >= 20 so the swing level is already visible.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from detectors.bos import detect_bos, BosConfig, _swing_points as det_swing
from detectors.choch import detect_choch
from ict_backtest.market_structure import (
	detect_market_structure,
	StructureConfig,
	_swing_points as ms_swing,
)


def _flat(n: int, price: float = 100.0) -> pd.DataFrame:
	idx = pd.date_range("2026-01-01", periods=n, freq="15min")
	return pd.DataFrame(
		{"open": price, "high": price, "low": price, "close": price}, index=idx
	)


def _set(idx_df, i, high=None, low=None, close=None):
	if high is not None:
		idx_df.loc[idx_df.index[i], "high"] = high
	if low is not None:
		idx_df.loc[idx_df.index[i], "low"] = low
	if close is not None:
		idx_df.loc[idx_df.index[i], "close"] = close


def _break_up(df, start, bars, step=1.0):
	for k in range(bars):
		i = start + k
		c = df.loc[df.index[i], "close"] + step
		_set(df, i, high=c, low=c - step * 0.3, close=c)


def _cross_down(df, at, level, step=1.0):
	c = level - step
	_set(df, at, high=c + step * 0.2, low=c, close=c)


def _hold_above(df, start, end, price=106.0):
	for i in range(start, end):
		_set(df, i, high=price + 0.5, low=price - 0.5, close=price)


# ---------------------------------------------------------------------------
# A. Swings identical between engines
# ---------------------------------------------------------------------------
def test_swings_identical():
	fr = _flat(40, 100.0)
	_set(fr, 10, high=105.0, close=105.0)
	_set(fr, 20, low=95.0, close=95.0)

	sh_d, sl_d = det_swing(fr, 5)
	sh_m, sl_m = ms_swing(fr, 5)
	assert sh_d.fillna(-1).equals(sh_m.fillna(-1))
	assert sl_d.fillna(-1).equals(sl_m.fillna(-1))


# ---------------------------------------------------------------------------
# B. Event-driven invalidation identical (same bar)
# ---------------------------------------------------------------------------
def test_invalidation_identical_canonical():
	fr = _flat(40, 100.0)
	_set(fr, 10, high=105.0, close=105.0)
	_set(fr, 20, high=106.0, low=105.5, close=106.0)
	_hold_above(fr, 21, 32)
	_cross_down(fr, 32, 105.0, 1.0)

	ms = detect_market_structure(fr, StructureConfig(confirm_bars=1))
	assert (ms["bos_status"] == "invalidated").any()
	ms_inv_pos = int(np.argmax(ms["bos_status"].to_numpy() == "invalidated"))
	assert ms_inv_pos >= 32


def test_invalidation_identical_detectors():
	fr = _flat(40, 100.0)
	_set(fr, 10, high=105.0, close=105.0)
	_set(fr, 20, high=106.0, low=105.5, close=106.0)
	_hold_above(fr, 21, 32)
	_cross_down(fr, 32, 105.0, 1.0)

	det = detect_bos(fr, BosConfig(swing_lookback=5))
	assert (det["bos_status"] == "invalidated").any()
	det_inv_pos = int(np.argmax(det["bos_status"].to_numpy() == "invalidated"))
	assert det_inv_pos >= 32


def test_invalidation_same_bar():
	fr = _flat(40, 100.0)
	_set(fr, 10, high=105.0, close=105.0)
	_set(fr, 20, high=106.0, low=105.5, close=106.0)
	_hold_above(fr, 21, 32)
	_cross_down(fr, 32, 105.0, 1.0)

	ms = detect_market_structure(fr, StructureConfig(confirm_bars=1))
	det = detect_bos(fr, BosConfig(swing_lookback=5))
	ms_inv_pos = int(np.argmax(ms["bos_status"].to_numpy() == "invalidated"))
	det_inv_pos = int(np.argmax(det["bos_status"].to_numpy() == "invalidated"))
	assert ms_inv_pos == det_inv_pos


# ---------------------------------------------------------------------------
# C. Both engines require confirm_bars=2 (no single-bar fakeout)
# ---------------------------------------------------------------------------
def test_canonical_requires_2_confirm_bars():
	fr = _flat(40, 100.0)
	_set(fr, 10, high=105.0, close=105.0)
	_set(fr, 20, high=106.0, low=105.5, close=106.0)

	ms = detect_market_structure(fr, StructureConfig(confirm_bars=2))
	assert int((ms["bos_dir"] != 0).sum()) == 0


def test_detectors_now_requires_2_bars():
	fr = _flat(40, 100.0)
	_set(fr, 10, high=105.0, close=105.0)
	_set(fr, 20, high=106.0, low=105.5, close=106.0)

	det = detect_bos(fr, BosConfig(swing_lookback=5))
	# After unification detectors adopts confirm_bars=2: must NOT fire on 1 bar.
	assert int((det["bos_direction"] != 0).sum()) == 0


# ---------------------------------------------------------------------------
# D. CHOCH aligned to canonical (unification resolved the divergence)
# ---------------------------------------------------------------------------
def test_choch_aligned_to_canonical():
	fr = _flat(70, 100.0)
	_set(fr, 10, high=105.0, close=105.0)
	_break_up(fr, 20, 3, 1.0)
	_set(fr, 45, high=98.5, low=97.5, close=98.0)

	det = detect_choch(fr)
	ms = detect_market_structure(fr, StructureConfig(confirm_bars=2))

	expected = np.where(
		ms["choch_dir"].to_numpy() == 1, "CHOCH_BULLISH",
		np.where(ms["choch_dir"].to_numpy() == -1, "CHOCH_BEARISH", "NONE"),
	)
	assert (det["choch_signal"].to_numpy() == expected).all()
	assert (det["choch_status"].to_numpy() == ms["choch_status"].to_numpy()).all()


# ---------------------------------------------------------------------------
# POST-UNIFICATION equivalence gate (active: detectors delegate to canonical)
# ---------------------------------------------------------------------------
def test_post_unification_equivalence():
	fr = _flat(70, 100.0)
	_set(fr, 10, high=105.0, close=105.0)
	_break_up(fr, 20, 3, 1.0)

	det = detect_bos(fr, BosConfig(swing_lookback=5))
	ms = detect_market_structure(fr, StructureConfig(confirm_bars=2, swing_lookback=5))

	d_dir = det["bos_direction"].fillna(0).reset_index(drop=True)
	m_dir = ms["bos_dir"].fillna(0).reset_index(drop=True)
	assert d_dir.equals(m_dir)

	d_st = det["bos_status"].fillna("none").reset_index(drop=True)
	m_st = ms["bos_status"].fillna("none").reset_index(drop=True)
	assert d_st.equals(m_st)
