"""Tests engine.turtle_soup — barrido PDH/PDL + reversion (geometria)."""
import numpy as np
import pandas as pd
from engine.turtle_soup import is_turtle_soup


def _frames():
    # M15: dia previo con pdh=1.10 pdl=1.00; dia sweep rompe pdh a 1.11 y revierte bajista
    idx = pd.date_range("2026-01-05 00:00", "2026-01-06 12:00", freq="15min", tz="UTC")
    n = len(idx)
    high = np.ones(n) * 1.05
    low = np.ones(n) * 1.02
    close = np.ones(n) * 1.035
    open_ = np.ones(n) * 1.035
    # dia previo (2026-01-05): pdh 1.10 pdl 1.00
    prev = idx.date == pd.Timestamp("2026-01-05").date()
    high[prev] = np.where(np.arange(n)[prev] % 2 == 0, 1.10, 1.05)
    low[prev] = np.where(np.arange(n)[prev] % 2 == 0, 1.00, 1.02)
    # sweep del pdh en dia actual: una vela high=1.11 (rompe pdh), luego cuerpo bajista
    sweep_i = int(np.where(idx.date == pd.Timestamp("2026-01-06").date())[0][0]) + 5
    high[sweep_i] = 1.11
    close[sweep_i] = 1.105
    open_[sweep_i] = 1.108
    # reversion bajista ~3 velas despues
    hi = sweep_i + 3
    open_[hi] = 1.10
    close[hi] = 1.04
    df = pd.DataFrame({"time": idx, "open": open_, "high": high, "low": low, "close": close})
    return {"M15": df}


def test_turtle_soup_short_detected():
    frames = _frames()
    sweep_ts = frames["M15"].iloc[int(np.where(frames["M15"]["high"] == 1.11)[0][0])]["time"]
    ok, meta = is_turtle_soup(sweep_ts, -1, frames, "M15")
    assert ok is True
    assert meta["ts_broke_pdh"] is True
