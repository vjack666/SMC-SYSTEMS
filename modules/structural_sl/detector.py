"""
Structural Stop Loss Detection Module.

Identifies the origin swing that initiated the BOS+FVG+Entry sequence,
and calculates the structural stop loss price based on ICT principles.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class StructuralStop:
    """Represents a structural stop level with audit trail."""
    
    origin_swing_price: float  # Price of the origin swing
    origin_swing_idx: int      # Index of the origin swing
    sweep_price: float         # Price where liquidity was swept
    sweep_idx: int             # Index of the sweep
    bos_break_price: float     # Price where BOS was broken
    bos_break_idx: int         # Index of BOS break
    fvg_entry_price: float     # Entry price in FVG
    structural_stop_price: float  # Structural SL (= origin swing price)
    stop_distance_pips: float     # Distance in pips
    stop_distance_atr: float      # Distance in ATR units
    direction: int             # 1 for LONG, -1 for SHORT


def detect_origin_swing(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    current_idx: int,
    lookback: int = 20,
    direction: int = 1,
) -> tuple[float, int]:
    """
    Detect the origin swing before the BOS sequence.
    
    For LONG:
      - Origin swing LOW that will support the structural stop
      - Returns the lowest low in the lookback window (stop placement point)
    
    For SHORT:
      - Origin swing HIGH that will support the structural stop
      - Returns the highest high in the lookback window (stop placement point)
    
    Args:
        high: array of high prices
        low: array of low prices
        close: array of close prices
        current_idx: current index in the sequence
        lookback: how many bars back to look for origin swing
        direction: 1 for LONG, -1 for SHORT
    
    Returns:
        (origin_swing_price, origin_swing_idx)
    """
    start_idx = max(0, current_idx - lookback)
    
    if direction == 1:
        # LONG: stop placement uses the lowest low in lookback window
        window = low[start_idx:current_idx]
        origin_idx = start_idx + np.argmin(window)
        origin_price = float(low[origin_idx])
    else:
        # SHORT: stop placement uses the highest high in lookback window
        window = high[start_idx:current_idx]
        origin_idx = start_idx + np.argmax(window)
        origin_price = float(high[origin_idx])
    
    return origin_price, origin_idx


def detect_liquidity_sweep(
    high: np.ndarray,
    low: np.ndarray,
    origin_price: float,
    origin_idx: int,
    current_idx: int,
    direction: int = 1,
) -> tuple[Optional[float], Optional[int]]:
    """
    Detect if liquidity was swept at the origin level after BOS.
    
    For LONG:
      - Origin is the lowest LOW; sweep validates that price touched/broke above origin
      - Search in highs after origin to confirm sweep occurred
    
    For SHORT:
      - Origin is the highest HIGH; sweep validates that price touched/broke below origin
      - Search in lows after origin to confirm sweep occurred
    
    Args:
        high: array of high prices
        low: array of low prices
        origin_price: price of the origin swing level
        origin_idx: index of the origin swing
        current_idx: current index (entry point)
        direction: 1 for LONG, -1 for SHORT
    
    Returns:
        (sweep_price, sweep_idx) or (None, None) if no sweep detected
    """
    if direction == 1:
        # LONG: look for high >= origin low (sweep/break above the low)
        search_window = high[origin_idx + 1 : current_idx]
        if len(search_window) == 0:
            return None, None
        mask = search_window >= origin_price
        if not np.any(mask):
            return None, None
        sweep_idx = origin_idx + 1 + np.argmax(mask)
        sweep_price = float(high[sweep_idx])
    else:
        # SHORT: look for low <= origin high (sweep/break below the high)
        search_window = low[origin_idx + 1 : current_idx]
        if len(search_window) == 0:
            return None, None
        mask = search_window <= origin_price
        if not np.any(mask):
            return None, None
        sweep_idx = origin_idx + 1 + np.argmax(mask)
        sweep_price = float(low[sweep_idx])
    
    return sweep_price, sweep_idx


def calculate_structural_stop(
    df: pd.DataFrame,
    entry_idx: int,
    direction: int,
    lookback_origin: int = 20,
    atr_col: str = "atr",
) -> Optional[StructuralStop]:
    """
    Calculate structural stop loss from origin swing to entry.
    
    For LONG: stop is placed at the lowest low that originated the upward BOS
    For SHORT: stop is placed at the highest high that originated the downward BOS
    
    Args:
        df: OHLC dataframe with columns: high, low, close, atr
        entry_idx: index of the entry candle
        direction: 1 for LONG, -1 for SHORT
        lookback_origin: how many bars to look back for origin swing
        atr_col: name of the ATR column
    
    Returns:
        StructuralStop object or None if calculation fails
    """
    if entry_idx < lookback_origin + 2:
        return None
    
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    atr = df[atr_col].values if atr_col in df.columns else None
    
    entry_price = float(close[entry_idx])
    
    # 1. Detect origin swing
    origin_price, origin_idx = detect_origin_swing(
        high, low, close, entry_idx, lookback_origin, direction
    )
    
    # 2. Detect liquidity sweep
    sweep_price, sweep_idx = detect_liquidity_sweep(
        high, low, origin_price, origin_idx, entry_idx, direction
    )
    
    if sweep_idx is None:
        return None
    
    # 3. If origin swing price is on the wrong side of entry, search farther back
    # This handles cases where price retraced within the FVG formation
    if direction == 1 and origin_price >= entry_price:
        # LONG: origin is above entry, search farther back for the true low
        extended_lookback = min(entry_idx, lookback_origin * 2)
        extended_origin_price, extended_origin_idx = detect_origin_swing(
            high, low, close, entry_idx, extended_lookback, direction
        )
        if extended_origin_price < entry_price:
            origin_price, origin_idx = extended_origin_price, extended_origin_idx
    elif direction == -1 and origin_price <= entry_price:
        # SHORT: origin is below entry, search farther back for the true high
        extended_lookback = min(entry_idx, lookback_origin * 2)
        extended_origin_price, extended_origin_idx = detect_origin_swing(
            high, low, close, entry_idx, extended_lookback, direction
        )
        if extended_origin_price > entry_price:
            origin_price, origin_idx = extended_origin_price, extended_origin_idx
    
    # 4. If still invalid, the structure is malformed - skip this trade
    if (direction == 1 and origin_price >= entry_price) or (direction == -1 and origin_price <= entry_price):
        return None
    
    # 5. Structural SL is at origin swing price
    structural_sl = origin_price
    stop_distance_pips = abs(entry_price - structural_sl)
    
    # 6. Calculate distance in ATR
    atr_entry = float(atr[entry_idx]) if atr is not None else np.nan
    stop_distance_atr = stop_distance_pips / atr_entry if atr is not None and atr_entry > 0 else np.nan
    
    return StructuralStop(
        origin_swing_price=origin_price,
        origin_swing_idx=origin_idx,
        sweep_price=sweep_price,
        sweep_idx=sweep_idx,
        bos_break_price=float(close[sweep_idx]),  # Simplified: BOS at sweep candle close
        bos_break_idx=sweep_idx,
        fvg_entry_price=entry_price,
        structural_stop_price=structural_sl,
        stop_distance_pips=stop_distance_pips,
        stop_distance_atr=stop_distance_atr,
        direction=direction,
    )


def apply_structural_stops_to_frame(
    df: pd.DataFrame,
    signal_indices: list[int],
    signal_directions: list[int],
    lookback_origin: int = 20,
) -> pd.DataFrame:
    """
    Apply structural stop calculation to a list of signal indices.
    
    Args:
        df: OHLC dataframe
        signal_indices: list of entry indices
        signal_directions: list of directions (1 or -1)
        lookback_origin: lookback window for origin swing detection
    
    Returns:
        DataFrame with structural stop columns added
    """
    output = df.copy()
    output["structural_stop_price"] = np.nan
    output["stop_distance_pips"] = np.nan
    output["stop_distance_atr"] = np.nan
    output["origin_swing_price"] = np.nan
    output["sweep_price"] = np.nan
    output["bos_break_price"] = np.nan
    
    for entry_idx, direction in zip(signal_indices, signal_directions):
        stop = calculate_structural_stop(df, entry_idx, direction, lookback_origin)
        if stop is not None:
            output.at[entry_idx, "structural_stop_price"] = stop.structural_stop_price
            output.at[entry_idx, "stop_distance_pips"] = stop.stop_distance_pips
            output.at[entry_idx, "stop_distance_atr"] = stop.stop_distance_atr
            output.at[entry_idx, "origin_swing_price"] = stop.origin_swing_price
            output.at[entry_idx, "sweep_price"] = stop.sweep_price
            output.at[entry_idx, "bos_break_price"] = stop.bos_break_price
    
    return output
