"""Demo sintético Brecha B (Opción 2) — SIN datos reales.

Objetivo: demostrar que canonical.evaluate_signals ahora ANOTA htf_anchored
en ICTSignal SIN modificar run_sequence y SIN cambiar el conteo de señales
(principio Brecha D: anota, no filtra).

Usa una señal dummy forzada (via mock de run_sequence) para aislar SOLO la
anotación B. No lee data/raw (radio de explosion minimo, demo pre-datos-reales).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import MagicMock, patch

import pandas as pd

from ict_backtest.canonical import evaluate_signals
from engine.htf_pd_index import HtfPdZone


def _synthetic_ltf(n: int = 200, direction: int = 1) -> pd.DataFrame:
    """Vela LTF con 'time' y campos ICT mínimos para sequence."""
    t0 = pd.Timestamp("2024-01-01 00:00", tz="UTC")
    times = [t0 + pd.Timedelta(minutes=15 * i) for i in range(n)]
    df = pd.DataFrame({
        "time": times,
        "open": 1.0, "high": 1.01, "low": 0.99, "close": 1.005,
        "atr": 0.001,
        "trend": "BULLISH" if direction == 1 else "BEARISH",
        "liquidity_sweep_down": False, "liquidity_sweep_up": False,
        "bos_dir": 0, "choch_dir": 0,
        "fvg_bullish": False, "fvg_bearish": False,
        "ob_direction": "-", "ob_bullish": False, "ob_bearish": False,
        "displacement_bullish": False, "displacement_bearish": False,
        "bos_level": float("nan"), "pd_type": "FVG", "pd_tier": "T2",
    })
    return df


def _mock_index(poi_present: bool) -> MagicMock:
    """HtfPdIndex mockeado: build_ltf_map devuelve mapa; zones_at devuelve zona."""
    idx = MagicMock()
    idx.timeframes = ["H4"]

    def _build_ltf_map(ltf_df):
        return {"H4": pd.DataFrame(index=range(len(ltf_df)))}

    def _zones_at(i, tf, ltf_map):
        if not poi_present:
            return []
        return [HtfPdZone(tf="H4", pd_type="FVG", pd_tier="T2",
                          direction=1, zone_high=1.1, zone_low=1.0)]

    idx.build_ltf_map.side_effect = _build_ltf_map
    idx.zones_at.side_effect = _zones_at
    return idx


def _dummy_sig() -> dict:
    return {
        "time": "2024-01-01 10:00:00+00:00", "direction": 1,
        "entry": 1.0, "sweep_at": 1, "bos_at": 5, "entry_at": 10,
        "zone_authority": None,
    }


if __name__ == "__main__":
    for poi_present in (True, False):
        with patch("ict_backtest.canonical.run_sequence",
                   return_value=([_dummy_sig()], {})):
            with patch("ict_backtest.canonical.detect_market_structure",
                       side_effect=lambda df: df):
                with patch("ict_backtest.canonical.HtfPdIndex",
                           return_value=_mock_index(poi_present)):
                    with patch("ict_backtest.canonical.killzone_en",
                               return_value="London Open"):
                        with patch("ict_backtest.canonical.fill_entry_price",
                                   return_value=1.0):
                            with patch("ict_backtest.canonical.calc_structural_sl",
                                       return_value=0.9995):
                                with patch("ict_backtest.canonical._tp_liquidity",
                                           return_value=None):
                                    sigs = evaluate_signals(
                                        "SYN", "H4", "M15",
                                        frames={"M15": _synthetic_ltf(),
                                                "H4": _synthetic_ltf().iloc[::4].reset_index(drop=True)},
                                        enable_pd_index=True,
                                    )
        s = sigs[0]
        print(f"[POI presente={poi_present}] n_senales={len(sigs)} "
              f"htf_anchored={s.htf_anchored}")
        assert len(sigs) == 1, "BRECHA D VIOLADA: cambio el conteo de senales"
        assert s.htf_anchored is (True if poi_present else False)
    print("OK: Brecha B anota sin filtrar (conteo identico, ancla correcta).")
