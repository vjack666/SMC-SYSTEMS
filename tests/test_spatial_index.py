"""Tests del índice espacial de intervalos de precio (FVG/OB)."""
from __future__ import annotations

import numpy as np
import pytest

from ict_backtest.spatial_index import (
    PriceIntervalIndex,
    build_fvg_price_index,
    build_ob_price_index,
)


def test_insert_and_query_overlap():
    idx = PriceIntervalIndex(p_min=1.0, p_max=2.0, n_buckets=32)
    idx.insert(10, 1.10, 1.15, direction=1)
    idx.insert(20, 1.40, 1.50, direction=-1)
    idx.insert(30, 1.12, 1.14, direction=1)

    hits = idx.query_overlap(1.11, 1.13, direction=1)
    ids = {h[0] for h in hits}
    assert 10 in ids
    assert 30 in ids
    assert 20 not in ids


def test_query_respects_bar_window():
    idx = PriceIntervalIndex(p_min=1.0, p_max=2.0, n_buckets=16)
    idx.insert(5, 1.10, 1.20, 1)
    idx.insert(50, 1.10, 1.20, 1)
    hits = idx.query_overlap(1.12, 1.18, direction=1, bar_min=40, bar_max=60)
    assert [h[0] for h in hits] == [50]


def test_best_overlap_depth():
    idx = PriceIntervalIndex(p_min=1.0, p_max=2.0, n_buckets=32)
    idx.insert(1, 1.12, 1.14, 1)  # depth 0.4 over gap [1.10,1.15]
    idx.insert(2, 1.10, 1.11, 1)  # depth 0.2
    best = idx.query_best_overlap(1.10, 1.15, direction=1, min_depth=0.0)
    assert best is not None
    ov_lo, ov_hi, depth = best
    assert ov_lo == pytest.approx(1.12)
    assert ov_hi == pytest.approx(1.14)
    assert depth == pytest.approx(0.4)


def test_build_fvg_price_index():
    f_lo = np.array([np.nan, 1.10, 1.20])
    f_hi = np.array([np.nan, 1.15, 1.25])
    f_dir = np.array([0, 1, -1], dtype=np.int8)
    index = build_fvg_price_index(f_lo, f_hi, f_dir, n_buckets=64)
    hits = index.query_overlap(1.12, 1.14, direction=1)
    assert any(h[0] == 1 for h in hits)


def test_no_false_overlap_when_disjoint():
    idx = PriceIntervalIndex(p_min=1.0, p_max=2.0, n_buckets=8)
    idx.insert(1, 1.00, 1.05, 1)
    hits = idx.query_overlap(1.50, 1.60, direction=1)
    assert hits == []
