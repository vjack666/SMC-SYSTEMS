"""app_observador/core/timezone.py — Zona horaria unica del proyecto.

Soluciona el hueco KZ-1 (docs/ict/01_KILLZONES.md): tres relojes distintos
(ET / broker-local / UTC) causaban desalineacion UI <-> backtest.

Decision de arquitectura (ver docs/plan/DECISION_TZ.md):
  1. El CALCULO interno SIEMPRE es UTC. Sin importar donde corra el binario
     (Ecuador hoy, VPS en el futuro), el resultado es deterministico porque
     UTC es absoluto. Usar datetime.now(timezone.utc) en todo lado.
  2. La ZONA DEL OPERADOR es CONFIGURACION, no hardcode. Ecuador =
     America/Guayaquil (GMT-5, sin DST). Se lee de la env SMC_TZ; si no
     existe, default Ecuador. Asi el mismo binario corre en cualquier huso:
     solo cambias SMC_TZ, no el codigo.
  3. Se MUESTRA la hora convertida a la zona del operador solo en la UI
     (con zoneinfo, stdlib 3.9+, sin pytz). El calculo no se toca.
  4. Defensa: utc_now() devuelve SIEMPRE tz-aware. Si alguien usa
     datetime.now() naive, falla temprano (no silencia el error de zona).

Por que no pytz: zoneinfo viene en stdlib desde 3.9 y usa la IANA tz DB
oficial. En Windows puede requerir el paquete 'tzdata' (pip install tzdata)
si el SO no trae la DB; lo validamos al importar.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from functools import lru_cache

from zoneinfo import ZoneInfo

# Zona por defecto: Ecuador (GMT-5, sin DST). Override via env SMC_TZ.
DEFAULT_OPERATOR_TZ = "America/Guayaquil"


@lru_cache(maxsize=1)
def operator_tz() -> ZoneInfo:
    """Zona del operador, cacheada. Lee SMC_TZ o usa Ecuador por defecto.

    Lanza ZoneInfoNotFoundError si el nombre no existe en la IANA DB
    (p.ej. falta tzdata en Windows) -> falla temprano, no calcula mal.
    """
    name = os.environ.get("SMC_TZ", DEFAULT_OPERATOR_TZ)
    return ZoneInfo(name)


def utc_now() -> datetime:
    """Ahora en UTC, SIEMPRE tz-aware. Unico reloj de calculo del sistema."""
    return datetime.now(timezone.utc)


def to_operator_time(dt: datetime | None = None) -> datetime:
    """Convierte un datetime (o ahora) de UTC a la zona del operador."""
    if dt is None:
        dt = utc_now()
    if dt.tzinfo is None:
        # Defensa: nunca calcular con naive; asumimos UTC si llega sin tz.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(operator_tz())


def operator_clock_str(dt: datetime | None = None) -> str:
    """Hora legible en zona del operador, p.ej. '07:00 Ecuador (-05)'."""
    ot = to_operator_time(dt)
    return ot.strftime(f"%H:%M {operator_tz().key} (%z)")


def operator_offset_hours() -> float:
    """Offset de la zona operador vs UTC en horas (Ecuador = -5.0)."""
    z = operator_tz()
    # Offset en el instante actual (cubre DST si la zona lo tuviera).
    off = z.utcoffset(utc_now())
    return off.total_seconds() / 3600.0 if off else 0.0


# Bandas canonicas del proyecto en UTC (docs/ict/01_KILLZONES.md §4).
# London 07-10 UTC, NY AM 12:30-15:00 UTC, NY PM 17:00-20:00 UTC.
KILLZONES_UTC = {
    "London Open": (7.0, 10.0),
    "New York AM": (12.5, 15.0),
    "New York PM": (17.0, 20.0),
}


def killzone_activa_ahora() -> str:
    """Nombre de la killzone activa AHORA (calculo en UTC) o '' si ninguna.

    Usa UTC para ser robusto en cualquier servidor. El display en zona
    operador lo hace la UI con operator_clock_str().
    """
    ahora = utc_now()
    h = ahora.hour + ahora.minute / 60.0
    for nombre, (ini, fin) in KILLZONES_UTC.items():
        if ini <= h < fin:
            return nombre
    return ""


def killzone_bandas_operador() -> dict[str, tuple[float, float]]:
    """Mismas bandas expresadas en la zona del operador (para mostrar)."""
    off = operator_offset_hours()
    return {k: (max(0.0, ini + off), max(0.0, fin + off)) for k, (ini, fin) in KILLZONES_UTC.items()}
