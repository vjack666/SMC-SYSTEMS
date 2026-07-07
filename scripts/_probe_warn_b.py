"""
Probe B: exercise first-party data/detector/feature/signal code on synthetic
OHLCV frames to surface SettingWithCopyWarning under pandas 3.0 (CoW always on).

MetaTrader5 is stubbed so import-time OK. langgraph not required here.
"""
from __future__ import annotations

import json
import sys
import types
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

# Stub mt5
_m = types.ModuleType("MetaTrader5")


def _mt5_getattr(name: str):
    def _noop(*_args, **_kwargs):
        return None

    return _noop


_m.__getattr__ = _mt5_getattr
sys.modules["MetaTrader5"] = _m

pd.options.mode.chained_assignment = "warn"

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

warnings.simplefilter("always")
_caught: list[dict] = []


def _show(message, category, filename, lineno, file=None, line=None):
    t = str(message)
    if "SettingWithCopy" in t or "chained" in t.lower():
        _caught.append(
            {"category": category.__name__, "message": t, "filename": str(filename), "lineno": lineno}
        )


warnings.showwarning = _show


def _synthetic_ohlcv(n: int = 500) -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=n, freq="15min")
    rng = np.random.default_rng(7)
    close = 1.1 + np.cumsum(rng.normal(0, 0.0005, n))
    close = np.maximum(close, 0.5)
    open_ = close + rng.normal(0, 0.0002, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.0003, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.0003, n))
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": rng.integers(10, 1000, n)},
        index=idx,
    )


def _exercise(module_names: list[str]) -> None:
    import importlib

    df = _synthetic_ohlcv()
    for name in module_names:
        try:
            mod = importlib.import_module(name)
        except Exception as e:  # noqa: BLE001
            print(f"[skip import {name}] {type(e).__name__}: {e}")
            continue
        # Try common entrypoints with a synthetic frame.
        for fn_name in ("detect", "run", "compute", "process", "transform", "build", "analyze"):
            fn = getattr(mod, fn_name, None)
            if callable(fn):
                for arg in (df, df.copy(), {"df": df, "symbol": "EURUSD"}):
                    try:
                        fn(arg)
                        break
                    except Exception:
                        continue
        print(f"[ok exercise {name}]")


def main() -> int:
    targets = [
        "detectors",
        "detectors.smc",
    ]
    try:
        _exercise(targets)
    except Exception as e:  # noqa: BLE001
        print(f"[err] {type(e).__name__}: {e}")

    seen = set()
    uniq = []
    for r in _caught:
        k = (r["filename"], r["lineno"], r["message"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    out = REPO / "scripts" / "_probe_warn.jsonl"
    out.write_text(json.dumps(uniq, indent=2), encoding="utf-8")
    print(f"\n=== {len(uniq)} unique chained warnings (probe B) ===")
    for r in uniq[:80]:
        print(f"  {r['filename']}:{r['lineno']}  {r['message'][:140]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
