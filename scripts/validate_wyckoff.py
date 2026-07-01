from __future__ import annotations

import numpy as np
import pandas as pd

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from modules.wyckoff.config import WyckoffConfig
from modules.wyckoff.detector import detect_wyckoff


def _make_synthetic_bars(n: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(0, 0.5, n))
    high = close + np.abs(rng.normal(0, 0.3, n))
    low = close - np.abs(rng.normal(0, 0.3, n))
    open_ = close - np.abs(rng.normal(0, 0.2, n))
    volume = np.abs(rng.integers(1000, 10000, n))
    return pd.DataFrame({
        "time": pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC"),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "tick_volume": volume,
    })


def test_detector_columns() -> None:
    df = _make_synthetic_bars(200)
    config = WyckoffConfig()
    result = detect_wyckoff(df, config)

    required_cols = [
        "wyckoff_phase",
        "wyckoff_sc", "wyckoff_ar", "wyckoff_st",
        "wyckoff_spring", "wyckoff_sos", "wyckoff_lps",
        "wyckoff_upthrust", "wyckoff_sow", "wyckoff_lpsy",
        "wyckoff_accumulation", "wyckoff_distribution",
        "wyckoff_markup", "wyckoff_markdown",
    ]
    for col in required_cols:
        assert col in result.columns, f"Missing column: {col}"
    print(f"  OK: All {len(required_cols)} columns present")


def test_phase_values() -> None:
    df = _make_synthetic_bars(300)
    config = WyckoffConfig()
    result = detect_wyckoff(df, config)
    unique = set(result["wyckoff_phase"].dropna().unique())
    expected = {
        "ACCUMULATION_A", "ACCUMULATION_B", "ACCUMULATION_C",
        "ACCUMULATION_D", "ACCUMULATION_E",
        "DISTRIBUTION_A", "DISTRIBUTION_B", "DISTRIBUTION_C",
        "DISTRIBUTION_D", "DISTRIBUTION_E",
        "MARKUP", "MARKDOWN", "UNKNOWN",
    }
    missing = expected - unique
    extra = unique - expected
    if missing:
        print(f"  WARN: Some phases never emitted: {sorted(missing)}")
    if extra:
        print(f"  WARN: Unexpected phases: {sorted(extra)}")
    print(f"  Phases observed ({len(unique)}): {sorted(unique)}")


def test_accumulation_event_coherence() -> None:
    df = _make_synthetic_bars(300)
    config = WyckoffConfig()
    result = detect_wyckoff(df, config)
    accum = result[result["wyckoff_accumulation"] == 1]
    if len(accum) > 0:
        has_event = (
            accum["wyckoff_sc"] | accum["wyckoff_ar"] | accum["wyckoff_st"]
            | accum["wyckoff_spring"] | accum["wyckoff_sos"] | accum["wyckoff_lps"]
        )
        pct_flagged = has_event.mean()
        print(f"  Accum bars with ≥1 event: {pct_flagged:.1%}")
        if pct_flagged < 0.30:
            print(f"  WARN: Low event density in accumulation phase ({pct_flagged:.1%})")


def test_distribution_event_coherence() -> None:
    df = _make_synthetic_bars(300)
    config = WyckoffConfig()
    result = detect_wyckoff(df, config)
    dist = result[result["wyckoff_distribution"] == 1]
    if len(dist) > 0:
        has_event = (
            dist["wyckoff_upthrust"] | dist["wyckoff_sow"] | dist["wyckoff_lpsy"]
        )
        pct_flagged = has_event.mean()
        print(f"  Distribution bars with ≥1 event: {pct_flagged:.1%}")
        if pct_flagged < 0.20:
            print(f"  WARN: Low event density in distribution phase ({pct_flagged:.1%})")


def test_mutual_exclusivity() -> None:
    df = _make_synthetic_bars(300)
    config = WyckoffConfig()
    result = detect_wyckoff(df, config)
    both = (
        (result["wyckoff_accumulation"] == 1)
        & (result["wyckoff_distribution"] == 1)
    ).sum()
    assert both == 0, f"Found {both} bars marked both accumulation AND distribution"
    print(f"  OK: Mutually exclusive (0 bars with both)")


def test_non_null_values() -> None:
    df = _make_synthetic_bars(300)
    config = WyckoffConfig()
    result = detect_wyckoff(df, config)
    assert result["wyckoff_phase"].notna().all(), "wyckoff_phase has nulls"
    assert result["wyckoff_sc"].notna().all(), "wyckoff_sc has nulls"
    assert result["wyckoff_upthrust"].notna().all(), "wyckoff_upthrust has nulls"
    print(f"  OK: No nulls in key columns")


if __name__ == "__main__":
    print("=== Wyckoff Detector Validation ===\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            print(f"\n{name}:")
            try:
                fn()
                print(f"  PASS")
            except Exception as e:
                print(f"  FAIL: {e}")
    print("\n=== Done ===")
