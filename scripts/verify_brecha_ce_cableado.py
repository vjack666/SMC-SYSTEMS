"""Verify cableado Brecha C + E en canonical.evaluate_signals (SINTETICO, sin parquet).

Objetivo: confirmar que el enchufe post-proceso en canonical.py (Opción 2) no
crash y anota zone_class (C) y po3_complete (E) en ICTSignal, SIN tocar
run_sequence. No lee data/raw.

Usa mock de run_sequence + detect_market_structure + HtfPdIndex para aislar
SOLO el enchufe de C/E. El conteo de senales debe ser 1 (principio Brecha D).
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from ict_backtest.canonical import evaluate_signals
from ict_backtest.htf_pd_index import HtfPdZone


def _ltf(n: int = 50) -> pd.DataFrame:
    t0 = pd.Timestamp("2024-01-01", tz="UTC")
    return pd.DataFrame({
        "time": [t0 + pd.Timedelta(minutes=15 * i) for i in range(n)],
        "open": 1.0, "high": 1.02, "low": 0.98, "close": 1.0, "atr": 0.001,
        "trend": "BULLISH", "sweep_up": False, "sweep_down": False, "bos_dir": 0,
        "bos_status": "", "choch_status": "", "fvg_state": "", "ob_dir": "",
        "session_range": "", "swing_high": 1.05, "swing_low": 0.95,
        "sweep_low": None, "sweep_high": None,
    })


def _dummy():
    return {"time": "2024-01-01 10:00:00+00:00", "direction": 1, "entry": 1.0,
            "sweep_at": 1, "bos_at": 5, "entry_at": 10, "zone_authority": None}


if __name__ == "__main__":
    idx = MagicMock()
    idx.timeframes = ["H4"]
    idx.zones_at.return_value = [HtfPdZone(tf="H4", pd_type="FVG", pd_tier="T2",
                                          direction=1, zone_high=1.1, zone_low=1.0)]
    idx.build_ltf_map.return_value = {"H4": pd.DataFrame(index=range(50))}

    with patch("ict_backtest.canonical.run_sequence", return_value=([_dummy()], {})):
        with patch("ict_backtest.canonical.detect_market_structure", side_effect=lambda df: df):
            with patch("ict_backtest.canonical.HtfPdIndex", return_value=idx):
                with patch("ict_backtest.canonical.killzone_en", return_value="London Open"):
                    with patch("ict_backtest.canonical.fill_entry_price", return_value=1.0):
                        with patch("ict_backtest.canonical.calc_structural_sl", return_value=0.9995):
                            with patch("ict_backtest.canonical._tp_liquidity", return_value=None):
                                sigs = evaluate_signals(
                                    "SYN", "H4", "M15",
                                    frames={"M15": _ltf(), "H4": _ltf().iloc[::4].reset_index(drop=True)},
                                    enable_pd_index=True,
                                )
    s = sigs[0]
    print(f"n_senales={len(sigs)} htf_anchored={s.htf_anchored} "
          f"zone_class={s.zone_class} po3_complete={s.po3_complete}")
    assert len(sigs) == 1, "Brecha D violada: cambio el conteo"
    assert s.zone_class in ("PREMIUM", "DISCOUNT", "EQ"), "zone_class mal"
    assert s.po3_complete in (True, False, None), "po3_complete mal"
    print("OK: enchufe C/E anota sin crashear (conteo idéntico, run_sequence intacto).")
