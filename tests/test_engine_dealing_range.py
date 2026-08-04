"""Tests del dealing range HTF (engine/dealing_range.py). Datos sintéticos deterministas."""

from __future__ import annotations

import pandas as pd
import pytest

from engine.dealing_range import compute_dealing_range, dealing_range_htf


class _FakeBias:
    """Stub con la misma superficie que HtfBias (.direction/.aligned)."""

    def __init__(self, direction: str) -> None:
        self.direction = direction

    @property
    def aligned(self) -> bool:
        return self.direction != "NEUTRAL"


def _frame(closes: list[float]) -> pd.DataFrame:
    # Rango fijo 100-200 en todas las velas: mid = 150.
    n = len(closes)
    return pd.DataFrame(
        {
            "high": [200.0] * n,
            "low": [100.0] * n,
            "close": closes,
        }
    )


def test_dealing_range_marks_discount_below_mid():
    out = compute_dealing_range(_frame([120.0]), lookback=5)
    assert out["zone_mid"].iloc[-1] == pytest.approx(150.0)
    assert out["premium_discount_zone"].iloc[-1] == "DISCOUNT"
    assert out["premium_distance"].iloc[-1] < 0


def test_dealing_range_marks_premium_above_mid():
    out = compute_dealing_range(_frame([180.0]), lookback=5)
    assert out["premium_discount_zone"].iloc[-1] == "PREMIUM"
    assert out["premium_distance"].iloc[-1] > 0


def test_dealing_range_marks_ote_long_and_short_bands():
    # OTE_LONG: 62-79% de retroceso desde el máximo → 121..138 (descuento).
    assert compute_dealing_range(_frame([130.0]), lookback=5)["premium_discount_zone"].iloc[-1] == "OTE_LONG"
    # OTE_SHORT: 162..179 (premium).
    assert compute_dealing_range(_frame([170.0]), lookback=5)["premium_discount_zone"].iloc[-1] == "OTE_SHORT"


def test_dealing_range_htf_summary_keys_and_bias():
    res = dealing_range_htf(_frame([120.0]), _FakeBias("BULLISH"), lookback=5)
    assert set(res) == {"zone", "distance", "bias", "is_favorable"}
    assert res["bias"] == "BULLISH"
    assert isinstance(res["distance"], float)


@pytest.mark.parametrize(
    ("close", "bias", "expected_zone", "favorable"),
    [
        (120.0, "BULLISH", "DISCOUNT", True),
        (130.0, "BULLISH", "OTE_LONG", True),
        (180.0, "BULLISH", "PREMIUM", False),
        (180.0, "BEARISH", "PREMIUM", True),
        (170.0, "BEARISH", "OTE_SHORT", True),
        (120.0, "BEARISH", "DISCOUNT", False),
        (120.0, "NEUTRAL", "DISCOUNT", False),
        (180.0, "NEUTRAL", "PREMIUM", False),
    ],
)
def test_dealing_range_htf_is_favorable_matrix(close, bias, expected_zone, favorable):
    res = dealing_range_htf(_frame([close]), _FakeBias(bias), lookback=5)
    assert res["zone"] == expected_zone
    assert res["is_favorable"] is favorable


def test_dealing_range_htf_empty_frame_is_safe():
    empty = pd.DataFrame({"high": [], "low": [], "close": []})
    res = dealing_range_htf(empty, _FakeBias("BULLISH"))
    assert res["is_favorable"] is False
    assert res["zone"] == "OTE_NONE"
