"""Tests capa 3 CHOCH — lógica: último BOS de dirección contraria anterior."""
from __future__ import annotations

from datetime import datetime, timedelta
from backtest.layers.layer_choch import update_choch


def _bar(ts: datetime, o: float, h: float, l: float, c: float) -> dict:
    return {"timestamp": ts, "open": o, "high": h, "low": l, "close": c, "volume": 0.0}


def test_choch_bullish_detected():
    state = {
        "m5_bars": [
            _bar(datetime(2026, 1, 1, 0, 0), 1.0, 1.01, 0.999, 1.005),
            _bar(datetime(2026, 1, 1, 0, 5), 0.996, 1.0, 0.995, 0.998),
        ],
        "bar_index_m5": 1,
        "timestamp": datetime(2026, 1, 1, 0, 5),
        "last_h4_high": 1.008,
        "last_h4_low": 0.998,
        "entities": {},
        "trace": [
            {"layer": "bos", "event": "bos_detected", "direction": "BULLISH", "price": 1.001, "bar_index_m5": 0},
            {"layer": "bos", "event": "bos_detected", "direction": "BEARISH", "price": 0.995, "bar_index_m5": 1},
        ],
    }
    # Bar 2: último BOS es bearish; cerrar por encima del BOS bullish anterior=1.001
    state["m5_bars"].append(_bar(datetime(2026, 1, 1, 0, 10), 1.000, 1.003, 0.999, 1.002))
    state["bar_index_m5"] = 2
    state["timestamp"] = datetime(2026, 1, 1, 0, 10)
    out = update_choch(state)
    events = [e for e in out.get("last_choch_events", []) if e["direction"] == "BULLISH"]
    assert len(events) == 1
    assert events[0]["status"] == "PENDING"
    assert events[0]["price"] == 1.001


def test_choch_bearish_detected():
    state = {
        "m5_bars": [
            _bar(datetime(2026, 1, 1, 0, 0), 1.0, 1.01, 0.999, 1.005),
            _bar(datetime(2026, 1, 1, 0, 5), 0.996, 1.0, 0.995, 0.998),
        ],
        "bar_index_m5": 1,
        "timestamp": datetime(2026, 1, 1, 0, 5),
        "last_h4_high": 1.008,
        "last_h4_low": 0.998,
        "entities": {},
        "trace": [
            {"layer": "bos", "event": "bos_detected", "direction": "BEARISH", "price": 0.995, "bar_index_m5": 0},
            {"layer": "bos", "event": "bos_detected", "direction": "BULLISH", "price": 1.001, "bar_index_m5": 1},
        ],
    }
    # Bar 2: último BOS es bullish; cerrar por debajo del BOS bearish anterior=0.995
    state["m5_bars"].append(_bar(datetime(2026, 1, 1, 0, 10), 0.994, 0.997, 0.991, 0.993))
    state["bar_index_m5"] = 2
    state["timestamp"] = datetime(2026, 1, 1, 0, 10)
    out = update_choch(state)
    events = [e for e in out.get("last_choch_events", []) if e["direction"] == "BEARISH"]
    assert len(events) == 1
    assert events[0]["status"] == "PENDING"
    assert events[0]["price"] == 0.995


def test_choch_confirmed():
    state = {
        "m5_bars": [
            _bar(datetime(2026, 1, 1, 0, 0), 1.0, 1.01, 0.999, 1.005),
            _bar(datetime(2026, 1, 1, 0, 5), 0.996, 1.0, 0.995, 0.998),
        ],
        "bar_index_m5": 1,
        "timestamp": datetime(2026, 1, 1, 0, 5),
        "last_h4_high": 1.008,
        "last_h4_low": 0.998,
        "entities": {},
        "trace": [
            {"layer": "bos", "event": "bos_detected", "direction": "BULLISH", "price": 1.001, "bar_index_m5": 0},
            {"layer": "bos", "event": "bos_detected", "direction": "BEARISH", "price": 0.995, "bar_index_m5": 1},
        ],
    }
    # Bar 2: close > 1.001 -> PENDING
    state["m5_bars"].append(_bar(datetime(2026, 1, 1, 0, 10), 1.000, 1.003, 0.999, 1.002))
    state["bar_index_m5"] = 2
    state["timestamp"] = datetime(2026, 1, 1, 0, 10)
    out = update_choch(state)
    cid = [k for k, v in out["entities"].items() if v.get("entity_type") == "choch"][0]
    assert out["entities"][cid]["status"] == "PENDING"

    # Confirmar en la siguiente vela con close > nivel invalidado
    out["m5_bars"].append(_bar(datetime(2026, 1, 1, 0, 15), 1.002, 1.004, 1.001, 1.003))
    out["bar_index_m5"] = 3
    out["timestamp"] = datetime(2026, 1, 1, 0, 15)
    out2 = update_choch(out)
    assert out2["entities"][cid]["status"] == "CONFIRMED"
    assert out2["entities"][cid]["confirmation_bar"] == 3


def test_choch_expired():
    state = {
        "m5_bars": [
            _bar(datetime(2026, 1, 1, 0, 0), 1.0, 1.01, 0.999, 1.005),
            _bar(datetime(2026, 1, 1, 0, 5), 0.996, 1.0, 0.995, 0.998),
        ],
        "bar_index_m5": 1,
        "timestamp": datetime(2026, 1, 1, 0, 5),
        "last_h4_high": 1.008,
        "last_h4_low": 0.998,
        "entities": {},
        "trace": [
            {"layer": "bos", "event": "bos_detected", "direction": "BULLISH", "price": 1.001, "bar_index_m5": 0},
            {"layer": "bos", "event": "bos_detected", "direction": "BEARISH", "price": 0.995, "bar_index_m5": 1},
        ],
    }
    # Bar 2: close > 1.001 -> PENDING
    state["m5_bars"].append(_bar(datetime(2026, 1, 1, 0, 10), 1.000, 1.003, 0.999, 1.002))
    state["bar_index_m5"] = 2
    state["timestamp"] = datetime(2026, 1, 1, 0, 10)
    out = update_choch(state)
    cid = [k for k, v in out["entities"].items() if v.get("entity_type") == "choch"][0]

    base_ts = datetime(2026, 1, 1, 0, 15)
    for i in range(3, 52):
        ts = base_ts + timedelta(minutes=5 * (i - 2))
        out["m5_bars"].append(_bar(ts, 1.001, 1.003, 0.999, 1.002))
    out["bar_index_m5"] = 51
    out["timestamp"] = base_ts + timedelta(minutes=5 * 49)
    out2 = update_choch(out)
    assert out2["entities"][cid]["status"] == "EXPIRED"
