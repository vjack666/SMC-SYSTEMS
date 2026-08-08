"""Tests engine.killzone — geometria de horas, cero indicadores."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from engine.killzone import killzone_en, server_to_utc


def test_killzone_utc_known():
    # 13:00 UTC -> New York AM (12.5-15.0)
    ts = datetime(2026, 1, 6, 13, 0, tzinfo=timezone.utc)
    assert killzone_en(ts) == "New York AM"


def test_killzone_utc_london_open():
    ts = datetime(2026, 1, 6, 8, 0, tzinfo=timezone.utc)
    assert killzone_en(ts) == "London Open"


def test_killzone_utc_outside():
    ts = datetime(2026, 1, 6, 20, 0, tzinfo=timezone.utc)
    assert killzone_en(ts) == ""


def test_killzone_broker_tz_dst():
    # 10:30 ET (NY) en invierno -> New York AM
    ny = ZoneInfo("America/New_York")
    ts_ny = datetime(2026, 1, 6, 10, 30, tzinfo=ny)
    assert killzone_en(ts_ny, broker_tz="America/New_York") == "New York AM"
