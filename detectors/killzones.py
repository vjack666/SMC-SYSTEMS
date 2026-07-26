"""Killzones — port de LuxAlgo ICT Concepts a Python.

Sesiones (horario del exchange del símbolo, igual que TradingView time()):
  London Open   : 02:00-05:00 ET  (London 07:00-10:00 UK)
  New York AM   : 10:00-12:00 ET  (Silver Bullet)
  New York PM   : 14:00-17:00 ET
  Asian         : 10:00-14:00 Asia/Tokyo

Agrega columna 'kz' con etiqueta de sesion activa por vela (para pintar banda de
fondo).

PRINCIPIO DE ZONA HORARIA (MDS_KILLZONES / DEC-009i, bug KZ-2): la hora la da el
SERVIDOR (broker MT5). Se CONVIERTE a UTC canónico via ZoneInfo (DST automático)
y recién ahí se evalúan las bandas ICT. NUNCA offset fijo hardcodeado. Si no se
pasa broker_tz se asume que `time` YA está en UTC (convención del proyecto).
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from ict_backtest.rules import (
    KILLZONES_ET,
    killzone_windows_utc,
    server_to_utc,
)

# Etiqueta corta por sesión (pintar banda de fondo). Las 3 killzones ICT
# (tesis §15) provienen de la FUENTE ÚNICA KILLZONES_ET/killzone_windows_utc
# de ict_backtest/rules.py (ET->UTC por día vía ZoneInfo, DST automático).
# ASIA es propia de este detector (Asia/Tokyo, sin DST) y solo pinta fondo.
KZ_SHORT = {
    "London Open": "LDN_OPEN",
    "New York AM": "NY_AM",
    "New York PM": "NY_PM",
}

# Compat: lista (nombre_corto, (h_ini,m_ini), (h_fin,m_fin)) usada por consumidores
# de pintura. Derivada de la fuente única + ASIA local.
SESSIONS = [
    (KZ_SHORT[nombre], ini, fin) for nombre, (ini, fin) in KILLZONES_ET.items()
] + [("ASIA", (10, 0), (14, 0))]

_TOKYO = ZoneInfo("Asia/Tokyo")


def _asia_window_utc(day_utc: datetime) -> tuple[datetime, datetime]:
    ini = datetime(day_utc.year, day_utc.month, day_utc.day, 10, 0,
                   tzinfo=_TOKYO).astimezone(timezone.utc)
    fin = datetime(day_utc.year, day_utc.month, day_utc.day, 14, 0,
                   tzinfo=_TOKYO).astimezone(timezone.utc)
    return ini, fin


def detect_killzones(df: pd.DataFrame, broker_tz=None) -> pd.DataFrame:
    """Marca sesiones activas por vela.

    broker_tz: ZoneInfo | str (nombre IANA) del servidor (broker MT5). Si se da,
    convierte server->UTC via ZoneInfo (DST) y evalúa en UTC canónico. Si None,
    asume que `time` ya viene en UTC (convención proyecto).

    Las 3 killzones ICT usan killzone_windows_utc (misma tabla que el edge).
    """
    out = df.copy()
    out["kz"] = ""

    t = pd.to_datetime(out["time"])
    if broker_tz is not None:
        utc_times = t.map(lambda x: server_to_utc(
            datetime(x.year, x.month, x.day, x.hour, x.minute, x.second),
            broker_tz))
    else:
        utc_times = (t.dt.tz_localize("UTC")
                     if t.dt.tz is None else t.dt.tz_convert("UTC"))

    labels = []
    for i in out.index:
        utc_dt = utc_times.iloc[i].to_pydatetime()
        activos = [
            KZ_SHORT[nombre]
            for nombre, (ini, fin) in killzone_windows_utc(utc_dt).items()
            if ini <= utc_dt < fin
        ]
        a_ini, a_fin = _asia_window_utc(utc_dt)
        if a_ini <= utc_dt < a_fin:
            activos.append("ASIA")
        labels.append(" ".join(activos))
    out["kz"] = labels
    return out
