"""
Probe: hunt real SettingWithCopyWarning / chained-assignment issues.

Strategy:
  * Inject a no-op MetaTrader5 stub into sys.modules so first-party modules
    that `import MetaTrader5 as mt5` at module level can import without the
    real (non-installable here) package.
  * Run pandas in chained_assignment="warn" mode + copy-on-write preview.
  * Import every first-party module, then run the test suite. Any
    SettingWithCopyWarning emitted (even from tests that later fail for
    unrelated mt5 reasons) is captured and dumped for triage.

Data-only deps required in the venv (no langchain/PySide6/MT5 needed).

Usage (from repo root, inside the probe venv):
    python scripts/_probe_warn.py
"""
from __future__ import annotations

import json
import sys
import types
import warnings
from pathlib import Path

import pandas as pd

# --- Inject MetaTrader5 stub BEFORE any first-party import -------------------
_mt5_stub = types.ModuleType("MetaTrader5")


class _Mt5Attr:
    """Any attribute access returns a callable returning None / empty."""

    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            return None

        return _noop


_mt5_stub.__getattr__ = lambda name: _Mt5Attr()
sys.modules["MetaTrader5"] = _mt5_stub

# --- Aggressive pandas warning config ---------------------------------------
# 'warn' makes pandas emit SettingWithCopyWarning instead of being silent.
pd.options.mode.chained_assignment = "warn"
# CoW preview: surfaces operations that will break under Pandas 4 copy-on-write.
try:
    pd.set_option("mode.copy_on_write", True)
except (ValueError, KeyError):
    pass

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "scripts" / "_probe_warn.jsonl"

warnings.simplefilter("always")


def _install_capture() -> list[dict]:
    records: list[dict] = []

    def showwarning(message, category, filename, lineno, file=None, line=None):
        text = str(message)
        if "SettingWithCopy" in text or "chained" in text.lower():
            records.append(
                {
                    "category": category.__name__,
                    "message": text,
                    "filename": str(filename),
                    "lineno": lineno,
                }
            )

    warnings.showwarning = showwarning
    return records


def _run_imports() -> None:
    import importlib

    first_party = [
        "backtest",
        "data",
        "detectors",
        "features",
        "harness",
        "ml",
        "regime",
        "signals",
        "trend_context",
        "_data_legacy",
        "_progress",
    ]
    for name in first_party:
        try:
            importlib.import_module(name)
            print(f"[ok] import {name}")
        except Exception as e:  # noqa: BLE001
            print(f"[skip] import {name}: {type(e).__name__}: {e}")


def main() -> int:
    records = _install_capture()
    sys.path.insert(0, str(REPO))
    _run_imports()

    try:
        import pytest

        print("\n=== running pytest (warnings captured as side effect) ===")
        ret = pytest.main(
            [
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
                "-W",
                "always",
                "tests",
                "harness",
            ]
        )
        print(f"pytest exit={ret}")
    except Exception as e:  # noqa: BLE001
        print(f"[skip] pytest: {type(e).__name__}: {e}")

    seen = set()
    unique = []
    for r in records:
        key = (r["filename"], r["lineno"], r["message"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    OUT.write_text(json.dumps(unique, indent=2), encoding="utf-8")
    print(f"\n=== {len(unique)} unique SettingWithCopy/chained warnings ===")
    print(f"written to {OUT}")
    for r in unique[:80]:
        print(f"  {r['filename']}:{r['lineno']}  {r['message'][:140]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
