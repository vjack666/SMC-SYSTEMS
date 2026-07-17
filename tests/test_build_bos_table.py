"""tests/test_build_bos_table.py

TDD para el generador de la bos_table empirica (R10 dinamico, sin indicadores).

Verifica:
- extract_bos_events: lee bos_dir/bos_level de velas (high-low, sin indicadores).
- measure_mitigation: vida del BOS = velas hasta BOS opuesto (anti-sesgo
  supervivencia: BOS sin opuesto despues se descarta).
- build_bos_table_from_counts: mediana por bucket 1..5.
- Integracion end-to-end con datos sinteticos.
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ict_backtest.bos_table_builder import (  # noqa: E402
    extract_bos_events,
    measure_mitigation,
    build_bos_table_from_counts,
    build_bos_table,
)


def _candle_df(rows):
    df = pd.DataFrame(rows)
    for col in ("high", "low", "open", "close", "bos_level"):
        if col in df.columns:
            df[col] = df[col].astype(float)
    return df


def test_extract_bos_events_reads_dir_and_level():
    df = _candle_df([
        {"time": "t0", "high": 10, "low": 9, "open": 9.5, "close": 9.6, "bos_dir": 0, "bos_level": float("nan")},
        {"time": "t1", "high": 11, "low": 9.5, "open": 9.6, "close": 10.8, "bos_dir": 1, "bos_level": 10.5},
        {"time": "t2", "high": 12, "low": 10, "open": 10.8, "close": 11.5, "bos_dir": 0, "bos_level": float("nan")},
        {"time": "t3", "high": 10.5, "low": 8.5, "open": 11.0, "close": 9.0, "bos_dir": -1, "bos_level": 9.5},
    ])
    events = extract_bos_events(df)
    assert len(events) == 2
    assert events[0] == (1, 10.5, 1)
    assert events[1] == (3, 9.5, -1)


def test_measure_mitigation_life_until_opposite_bos():
    # BOS alcista idx1. BOS opuesto (bajista) en idx5. Vida = 5-1 = 4.
    df = _candle_df([
        {"time": "t0", "high": 10, "low": 9, "open": 9.5, "close": 9.6, "bos_dir": 0, "bos_level": float("nan")},
        {"time": "t1", "high": 11, "low": 9.5, "open": 9.6, "close": 10.8, "bos_dir": 1, "bos_level": 10.5},
        {"time": "t2", "high": 10.4, "low": 10.0, "open": 10.2, "close": 10.3, "bos_dir": 0, "bos_level": float("nan")},
        {"time": "t3", "high": 10.6, "low": 10.2, "open": 10.3, "close": 10.5, "bos_dir": 0, "bos_level": float("nan")},
        {"time": "t4", "high": 10.5, "low": 10.1, "open": 10.4, "close": 10.2, "bos_dir": 0, "bos_level": float("nan")},
        {"time": "t5", "high": 9.0, "low": 8.5, "open": 9.5, "close": 8.8, "bos_dir": -1, "bos_level": 9.0},
    ])
    events = extract_bos_events(df)
    ns = measure_mitigation(df, events)
    assert ns[0] == 4
    assert len(ns) == 1


def test_measure_mitigation_drops_bos_with_no_opposite_after():
    # BOS alcista idx1, pero NO hay BOS bajista despues -> se descarta.
    df = _candle_df([
        {"time": "t0", "high": 10, "low": 9, "open": 9.5, "close": 9.6, "bos_dir": 0, "bos_level": float("nan")},
        {"time": "t1", "high": 11, "low": 9.5, "open": 9.6, "close": 10.8, "bos_dir": 1, "bos_level": 10.5},
        {"time": "t2", "high": 10.4, "low": 10.0, "open": 10.2, "close": 10.3, "bos_dir": 0, "bos_level": float("nan")},
        {"time": "t3", "high": 10.6, "low": 10.2, "open": 10.3, "close": 10.5, "bos_dir": 0, "bos_level": float("nan")},
    ])
    events = extract_bos_events(df)
    ns = measure_mitigation(df, events)
    assert len(ns) == 0


def test_build_bos_table_from_counts_median_per_bucket():
    measures = {1: [2, 4, 6], 3: [10, 12], 5: [20]}
    table = build_bos_table_from_counts(measures)
    assert table[1] == 4
    assert table[3] == 11
    assert table[5] == 20
    assert 2 not in table
    assert 4 not in table


def test_build_bos_table_end_to_end_synthetic():
    # BOS debil idx1 (rango pequeño) -> opuesto idx3: vida = 2
    # BOS fuerte idx4 (rango grande) -> sin opuesto despues: descartado
    df = _candle_df([
        {"time": "t0", "high": 10, "low": 9.9, "open": 9.95, "close": 9.95, "bos_dir": 0, "bos_level": float("nan")},
        {"time": "t1", "high": 10.1, "low": 10.0, "open": 10.0, "close": 10.05, "bos_dir": 1, "bos_level": 10.05},
        {"time": "t2", "high": 10.6, "low": 10.1, "open": 10.1, "close": 10.5, "bos_dir": 0, "bos_level": float("nan")},
        {"time": "t3", "high": 9.0, "low": 8.5, "open": 10.0, "close": 8.8, "bos_dir": -1, "bos_level": 9.0},
        {"time": "t4", "high": 12.0, "low": 10.1, "open": 10.1, "close": 11.8, "bos_dir": 1, "bos_level": 11.5},
        {"time": "t5", "high": 11.2, "low": 11.0, "open": 11.8, "close": 11.1, "bos_dir": 0, "bos_level": float("nan")},
    ])
    table = build_bos_table(df)
    assert isinstance(table, dict)
    assert 1 in table
    assert table[1] == 2
