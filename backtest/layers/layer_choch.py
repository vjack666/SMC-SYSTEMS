"""Capa 3: CHOCH detection — cierre M5 vs nivel del BOS anterior de dirección contraria."""
from __future__ import annotations

from typing import Any

AuditState = dict[str, Any]


def update_choch(state: AuditState) -> AuditState:
    m5_bars = list(state.get("m5_bars", []))
    entities = dict(state.get("entities", {}))
    trace = list(state.get("trace", []))
    bar_index = int(state.get("bar_index_m5", -1))
    ts = state.get("timestamp")

    if len(m5_bars) < 2:
        return state

    new_events: list[dict[str, Any]] = []
    bos_events = [ev for ev in trace if ev.get("layer") == "bos" and ev.get("event") == "bos_detected"]

    if len(bos_events) < 2:
        return state

    last_bos = bos_events[-1]
    last_direction = last_bos["direction"]
    last_bar = int(last_bos["bar_index_m5"])

    if bar_index <= last_bar:
        return state

    prev_opposite_bos = None
    for ev in reversed(bos_events[:-1]):
        if ev["direction"] != last_direction:
            prev_opposite_bos = ev
            break

    if prev_opposite_bos is None:
        return state

    opp_price = float(prev_opposite_bos["price"])
    close = float(m5_bars[-1]["close"])

    if last_direction == "BEARISH" and close > opp_price:
        already_pending = any(
            ent.get("direction") == "BULLISH" and ent.get("invalidated_level") == opp_price
            for ent in entities.values()
            if ent.get("entity_type") == "choch" and ent.get("status") == "PENDING"
        )
        if not already_pending:
            choch_id = f"choch_{bar_index}_bullish"
            entities[choch_id] = {
                "choch_id": choch_id,
                "entity_type": "choch",
                "direction": "BULLISH",
                "price": opp_price,
                "invalidated_level": opp_price,
                "break_bar": bar_index,
                "timestamp": ts,
                "timeframe": "H4",
                "status": "PENDING",
                "confirmation_bar": None,
            }
            trace.append({
                "bar_index_m5": bar_index,
                "timestamp": ts,
                "layer": "choch",
                "event": "choch_detected",
                "entity_id": choch_id,
                "entity_type": "choch",
                "direction": "BULLISH",
                "price": opp_price,
                "m5_bars_ago": 0,
                "previous_state": None,
                "new_state": "PENDING",
                "reason": f"close={close:.6f} > prev_bearish_bos={opp_price:.6f}",
            })
            new_events.append(entities[choch_id])

    if last_direction == "BULLISH" and close < opp_price:
        already_pending = any(
            ent.get("direction") == "BEARISH" and ent.get("invalidated_level") == opp_price
            for ent in entities.values()
            if ent.get("entity_type") == "choch" and ent.get("status") == "PENDING"
        )
        if not already_pending:
            choch_id = f"choch_{bar_index}_bearish"
            entities[choch_id] = {
                "choch_id": choch_id,
                "entity_type": "choch",
                "direction": "BEARISH",
                "price": opp_price,
                "invalidated_level": opp_price,
                "break_bar": bar_index,
                "timestamp": ts,
                "timeframe": "H4",
                "status": "PENDING",
                "confirmation_bar": None,
            }
            trace.append({
                "bar_index_m5": bar_index,
                "timestamp": ts,
                "layer": "choch",
                "event": "choch_detected",
                "entity_id": choch_id,
                "entity_type": "choch",
                "direction": "BEARISH",
                "price": opp_price,
                "m5_bars_ago": 0,
                "previous_state": None,
                "new_state": "PENDING",
                "reason": f"close={close:.6f} < prev_bullish_bos={opp_price:.6f}",
            })
            new_events.append(entities[choch_id])

    pending_ids = [
        eid
        for eid, ent in entities.items()
        if ent.get("entity_type") == "choch" and ent.get("status") == "PENDING" and ent.get("break_bar") != bar_index
    ]
    for cid in pending_ids:
        ent = entities[cid]
        created_bar = int(ent["break_bar"])
        if bar_index - created_bar > 48:
            ent["status"] = "EXPIRED"
            trace.append({
                "bar_index_m5": bar_index,
                "timestamp": ts,
                "layer": "choch",
                "event": "choch_expired",
                "entity_id": cid,
                "entity_type": "choch",
                "direction": ent["direction"],
                "price": ent["invalidated_level"],
                "m5_bars_ago": bar_index - created_bar,
                "previous_state": "PENDING",
                "new_state": "EXPIRED",
                "reason": "max 48 bars sin confirmar",
            })
            continue
        inv_level = float(ent["invalidated_level"])
        if ent["direction"] == "BULLISH" and close > inv_level:
            ent["status"] = "CONFIRMED"
            ent["confirmation_bar"] = bar_index
            trace.append({
                "bar_index_m5": bar_index,
                "timestamp": ts,
                "layer": "choch",
                "event": "choch_confirmed",
                "entity_id": cid,
                "entity_type": "choch",
                "direction": "BULLISH",
                "price": inv_level,
                "m5_bars_ago": bar_index - created_bar,
                "previous_state": "PENDING",
                "new_state": "CONFIRMED",
                "reason": f"close={close:.6f} > level={inv_level:.6f}",
            })
        elif ent["direction"] == "BEARISH" and close < inv_level:
            ent["status"] = "CONFIRMED"
            ent["confirmation_bar"] = bar_index
            trace.append({
                "bar_index_m5": bar_index,
                "timestamp": ts,
                "layer": "choch",
                "event": "choch_confirmed",
                "entity_id": cid,
                "entity_type": "choch",
                "direction": "BEARISH",
                "price": inv_level,
                "m5_bars_ago": bar_index - created_bar,
                "previous_state": "PENDING",
                "new_state": "CONFIRMED",
                "reason": f"close={close:.6f} < level={inv_level:.6f}",
            })

    new_state = dict(state)
    new_state["entities"] = entities
    new_state["trace"] = trace
    new_state["last_choch_events"] = new_events
    return new_state
