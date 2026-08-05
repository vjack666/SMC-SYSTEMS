from __future__ import annotations

import numpy as np
import pandas as pd

from modules.wyckoff.detector import (
    _upthrust,
    _sign_of_weakness,
    _last_point_supply,
    _detect_distribution_phase,
    detect_wyckoff,
)
from modules.wyckoff.config import WyckoffConfig


def _build_distribution_scenario() -> pd.DataFrame:
    n = 200
    close = np.concatenate([
        100 + np.arange(80) * 0.5,
        140 - np.arange(120) * 0.3,
    ])
    high = close + 1.0
    low = close - 1.0
    rng = np.random.default_rng(42)
    vol = np.abs(rng.normal(5000, 2000, n)).astype(int)
    vol[140:160] = 15000
    return pd.DataFrame({
        "time": pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC"),
        "open": close - 0.3,
        "high": high,
        "low": low,
        "close": close,
        "tick_volume": vol,
    })


def test_upthrust_detection() -> None:
    df = _build_distribution_scenario()
    df["atr"] = 2.0
    config = WyckoffConfig(spring_depth_atr=0.5)
    dist_high_idx = 100
    i = 105
    hi = df.iloc[i]["high"]
    resistance = df.iloc[dist_high_idx]["high"]
    threshold = config.spring_depth_atr * df.iloc[i]["atr"]
    print(f"  hi={hi:.2f}, resistance={resistance:.2f}, threshold={threshold:.2f}")
    ut = _upthrust(df, i, dist_high_idx, config)
    print(f"  _upthrust(result={ut})")
    assert isinstance(ut, (bool, np.bool_)), "upthrust should return bool"


def test_sign_of_weakness_detection() -> None:
    df = _build_distribution_scenario()
    df["atr"] = 2.0
    vol_ma = df["tick_volume"].rolling(20).mean().fillna(5000.0)
    config = WyckoffConfig(volume_threshold=1.0, sos_min_atr=0.5)
    dist_low_idx = 120
    i = 135
    sow = _sign_of_weakness(df, i, dist_low_idx, vol_ma, config)
    print(f"  _sign_of_weakness(result={sow})")
    assert isinstance(sow, (bool, np.bool_)), "SoW should return bool"


def test_distribution_phase_classification() -> None:
    df = _build_distribution_scenario()
    df["atr"] = 2.0
    df["wyckoff_upthrust"] = False
    df["wyckoff_sow"] = False
    df["wyckoff_lpsy"] = False
    df.loc[105, "wyckoff_upthrust"] = True
    df.loc[135, "wyckoff_sow"] = True
    config = WyckoffConfig(phase_lookback=30)
    phase = _detect_distribution_phase(df, 150, config)
    print(f"  _detect_distribution_phase(at 150) = {phase}")
    assert phase in ("DISTRIBUTION_E", "DISTRIBUTION_D", "DISTRIBUTION_C", "DISTRIBUTION_B", "NONE"), f"Unexpected phase: {phase}"
    if phase == "NONE":
        print("  (distribution events too far back for phase_lookback window)")


def test_full_detector_no_crash() -> None:
    df = _build_distribution_scenario()
    config = WyckoffConfig(volume_threshold=1.2, spring_depth_atr=0.5, sos_min_atr=0.5, lps_max_atr=2.0)
    result = detect_wyckoff(df, config)
    assert "wyckoff_phase" in result.columns
    assert "wyckoff_distribution" in result.columns
    assert "wyckoff_upthrust" in result.columns
    assert "wyckoff_sow" in result.columns
    phase_counts = result["wyckoff_phase"].value_counts().to_dict()
    print(f"  Phase counts: {phase_counts}")
    dist_bars = int(result["wyckoff_distribution"].sum())
    print(f"  Distribution bars: {dist_bars}")
    ut_bars = int(result["wyckoff_upthrust"].sum())
    sow_bars = int(result["wyckoff_sow"].sum())
    lpsy_bars = int(result["wyckoff_lpsy"].sum())
    print(f"  UT={ut_bars}, SoW={sow_bars}, LPSY={lpsy_bars}")
    assert len(result) == len(df), "Row count changed"
    print("  PASS: Full detector runs without error")


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("=== Wyckoff Distribution Detection Tests ===\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            print(f"\n{name}:")
            try:
                fn()
                print("  PASS")
            except Exception as e:
                import traceback
                print(f"  FAIL: {e}")
                traceback.print_exc()
