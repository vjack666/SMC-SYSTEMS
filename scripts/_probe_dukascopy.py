"""Probe Dukascopy availability for long history (no full download).

Tests a few short chunks to find how far back data goes for each
symbol/timeframe. Confirms whether 20y intraday is feasible.
"""
from __future__ import annotations

import sys
import time as _time
from datetime import datetime, timezone

_ROOT = "C:/Users/v_jac/Desktop/SMC-SYSTEMS"
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

def main() -> None:
    try:
        import dukascopy_python
    except Exception as e:
        print(f"IMPORT_FAIL: {e}")
        return

    from dukascopy_python.instruments import (
        INSTRUMENT_FX_MAJORS_EUR_USD,
        INSTRUMENT_FX_MAJORS_GBP_USD,
        INSTRUMENT_FX_METALS_XAU_USD,
    )

    I = {
        "EURUSD": INSTRUMENT_FX_MAJORS_EUR_USD,
        "GBPUSD": INSTRUMENT_FX_MAJORS_GBP_USD,
        "XAUUSD": INSTRUMENT_FX_METALS_XAU_USD,
    }
    TF = {
        "M1": dukascopy_python.INTERVAL_MIN_1,
        "M5": dukascopy_python.INTERVAL_MIN_5,
        "M15": dukascopy_python.INTERVAL_MIN_15,
    }

    # Probe dates to find the earliest available: try 2003, then 2006, then 2012.
    probes = [
        ("2003-01-01", "2003-02-01"),
        ("2006-01-01", "2006-02-01"),
        ("2012-01-01", "2012-02-01"),
    ]

    print(f"{'SYMBOL':8} {'TF':4} {'PROBE':12} {'N_BARS':>8}  RESULT")
    print("-" * 60)
    for sym, instr in I.items():
        for tfname, interval in TF.items():
            found = None
            for pstart, pend in probes:
                start = datetime.fromisoformat(pstart).replace(tzinfo=timezone.utc)
                end = datetime.fromisoformat(pend).replace(tzinfo=timezone.utc)
                try:
                    df = dukascopy_python.fetch(
                        instr, interval, dukascopy_python.OFFER_SIDE_BID,
                        start, end, max_retries=3,
                    )
                except Exception as e:
                    print(f"{sym:8} {tfname:4} {pstart:12}    ERR  {e}")
                    continue
                n = len(df) if df is not None else 0
                if n > 0:
                    found = (pstart, n)
                    print(f"{sym:8} {tfname:4} {pstart:12} {n:>8}  OK (data present)")
                    break
                else:
                    print(f"{sym:8} {tfname:4} {pstart:12} {0:>8}  empty")
                    _time.sleep(0.5)
            if found is None:
                print(f"{sym:8} {tfname:4}  -> NO DATA even at 2012 probe")
            _time.sleep(0.5)
    print("-" * 60)
    print("Probe done.")

if __name__ == "__main__":
    main()
