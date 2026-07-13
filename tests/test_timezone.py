"""R2 — Tests de zona horaria y killzones.

Verifica la decision de DECISION_TZ.md:
  - calculo SIEMPRE en UTC (killzone robusta en cualquier servidor)
  - zona operador configurable (Ecuador por defecto; override via SMC_TZ)
  - conversion UTC -> operador correcta (Ecuador GMT-5 sin DST)
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_observador.core import timezone as tz  # noqa: E402


def test_utc_now_is_aware():
    """utc_now() nunca es naive (defensa contra hora local del sistema)."""
    now = tz.utc_now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timezone.utc.utcoffset(None) or now.utcoffset() == datetime.now(timezone.utc).utcoffset()


def test_ecuador_default_offset():
    """Default operador = America/Guayaquil = -5.0h vs UTC (sin DST)."""
    off = tz.operator_offset_hours()
    assert off == -5.0


def test_conversion_utc_to_ecuador():
    """UTC 12:00 -> Ecuador 07:00 (-05)."""
    utc = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
    op = tz.to_operator_time(utc)
    assert op.hour == 7
    assert op.minute == 0
    assert op.utcoffset().total_seconds() == -5 * 3600


def test_override_por_env(monkeypatch):
    """SMC_TZ cambia la zona sin tocar el codigo (robusto para servidor)."""
    monkeypatch.setenv("SMC_TZ", "America/New_York")
    tz.operator_tz.cache_clear()  # limpiar cache lru
    try:
        off = tz.operator_offset_hours()
        # NY en verano es -4, en invierno -5; aceptamos cualquiera (tiene DST).
        assert off in (-4.0, -5.0)
        utc = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
        op = tz.to_operator_time(utc)
        assert op.hour in (7, 8)  # 12 UTC -> 08 o 07 NY
    finally:
        monkeypatch.delenv("SMC_TZ", raising=False)
        tz.operator_tz.cache_clear()


def test_killzone_calculo_utc():
    """killzone_activa_ahora usa UTC -> deterministico en cualquier servidor."""
    # Forzar un instante UTC conocido parcheando utc_now.
    class _Fake:
        def hour(self):
            return 8

    import app_observador.core.timezone as T

    original = T.utc_now
    try:
        T.utc_now = lambda: datetime(2026, 7, 13, 8, 30, tzinfo=timezone.utc)
        assert T.killzone_activa_ahora() == "London Open"
        T.utc_now = lambda: datetime(2026, 7, 13, 13, 0, tzinfo=timezone.utc)
        assert T.killzone_activa_ahora() == "New York AM"
        T.utc_now = lambda: datetime(2026, 7, 13, 3, 0, tzinfo=timezone.utc)
        assert T.killzone_activa_ahora() == ""  # fuera de ventana
    finally:
        T.utc_now = original


def test_bandas_operador_ecuador():
    """Bandas UTC expresadas en Ecuador (restan 5h)."""
    bandas = tz.killzone_bandas_operador()
    # London Open UTC 7-10 -> Ecuador 2-5
    assert bandas["London Open"] == (2.0, 5.0)
    # NY AM UTC 12.5-15 -> Ecuador 7.5-10
    assert bandas["New York AM"] == (7.5, 10.0)
