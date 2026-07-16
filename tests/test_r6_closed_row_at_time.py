"""tests/test_r6_closed_row_at_time.py — R6.1 (G1): HTF closed-only.

RED: `closed_row_at_time(df, t, duration)` es la UNICA via para leer HTF en
el backtest. Exige que la barra HTF haya CERRADO (time + duration <= t);
nunca devuelve una vela HTF en formacion (look-ahead cross-timeframe).

Contrato:
- `duration` es OBLIGATORIO (no opcional como el viejo row_at_time sin freq).
- Si `t` cae a mitad de una vela H4 (aun abierta), devuelve la H4 ANTERIOR
  ya cerrada, no la en formacion.
- Si `t` es exactamente el open de la H4, la H4 aun no cerro -> devuelve la
  anterior (corte estricto, como el bug residual de 2026-07-13).

Esto elimina el look-ahead de raiz: los call sites HTF migran a esta funcion
y dejan de poder leer velas sin cerrar aunque "se les olvide" pasar freq.
"""

from __future__ import annotations

import pandas as pd
import pytest

from ict_backtest._util import closed_merge_asof, closed_row_at_time


def _h4() -> pd.DataFrame:
    df = pd.DataFrame({
        "time": ["2024-01-01 00:00", "2024-01-01 04:00",
                 "2024-01-01 08:00", "2024-01-01 12:00"],
        "close": [1.0, 2.0, 3.0, 4.0],
    })
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df


def _ltf_mid_h4() -> pd.DataFrame:
    """LTF con un barra exactamente a mitad de la H4 08:00-12:00 (10:00)."""
    ltf = pd.DataFrame({
        "time": ["2024-01-01 07:55", "2024-01-01 10:00", "2024-01-01 11:55"],
    })
    ltf["time"] = pd.to_datetime(ltf["time"], utc=True)
    return ltf


def test_closed_row_at_time_mid_bar_returns_previous_closed():
    """LTF a mitad de H4 (09:03) -> H4 anterior ya cerrada (close=2.0)."""
    h4 = _h4()
    row = closed_row_at_time(h4, "2024-01-01 09:03", duration="4h")
    assert float(row["close"]) == 2.0, (
        f"devolvio vela HTF sin cerrar (close={row['close']}), "
        f"esperaba la anterior ya cerrada (close=2.0)")


def test_closed_row_at_time_exact_open_returns_previous_closed():
    """LTF exacto en open H4 (08:00) -> H4 aun no cerro -> anterior (close=2.0)."""
    h4 = _h4()
    row = closed_row_at_time(h4, "2024-01-01 08:00", duration="4h")
    assert float(row["close"]) == 2.0, (
        f"bug residual: devolvio vela HTF sin cerrar (close={row['close']}), "
        f"esperaba la anterior ya cerrada (close=2.0)")


def test_closed_row_at_time_duration_is_mandatory():
    """Sin duration -> error: el contrato closed-only no acepta 'modo abierto'."""
    h4 = _h4()
    with pytest.raises(TypeError):
        closed_row_at_time(h4, "2024-01-01 09:03")  # type: ignore[call-arg]


def test_closed_row_at_time_after_close_returns_current():
    """LTF despues del cierre de la H4 (12:01) -> la H4 08:00 ya cerro."""
    h4 = _h4()
    row = closed_row_at_time(h4, "2024-01-01 12:01", duration="4h")
    assert float(row["close"]) == 3.0, (
        f"esperaba H4 08:00 cerrada (close=3.0), got {row['close']}")


def test_closed_merge_asof_mid_bar_sees_only_closed_h4():
    """LTF a mitad de H4 (10:00) NO ve la H4 08:00 en formacion.

    La H4 08:00 cierra 12:00; a las 10:00 la vela aun esta abierta. El merge
    closed-only debe unir la H4 ANTERIOR ya cerrada (04:00, close=2.0), no la
    en formacion (08:00, close=3.0). Esto mata el look-ahead en trend_context.
    """
    h4 = _h4().rename(columns={"close": "h4_close"})
    ltf = _ltf_mid_h4()
    merged = closed_merge_asof(ltf, h4, "4h")
    # La barra del LTF a las 10:00 debe haber tomado la H4 04:00 (close=2.0),
    # no la 08:00 en formacion (close=3.0).
    mid = merged.iloc[1]
    assert float(mid["h4_close"]) == 2.0, (
        f"look-ahead: vio H4 en formacion (close={mid['h4_close']}), "
        f"esperaba H4 cerrada anterior (close=2.0)")
    # El 'time' del resultado se restaura al del LTF (no el cortado).
    assert pd.Timestamp(mid["time"]).strftime("%H:%M") == "10:00"


def test_closed_merge_asof_after_close_sees_current_h4():
    """LTF despues del cierre de la H4 (12:01) -> la H4 08:00 ya cerro."""
    h4 = _h4().rename(columns={"close": "h4_close"})
    ltf = pd.DataFrame({"time": ["2024-01-01 12:01"]})
    ltf["time"] = pd.to_datetime(ltf["time"], utc=True)
    merged = closed_merge_asof(ltf, h4, "4h")
    assert float(merged.iloc[0]["h4_close"]) == 3.0, (
        f"esperaba H4 08:00 cerrada (close=3.0), got {merged.iloc[0]['h4_close']}")
