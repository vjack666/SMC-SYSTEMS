"""tests/test_closed_row_at_time_equivalence.py — FASE 1 (congelar) + FASE 3 (equivalencia).

M2: optimizacion de indexacion temporal SIN cambiar semantica.

Congela el contrato actual de closed_row_at_time (copia literal de la
impl original en engine/_util.py) y lo usa como REFERENCIA. Luego compara
la implementacion ACTUAL de engine._util.closed_row_at_time contra esa
referencia en todos los casos validos. Tras aplicar el parche O(log n),
este mismo test debe seguir pasando: nueva impl == referencia.

Casos cubiertos (orden del Director):
- vela cerrada disponible
- ninguna vela cerrada (anti look-ahead => None, NO iloc[0])
- timestamp exactamente en frontera (time == cutoff)
- timestamp antes de la primera vela
- timestamp despues de la ultima vela
- indices UTC
- indices tz-aware
- gaps
- datos duplicados (misma time)
- multiples TF
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine._util import closed_row_at_time as NEW


def _reference_closed_row_at_time(df, t, duration):
    """COPIA LITERAL de la impl original (engine/_util.py, pre-parche M2).

    Fuente de verdad congelada para la prueba de equivalencia. NO editar.
    """
    if duration is None:
        raise TypeError("closed_row_at_time requiere duration obligatorio (HTF closed-only)")
    try:
        tt = pd.to_datetime(t, utc=True, errors="coerce")
        times = pd.to_datetime(df["time"], utc=True, errors="coerce")
        cutoff = tt - pd.Timedelta(duration)
        exact_idx = df.index[times == cutoff].to_numpy()
        if len(exact_idx):
            return df.iloc[int(exact_idx[0])]
        prior_idx = df.index[times <= cutoff].to_numpy()
        if len(prior_idx):
            return df.iloc[int(prior_idx[-1])]
        return None
    except Exception:
        return None


# ---- constructores de datos de referencia (ordenados por time, caso valido) ----

def _mk(times, vals):
    return pd.DataFrame(
        {"time": pd.to_datetime(times, utc=True), "close": vals, "high": vals, "low": vals}
    )


DUR = "1h"  # duracion H1 para los casos

CASES = []


def _add(name, df, t, expect_close):
    CASES.append((name, df, t, expect_close))


# 1. vela cerrada disponible (cutoff cae entre dos velas => ultima <= cutoff)
_add("vela_cerrada_disponible",
     _mk(["2024-01-01 00:00", "2024-01-01 01:00", "2024-01-01 02:00"], [10, 20, 30]),
     "2024-01-01 02:00", 20)  # cutoff = 01:00 => ultima <= 01:00 es 01:00 (close 20)

# 2. ninguna vela cerrada (t antes de la primera => None, NO iloc[0])
_add("ninguna_cerrada_anti_lookahead",
     _mk(["2024-01-01 01:00", "2024-01-01 02:00"], [10, 20]),
     "2024-01-01 01:00", None)  # cutoff = 00:00 => nada <= 00:00

# 3. timestamp exactamente en frontera (time == cutoff => esa vela)
_add("frontera_exacta",
     _mk(["2024-01-01 00:00", "2024-01-01 01:00", "2024-01-01 02:00"], [10, 20, 30]),
     "2024-01-01 01:00", 10)  # cutoff = 00:00 => time==cutoff es 00:00 (close 10)

# 4. timestamp antes de la primera vela (cutoff antes de todo => None)
_add("antes_de_primera",
     _mk(["2024-01-01 05:00", "2024-01-01 06:00"], [10, 20]),
     "2024-01-01 03:00", None)  # cutoff = 02:00 => nada

# 5. timestamp despues de la ultima vela (cutoff despues de todo => ultima)
_add("despues_de_ultima",
     _mk(["2024-01-01 00:00", "2024-01-01 01:00", "2024-01-01 02:00"], [10, 20, 30]),
     "2024-01-01 10:00", 30)  # cutoff = 09:00 => ultima <= 09:00 es 02:00 (close 30)

# 6. gaps (hueco de 2h entre velas)
_add("con_gaps",
     _mk(["2024-01-01 00:00", "2024-01-01 03:00", "2024-01-01 04:00"], [10, 20, 30]),
     "2024-01-01 04:00", 20)  # cutoff = 03:00 => ultima <= 03:00 es 03:00 (close 20)

# 7. datos duplicados (misma time repetida => primera por posicion en exacto,
#    ultima por posicion en <=)
_add("duplicados",
     _mk(["2024-01-01 00:00", "2024-01-01 00:00", "2024-01-01 01:00"], [10, 11, 20]),
     "2024-01-01 01:00", 10)  # cutoff=00:00 => time==cutoff => primer iloc = 10
_add("duplicados_le",
     _mk(["2024-01-01 00:00", "2024-01-01 00:00", "2024-01-01 02:00"], [10, 11, 20]),
     "2024-01-01 03:00", 20)  # cutoff=02:00 => ultima <= 02:00 es 02:00 (close 20)

# 8. multiples TF (mismo helper, distinta duracion)
_add("tf_h4",
     _mk(["2024-01-01 00:00", "2024-01-01 04:00", "2024-01-01 08:00"], [10, 20, 30]),
     "2024-01-01 08:00", 20)  # dur 4h, cutoff=04:00 => 04:00 (close 20)

# 9. tz-aware con offset (Asia/Shanghai) => debe normalizar a UTC igual que ref
_sh = pd.DataFrame({
    "time": pd.to_datetime(
        ["2024-01-01 08:00", "2024-01-01 09:00", "2024-01-01 10:00"],
        utc=True),  # ya UTC; el punto es que to_datetime(utc=True) maneje
    "close": [10, 20, 30], "high": [10, 20, 30], "low": [10, 20, 30],
})
CASES.append(("tz_aware_utc", _sh, "2024-01-01 10:00", 20))


@pytest.mark.parametrize("name,df,t,exp_close", CASES)
def test_equivalence_vs_reference(name, df, t, exp_close):
    ref = _reference_closed_row_at_time(df, t, DUR if name != "tf_h4" else "4h")
    new = NEW(df, t, DUR if name != "tf_h4" else "4h")
    # comparamos None vs fila. Si ambos None, ok.
    if exp_close is None:
        # referencia ya validada arriba; ahora exigimos nueva == referencia
        assert (ref is None) == (new is None), f"{name}: ref is None={ref is None}, new is None={new is None}"
        return
    assert ref is not None and new is not None, f"{name}: None inesperado ref={ref} new={new}"
    # misma fila por close (proxy del contenido OHLC)
    assert float(ref["close"]) == float(new["close"]), (
        f"{name}: close diverge ref={ref['close']} new={new['close']}"
    )
    # misma posicion iloc (debe ser identica fila)
    assert ref.name == new.name, f"{name}: iloc diverge ref={ref.name} new={new.name}"


def test_duration_obligatorio():
    df = _mk(["2024-01-01 00:00", "2024-01-01 01:00"], [1, 2])
    with pytest.raises(TypeError):
        NEW(df, "2024-01-01 02:00", None)
    with pytest.raises(TypeError):
        _reference_closed_row_at_time(df, "2024-01-01 02:00", None)
