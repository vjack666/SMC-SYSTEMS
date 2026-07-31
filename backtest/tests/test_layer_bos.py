"""TDD tests for layer_bos."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from datetime import datetime
import pytest

from backtest.layers.layer_bos import update_bos


def _bar(ts, close):
    return {"timestamp": ts, "open": close, "high": close, "low": close, "close": close, "volume": 0.0}


def test_bos_bullish_detected():
    state = {
        "m5_bars": [_bar(datetime(2026,1,1,0,0), 1.0)],
        "bar_index_m5": 0,
        "timestamp": datetime(2026,1,1,0,0),
        "htf_chain": {"H4": {"high": 1.001, "low": 0.999}},
        "last_h4_high": 1.001,
        "last_h4_low": 0.999,
        "entities": {},
        "trace": [],
    }
    state["m5_bars"].append(_bar(datetime(2026,1,1,0,5), 1.002))
    state["bar_index_m5"] = 1
    state["timestamp"] = datetime(2026,1,1,0,5)
    out = update_bos(state)
    events = out.get("last_bos_events", [])
    assert len(events) == 1
    assert events[0]["direction"] == "BULLISH"
    assert events[0]["status"] == "ACTIVE"
    assert len(out["trace"]) == 1


def test_bos_bearish_detected():
    state = {
        "m5_bars": [_bar(datetime(2026,1,1,0,0), 1.0)],
        "bar_index_m5": 0,
        "timestamp": datetime(2026,1,1,0,0),
        "htf_chain": {"H4": {"high": 1.001, "low": 0.999}},
        "last_h4_high": 1.001,
        "last_h4_low": 0.999,
        "entities": {},
        "trace": [],
    }
    state["m5_bars"].append(_bar(datetime(2026,1,1,0,5), 0.998))
    state["bar_index_m5"] = 1
    state["timestamp"] = datetime(2026,1,1,0,5)
    out = update_bos(state)
    events = out.get("last_bos_events", [])
    assert len(events) == 1
    assert events[0]["direction"] == "BEARISH"
    assert events[0]["status"] == "ACTIVE"
    assert len(out["trace"]) == 1
