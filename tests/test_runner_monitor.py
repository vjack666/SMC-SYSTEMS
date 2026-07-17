"""Unit tests for Hermes Runner Monitor helpers (no long jobs)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_MOD_PATH = _ROOT / "scripts" / "runner_monitor.py"
_spec = importlib.util.spec_from_file_location("runner_monitor", _MOD_PATH)
assert _spec and _spec.loader
_rm = importlib.util.module_from_spec(_spec)
sys.modules["runner_monitor"] = _rm
_spec.loader.exec_module(_rm)

format_bar = _rm.format_bar
format_elapsed = _rm.format_elapsed
read_progress = _rm.read_progress
recommended_workers = _rm.recommended_workers


def test_recommended_workers_uses_fraction_not_all_cores():
    # 16 logical CPUs → ~12 at 75%
    assert recommended_workers(16, 0.75) == 12
    assert recommended_workers(8, 0.75) == 6
    assert recommended_workers(1, 0.75) == 1
    # Never exceeds cpu_count
    assert recommended_workers(4, 0.75) <= 4


def test_format_elapsed_and_bar():
    assert format_elapsed(65) == "01:05"
    assert format_elapsed(3661) == "01:01:01"
    bar = format_bar(50, 100, width=10)
    assert len(bar) == 10
    assert "█" in bar and "░" in bar
    # No total → empty bar, not a fake 50%
    assert format_bar(5, 0, width=10) == "░" * 10


def test_read_progress_real_only(tmp_path: Path):
    p = tmp_path / "prog.json"
    assert read_progress(None) is None
    assert read_progress(p) is None  # missing file

    p.write_text(json.dumps({"done": 10, "total": 40, "unit": "candles", "current": "2022"}), encoding="utf-8")
    data = read_progress(p)
    assert data is not None
    assert data["done"] == 10
    assert data["total"] == 40
    assert data["unit"] == "candles"
