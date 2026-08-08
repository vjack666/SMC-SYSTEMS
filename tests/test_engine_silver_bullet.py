"""Tests engine.silver_bullet — geometria pura (killzone + orden temporal)."""
from datetime import datetime, timezone
from engine.silver_bullet import is_silver_bullet
from engine.killzone import killzone_en


def _ts(h):
    return datetime(2026, 1, 6, h, 0, tzinfo=timezone.utc)


def test_sb_same_killzone_valid():
    ok, meta = is_silver_bullet(_ts(13), _ts(14), 1, killzone_en)
    assert ok is True
    assert meta["sb_killzone"] == "NY_AM"


def test_sb_different_killzone_invalid():
    ok, meta = is_silver_bullet(_ts(13), _ts(8), 1, killzone_en)
    assert ok is False


def test_sb_return_before_sweep_invalid():
    ok, _ = is_silver_bullet(_ts(14), _ts(13), 1, killzone_en)
    assert ok is False
