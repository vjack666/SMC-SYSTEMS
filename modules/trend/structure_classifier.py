from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

StructureLabel = Literal["BULLISH", "BEARISH", "RANGING"]


@dataclass(frozen=True)
class StructureResult:
    structure: StructureLabel
    last_hh: float | None
    last_hl: float | None
    last_lh: float | None
    last_ll: float | None
    swing_sequence: list[str]


def _extract_swings(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    highs = frame.loc[frame["swing_high"], ["time", "high"]].copy()
    lows = frame.loc[frame["swing_low"], ["time", "low"]].copy()
    highs = highs.rename(columns={"high": "price"}).reset_index(names="bar_index")
    lows = lows.rename(columns={"low": "price"}).reset_index(names="bar_index")
    return highs, lows


def _sequence_from_prices(prices: pd.Series, up_tag: str, down_tag: str) -> list[str]:
    labels: list[str] = []
    for i in range(1, len(prices)):
        labels.append(up_tag if float(prices.iloc[i]) > float(prices.iloc[i - 1]) else down_tag)
    return labels


def classify_structure(frame: pd.DataFrame, n_swings: int = 3) -> StructureResult:
    """Classify market structure from swing highs/lows.

    Rules:
    - BULLISH: last 2 highs ascending and last 2 lows ascending.
    - BEARISH: last 2 highs descending and last 2 lows descending.
    - Otherwise RANGING.
    """
    highs, lows = _extract_swings(frame)

    highs_tail = highs.tail(max(2, n_swings))
    lows_tail = lows.tail(max(2, n_swings))

    if len(highs_tail) < 2 or len(lows_tail) < 2:
        return StructureResult("RANGING", None, None, None, None, [])

    highs_prices = highs_tail["price"].reset_index(drop=True)
    lows_prices = lows_tail["price"].reset_index(drop=True)

    highs_up = float(highs_prices.iloc[-1]) > float(highs_prices.iloc[-2])
    lows_up = float(lows_prices.iloc[-1]) > float(lows_prices.iloc[-2])

    highs_down = float(highs_prices.iloc[-1]) < float(highs_prices.iloc[-2])
    lows_down = float(lows_prices.iloc[-1]) < float(lows_prices.iloc[-2])

    structure: StructureLabel = "RANGING"
    if highs_up and lows_up:
        structure = "BULLISH"
    elif highs_down and lows_down:
        structure = "BEARISH"

    high_seq = _sequence_from_prices(highs_prices, "HH", "LH")
    low_seq = _sequence_from_prices(lows_prices, "HL", "LL")

    seq_events: list[tuple[int, str]] = []
    if len(high_seq) > 0:
        high_indices = highs_tail["bar_index"].iloc[1:].tolist()
        seq_events.extend([(int(idx), tag) for idx, tag in zip(high_indices, high_seq)])
    if len(low_seq) > 0:
        low_indices = lows_tail["bar_index"].iloc[1:].tolist()
        seq_events.extend([(int(idx), tag) for idx, tag in zip(low_indices, low_seq)])

    seq_events.sort(key=lambda item: item[0])
    swing_sequence = [item[1] for item in seq_events]

    last_hh = float(highs_prices.iloc[-1]) if structure == "BULLISH" else None
    last_hl = float(lows_prices.iloc[-1]) if structure == "BULLISH" else None
    last_lh = float(highs_prices.iloc[-1]) if structure == "BEARISH" else None
    last_ll = float(lows_prices.iloc[-1]) if structure == "BEARISH" else None

    return StructureResult(
        structure=structure,
        last_hh=last_hh,
        last_hl=last_hl,
        last_lh=last_lh,
        last_ll=last_ll,
        swing_sequence=swing_sequence,
    )


def consecutive_structure_count(result: StructureResult) -> int:
    """Count consecutive terminal structure tags (HH/HL or LH/LL) from sequence end."""
    if not result.swing_sequence:
        return 0

    if result.structure == "BULLISH":
        valid = {"HH", "HL"}
    elif result.structure == "BEARISH":
        valid = {"LH", "LL"}
    else:
        return 0

    count = 0
    for tag in reversed(result.swing_sequence):
        if tag in valid:
            count += 1
        else:
            break
    return count
