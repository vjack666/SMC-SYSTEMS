"""
Killzones — port de LuxAlgo ICT Concepts a Python.

Sesiones (horario del exchange del símbolo, igual que TradingView time()):
  New York Open : 07:00-09:00 America/New_York
  London Open   : 07:00-10:00 Europe/London
  London Close  : 15:00-17:00 Europe/London
  Asian         : 10:00-14:00 Asia/Tokyo

Agrega columna 'kz' con etiqueta de sesion activa por vela (para pintar banda de fondo).
Usa la hora de 'time' del parquet (tz-aware). Si viene en UTC, las sesiones se calculan
en UTC restando el offset de cada zona (aprox fijo: NY=-4, LDN=0, TOKYO=+9 en verano).
Para simplicidad y coincidencia con MT5 (horario broker), asumimos el time del parquet
YA esta en la zona del broker; LuxAlgo usa sesiones por defecto del chart.
"""
from __future__ import annotations

import pandas as pd

# (nombre, hora_inicio, hora_fin) en horas locales del chart
SESSIONS = [
    ("NY", 7, 9),
    ("LDN_OPEN", 7, 10),
    ("LDN_CLOSE", 15, 17),
    ("ASIA", 10, 14),
]


def detect_killzones(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["kz"] = ""
    t = pd.to_datetime(out["time"])
    h = t.dt.hour + t.dt.minute / 60.0

    for name, h0, h1 in SESSIONS:
        mask = (h >= h0) & (h < h1)
        out.loc[mask, "kz"] = out.loc[mask, "kz"].astype(str) + (name + " ")

    out["kz"] = out["kz"].str.strip()
    return out
