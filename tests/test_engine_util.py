"""Verificación causal de utilidades compartidas del motor."""

from __future__ import annotations

import pandas as pd

from engine._util import avg_candle_range


def test_avg_candle_range_no_retroactive_future_fill():
    """El calentamiento no puede copiar un rango de una vela futura."""
    frame = pd.DataFrame({
        "high": [101.0, 110.0, 110.0, 110.0],
        "low": [100.0, 100.0, 100.0, 100.0],
    })
    out = avg_candle_range(frame, window=4)
    assert out.iloc[0] == 1.0
    assert out.iloc[1] == 5.5
