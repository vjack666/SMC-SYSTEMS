"""TDD sintético para KZ-2: killzone_en / detect_killzones con conversión
servidor->UTC vía ZoneInfo (SIN offset fijo hardcodeado).

Principio de Ruben (DEC-009i): la hora del SERVIDOR (broker MT5) es la fuente;
se CONVIERTE vía ZoneInfo (DST automático) a UTC canónico y recién ahí se
evalúan las bandas ICT (definidas en ET fijo). NUNCA offset fijo.

Los timestamps son SINTÉTICOS (pd.Timestamp / datetime con tz). No se toca
parquet ni datos reales.
"""

import inspect

import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ict_backtest.rules import killzone_en, server_to_utc
from detectors.killzones import detect_killzones


def test_verano_invierno_misma_ny_am():
    """10:30 ET en VERANO (EDT=UTC-4) y en INVIERNO (EST=UTC-5) deben dar la
    MISMA killzone 'New York AM'. La conversión a UTC difiere (14:30 vs 15:30
    UTC) -> prueba que NO se usa offset fijo."""
    ny = ZoneInfo("America/New_York")
    verano = datetime(2026, 7, 15, 10, 30, tzinfo=ny)   # 14:30 UTC
    invierno = datetime(2026, 1, 15, 10, 30, tzinfo=ny)  # 15:30 UTC
    assert killzone_en(verano, broker_tz=ny) == "New York AM"
    assert killzone_en(invierno, broker_tz=ny) == "New York AM"
    # Conversión a UTC difiere por DST (evidencia de que no hay offset fijo):
    u_v = server_to_utc(verano, ny)
    u_i = server_to_utc(invierno, ny)
    assert u_v != u_i
    assert u_v.hour == 14 and u_v.minute == 30   # 10:30 EDT -> 14:30 UTC
    assert u_i.hour == 15 and u_i.minute == 30   # 10:30 EST  -> 15:30 UTC


def test_broker_tz_vs_none():
    """broker_tz dado convierte (naive se asume hora broker); broker_tz=None
    asume UTC crudo (convención del proyecto)."""
    ny = ZoneInfo("America/New_York")
    # broker_tz dado: naive 10:30 se asume NY local -> New York AM
    assert killzone_en(datetime(2026, 7, 15, 10, 30), broker_tz=ny) == "New York AM"
    # broker_tz=None: se asume UTC crudo (convención proyecto)
    assert killzone_en(pd.Timestamp("2026-07-15 14:30:00", tz="UTC")) == "New York AM"


def test_london_open_dst():
    ny = ZoneInfo("America/New_York")
    # London Open = 02:00-05:00 ET. 03:30 ET verano(07:30 UTC)/invierno(08:30 UTC)
    assert killzone_en(datetime(2026, 7, 15, 3, 30, tzinfo=ny), broker_tz=ny) == "London Open"
    assert killzone_en(datetime(2026, 1, 15, 3, 30, tzinfo=ny), broker_tz=ny) == "London Open"


def test_ny_pm_dst():
    ny = ZoneInfo("America/New_York")
    # NY PM = 14:00-17:00 ET. 15:30 ET verano(19:30 UTC)/invierno(20:30 UTC)
    assert killzone_en(datetime(2026, 7, 15, 15, 30, tzinfo=ny), broker_tz=ny) == "New York PM"
    assert killzone_en(datetime(2026, 1, 15, 15, 30, tzinfo=ny), broker_tz=ny) == "New York PM"


def test_fuera_ventana():
    ny = ZoneInfo("America/New_York")
    assert killzone_en(datetime(2026, 7, 15, 20, 0, tzinfo=ny), broker_tz=ny) == ""


def test_detect_killzones_broker_tz():
    """detect_killzones convierte server->UTC vía ZoneInfo cuando se pasa broker_tz."""
    ny = ZoneInfo("America/New_York")
    df = pd.DataFrame({
        "time": pd.to_datetime([
            "2026-07-15 10:30:00",  # NY local -> NY AM
            "2026-07-15 03:30:00",  # NY local -> London Open
            "2026-07-15 20:00:00",  # fuera de ventana
        ])
    })
    out = detect_killzones(df, broker_tz=ny)
    assert "NY_AM" in out["kz"].iloc[0]
    assert "LDN_OPEN" in out["kz"].iloc[1]
    assert out["kz"].iloc[2] == ""


def test_sin_offset_fijo_hardcodeado():
    """Evidencia: el código usa ZoneInfo (DST) y NO offsets fijos NY/LDN/TOKYO."""
    src_rules = inspect.getsource(killzone_en)
    src_kz = inspect.getsource(detect_killzones)
    for src in (src_rules, src_kz):
        assert "ZoneInfo" in src
        assert "server_to_utc" in src
        assert "NY=-4" not in src
        assert "LDN=0" not in src
        assert "TOKYO=+9" not in src
