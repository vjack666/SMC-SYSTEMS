"""Capa 1: HTF structure desde M5.

Reglas hard:
- H1 = 12 velas M5
- H4 = 48 velas M5
- D1 = 288 velas M5
- Agregacion estricta: open=primera vela, high=max, low=min, close=ultima, volume=suma
- No se inventan velas. Si faltan, no se forma TF hasta tener las N velas.
"""
from __future__ import annotations

from typing import Any

OHLCVBar = dict[str, Any]
HTFBar = dict[str, Any]
AuditState = dict[str, Any]


def build_htf_chain(
    htf_chain: dict[str, HTFBar],
    m5_bars: list[OHLCVBar],
    bar_index_m5: int,
) -> dict[str, HTFBar]:
    """Reconstruye H1/H4/D1 segun la vela M5 actual."""
    if bar_index_m5 < 11:
        return htf_chain
    needed = {"H1": 12, "H4": 48, "D1": 288}
    for tf, n in needed.items():
        if bar_index_m5 % n != n - 1:
            continue
        start = bar_index_m5 - n + 1
        if start < 0 or len(m5_bars) < bar_index_m5 + 1:
            continue
        window = m5_bars[start : bar_index_m5 + 1]
        if len(window) != n:
            continue
        highs = [b["high"] for b in window]
        lows = [b["low"] for b in window]
        volumes = [b.get("volume", 0.0) for b in window]
        htf_chain[tf] = {
            "timestamp": window[0]["timestamp"],
            "open": float(window[0]["open"]),
            "high": float(max(highs)),
            "low": float(min(lows)),
            "close": float(window[-1]["close"]),
            "volume": float(sum(volumes)),
            "tf": tf,
            "bar_index_m5": bar_index_m5,
        }
    return htf_chain


def compute_htf_bias(
    htf_history: list[dict[str, Any]],
    lookback: int = 5,
) -> str:
    """Sesgo HTF: compara close vs open de hace lookback periodos.

    Si no hay suficientes datos -> RANGE.
    """
    if len(htf_history) < lookback + 1:
        return "RANGE"
    current_close = float(htf_history[-1]["close"])
    past_open = float(htf_history[-(lookback + 1)]["open"])
    if current_close > past_open:
        return "BULLISH"
    if current_close < past_open:
        return "BEARISH"
    return "RANGE"


def update_m5_state(state: AuditState, m5_bar: OHLCVBar) -> AuditState:
    """Agrega la vela M5 al estado y reevalua H1/H4/D1 si corresponde."""
    m5_bars = list(state.get("m5_bars", [])) + [m5_bar]
    bar_index = len(m5_bars) - 1
    htf_chain = dict(state.get("htf_chain", {}))
    build_htf_chain(htf_chain, m5_bars, bar_index)
    last_h4 = htf_chain.get("H4")
    new_state = dict(state)
    new_state["m5_bars"] = m5_bars
    new_state["bar_index_m5"] = bar_index
    new_state["timestamp"] = m5_bar["timestamp"]
    new_state["htf_chain"] = htf_chain
    new_state["last_h4_high"] = float(last_h4["high"]) if last_h4 else None
    new_state["last_h4_low"] = float(last_h4["low"]) if last_h4 else None
    return new_state
