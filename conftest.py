"""
conftest.py — local verification helper (NOT part of the shipped project).

Purpose: inject a no-op `MetaTrader5` stub into sys.modules so the test suite
can be collected/run in the probe venv without the real (non-installable here)
MetaTrader5 package. This is only needed for offline pandas/CoW verification of
chained-assignment issues; the real runner uses the genuine mt5 package.

Remove this file (or its stub block) before relying on live MT5 behaviour.
"""
from __future__ import annotations

import sys
import types


def _ensure_mt5_stub() -> None:
    if "MetaTrader5" in sys.modules:
        return

    stub = types.ModuleType("MetaTrader5")

    def _getattr(name: str):
        def _noop(*_args, **_kwargs):
            return None

        return _noop

    stub.__getattr__ = _getattr
    sys.modules["MetaTrader5"] = stub


_ensure_mt5_stub()
