"""Capa 2: BOS detection sobre cierre M5 vs nivel H4.

Reglas:
- BOS alcista: m5.close > last_h4_high
- BOS bajista: m5.close < last_h4_low
- strength_pct = (close - level) / level * 100
- Traza forense por evento.
"""
from __future__ import annotations

from typing import Any

AuditState = dict[str, Any]


def _pct(price: float, level: float) -> float:
    return abs(price - level) / level * 100.0 if level else 0.0


def update_bos(state: AuditState) -> AuditState:
    """Detecta BOS si el cierre M5 rompe el H4 high/low anterior."""
    m5_bars = list(state.get("m5_bars", []))
    if not m5_bars:
        return state
    bar = m5_bars[-1]
    close = float(bar["close"])
    ts = bar["timestamp"]
    bar_index = int(state.get("bar_index_m5", -1))
    last_h4_high = state.get("last_h4_high")
    last_h4_low = state.get("last_h4_low")
    entities = dict(state.get("entities", {}))
    trace = list(state.get("trace", []))

    new_events: list[dict[str, Any]] = []

    last_bos_events = list(state.get("last_bos_events", []))
    last_bullish_price = state.get("last_bullish_bos")
    last_bearish_price = state.get("last_bearish_bos")

    if last_h4_high is not None and close > last_h4_high:
        # Solo emitir BOS alcista si no hubo uno en el mismo nivel
        if last_bullish_price is None or abs(last_bullish_price - last_h4_high) > 1e-9:
            bos_id = f"bos_{bar_index}_bullish"
            entities[bos_id] = {
                "bos_id": bos_id,
                "direction": "BULLISH",
                "level": float(last_h4_high),
                "break_bar": bar_index,
                "timestamp": ts,
                "tf": "H4",
                "strength_pct": _pct(close, last_h4_high),
                "status": "ACTIVE",
                "confirmed_by_bars": 0,
            }
            trace.append({
                "bar_index_m5": bar_index,
                "timestamp": ts,
                "layer": "bos",
                "event": "bos_detected",
                "entity_id": bos_id,
                "entity_type": "bos",
                "direction": "BULLISH",
                "price": float(last_h4_high),
                "m5_bars_ago": 0,
                "previous_state": None,
                "new_state": "ACTIVE",
                "reason": f"close={close:.6f} > h4_high={last_h4_high:.6f}",
            })
            new_events.append(entities[bos_id])
            state["last_bullish_bos"] = float(last_h4_high)

    if last_h4_low is not None and close < last_h4_low:
        # Solo emitir BOS bajista si no hubo uno en el mismo nivel
        if last_bearish_price is None or abs(last_bearish_price - last_h4_low) > 1e-9:
            bos_id = f"bos_{bar_index}_bearish"
            entities[bos_id] = {
                "bos_id": bos_id,
                "direction": "BEARISH",
                "level": float(last_h4_low),
                "break_bar": bar_index,
                "timestamp": ts,
                "tf": "H4",
                "strength_pct": _pct(close, last_h4_low),
                "status": "ACTIVE",
                "confirmed_by_bars": 0,
            }
            trace.append({
                "bar_index_m5": bar_index,
                "timestamp": ts,
                "layer": "bos",
                "event": "bos_detected",
                "entity_id": bos_id,
                "entity_type": "bos",
                "direction": "BEARISH",
                "price": float(last_h4_low),
                "m5_bars_ago": 0,
                "previous_state": None,
                "new_state": "ACTIVE",
                "reason": f"close={close:.6f} < h4_low={last_h4_low:.6f}",
            })
            new_events.append(entities[bos_id])
            state["last_bearish_bos"] = float(last_h4_low)

    new_state = dict(state)
    new_state["entities"] = entities
    new_state["trace"] = trace
    new_state["last_bos_events"] = new_events
    return new_state
