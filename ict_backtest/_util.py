"""ict_backtest/_util.py — helpers compartidos (único punto de verdad).

Evita duplicar _row_at_time entre engine.py y sequence.py (hallazgo #7).
"""
from __future__ import annotations

from typing import Any

import pandas as pd

def row_at_time(df: pd.DataFrame, t: Any, freq: Any = None) -> Any:
    """Devuelve la fila de `df` cuyo 'time' coincide con `t` (o la previa más
    cercana, búsqueda asof). Robusta a recortes de walk-forward donde el LTF y
    el HTF tienen rangos distintos.

    Si `freq` se indica, exige que la barra ya haya CERRADO (time + freq <= t)
    para evitar look-ahead cross-timeframe: al leer el HTF desde una vela LTF
    en formación, la barra HTF aún no cerró y sus indicadores (trend, BOS,
    CHOCH) usan precio futuro. Ver AUDIT_LOOKAHEAD_HTF.md.
    """
    try:
        tt = pd.to_datetime(t, utc=True, errors="coerce")
        times = pd.to_datetime(df["time"], utc=True, errors="coerce")
        exact = df.index[times == tt]
        if len(exact):
            return df.iloc[int(list(exact)[0])]
        upper = tt - pd.Timedelta(freq) if freq is not None else tt
        prior = times[times <= upper]
        if len(prior):
            return df.iloc[int(prior.index[-1])]
    except Exception:
        pass
    return df.iloc[0]
