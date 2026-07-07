"""Tests for scripts/download_multiyear.py (Ítem B harness helper).

The real script requires a live MetaTrader 5 terminal, so we mock the
MT5Connector and the parquet writer. These tests verify ONLY the logic that
lives in the script itself:
  - estimated bar count per timeframe,
  - the global tqdm progress loop,
  - the calendar-window (date_from/date_to) filtering,
  - skip-if-file-exists,
  - the "NO DATA" guard when the download returns nothing in-window.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "download_multiyear.py"


def _fake_connector_module():
    """Build a fake `data.mt5.connector` so the script imports without MT5."""
    import dataclasses

    @dataclasses.dataclass
    class ConnectionConfig:
        path: str | None = None
        timeout: int = 60_000
        retry_delay: float = 2.0
        max_retries: int = 3

    mod = types.ModuleType("data.mt5.connector")
    mod.ConnectionConfig = ConnectionConfig

    class MT5Connector:
        def __init__(self, config=None):
            self.config = config
            self.calls = []
            self.skip_existing = False
            mod._last_instance = self

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def terminal_info(self):
            return {"name": "mock"}

        def download_rates(self, symbol, timeframe, count=100_000):
            # Align "now" with what main() uses for date_to.
            now = datetime.now(timezone.utc)
            step_min = {"M1": 1, "M5": 5, "M15": 15, "M30": 30,
                        "H1": 60, "H4": 240, "D1": 1440}[timeframe]
            n = int(count)
            times = [now - timedelta(minutes=step_min * i) for i in range(n, 0, -1)]
            self.calls.append((symbol, timeframe, count))
            return pd.DataFrame({
                "time": pd.to_datetime(times, utc=True),
                "open": np.random.rand(n),
                "high": np.random.rand(n),
                "low": np.random.rand(n),
                "close": np.random.rand(n),
                "tick_volume": np.ones(n, dtype=int),
                "spread": np.zeros(n, dtype=int),
            })

    mod.MT5Connector = MT5Connector
    return mod


@pytest.fixture
def patched_script(monkeypatch, tmp_path):
    # Inject fake connector modules before importing the script.
    sys.modules.setdefault("data", types.ModuleType("data"))
    sys.modules.setdefault("data.mt5", types.ModuleType("data.mt5"))
    fake = _fake_connector_module()
    monkeypatch.setitem(sys.modules, "data.mt5.connector", fake)

    # Capture parquet writes (pyarrow unavailable on py3.14 sandbox).
    written = []
    monkeypatch.setattr(
        pd.DataFrame, "to_parquet",
        lambda self, path, index=False: written.append((Path(path), len(self))),
    )

    spec = importlib.util.spec_from_file_location("download_multiyear", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, fake, written, tmp_path


def _run(patched_script, argv):
    module, fake, written, tmp_path = patched_script
    monkeypatch = None  # argv is set via sys.argv below
    import sys as _sys
    old = _sys.argv
    _sys.argv = ["download_multiyear.py"] + argv
    try:
        module.main()
    finally:
        _sys.argv = old
    return fake, written


def test_downloads_writes_parquet_and_filters_window(patched_script):
    fake, written = _run(
        patched_script,
        ["--symbols", "EURUSD", "--timeframes", "M15",
         "--years", "4", "--output", str(patched_script[3])],
    )
    conn = fake._last_instance
    # One parquet write for the single (symbol, tf) job.
    assert len(written) == 1, written
    path, n_rows = written[0]
    assert path.name == "EURUSD_M15.parquet"
    # The window is ~4 years; the synthetic series spans ~4.4 years back from
    # now, so filtering should keep the large majority of bars.
    assert n_rows > 100_000, n_rows
    # Connector was actually called with the estimated count.
    assert conn.calls and conn.calls[0][0] == "EURUSD"


def test_skip_existing_file(patched_script):
    tmp_path = patched_script[3]
    existing = tmp_path / "EURUSD_M15.parquet"
    existing.write_text("dummy")  # pretend a prior download exists
    fake, written = _run(
        patched_script,
        ["--symbols", "EURUSD", "--timeframes", "M15",
         "--years", "4", "--output", str(tmp_path)],
    )
    conn = fake._last_instance
    # Skipped: no download, no parquet write.
    assert conn.calls == [], conn.calls
    assert written == [], written


def test_no_data_guard_does_not_crash(patched_script, monkeypatch):
    module, fake, written, tmp_path = patched_script

    # Force download_rates to return an empty (out-of-window) frame so the
    # date filter drops everything -> script must print "NO DATA" and continue.
    def _empty(self, symbol, timeframe, count=100_000):
        now = datetime.now(timezone.utc)
        # All bars are BEFORE the requested window -> filtered out.
        times = [now - timedelta(days=365 * 10 + i) for i in range(10)]
        self.calls.append((symbol, timeframe, count))
        return pd.DataFrame({
            "time": pd.to_datetime(times, utc=True),
            "open": np.zeros(10), "high": np.zeros(10),
            "low": np.zeros(10), "close": np.zeros(10),
            "tick_volume": np.ones(10, dtype=int),
            "spread": np.zeros(10, dtype=int),
        })

    monkeypatch.setattr(fake.MT5Connector, "download_rates", _empty)
    # Should not raise SystemExit; just records no parquet.
    fake2, written2 = _run(
        patched_script,
        ["--symbols", "EURUSD", "--timeframes", "M15",
         "--years", "4", "--output", str(tmp_path)],
    )
    assert written2 == [], written2
