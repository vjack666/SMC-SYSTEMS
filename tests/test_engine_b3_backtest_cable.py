"""Prueba de funnel: B3 cableado al backtest (flag_liquidity_irl_erl).

No requiere datos de mercado reales (sin parquet). Simula el paso POST del
pipeline de canonical.py: senales estilo ICTSignal anotadas con metadato IRL/ERL.
Demuestra que el backtest (consumidor) recibe erl_sweep / irl_target /
seq_erl_then_irl sin alterar entry/SL/TP (patron Brecha D).
"""
import numpy as np
import pandas as pd
from engine.liquidity_internal_external import flag_liquidity_irl_erl, volume_confirm


class _Sig:
    def __init__(self, direction, entry_at, entry=1.0, sl=0.99, tp=1.03):
        self.direction = direction
        self.entry_at = entry_at
        self.entry = entry
        self.stop_loss = sl
        self.take_profit = tp
        self.erl_sweep = None
        self.irl_target = None
        self.irl_fvg_idx = None
        self.seq_erl_then_irl = None
        self.erl_vol_ratio = None
        self.irl_vol_ratio = None


def _ltf_df_with_erl_and_irl():
    idx = pd.date_range("2026-01-06 00:00", periods=40, freq="15min", tz="UTC")
    high = np.full(40, 1.05)
    low = np.full(40, 1.00)
    open_ = np.full(40, 1.025)
    close = np.full(40, 1.025)
    low[:30] = 1.00
    # sweep ERL (SSL) en vela 30: low 0.99
    low[30] = 0.99
    open_[30] = 0.999
    close[30] = 0.998
    # FVG BULLISH interno sin llenar velas 34-35 (low[34] > high[32])
    high[32] = 1.015
    low[32] = 1.012
    open_[32] = 1.013
    close[32] = 1.014
    high[33] = 1.016
    low[33] = 1.013
    open_[33] = 1.014
    close[33] = 1.015
    high[34] = 1.024
    low[34] = 1.022
    open_[34] = 1.023
    close[34] = 1.022
    high[35] = 1.026
    low[35] = 1.021
    open_[35] = 1.022
    close[35] = 1.025
    high[36] = 1.028
    low[36] = 1.023
    open_[36] = 1.025
    close[36] = 1.027
    volume = np.ones(40) * 100.0
    volume[30] = 250.0
    volume[34:37] = 180.0
    return pd.DataFrame({"time": idx, "open": open_, "high": high,
                        "low": low, "close": close, "volume": volume})


def test_flag_irl_erl_annotates_long_signal():
    df = _ltf_df_with_erl_and_irl()
    sig = _Sig(direction=1, entry_at=36)
    out = flag_liquidity_irl_erl([sig], {"M15": df}, "M15")
    s = out[0]
    assert s.erl_sweep is True, f"erl_sweep deberia ser True, fue {s.erl_sweep}"
    assert s.irl_target is not None, "irl_target no debe ser None"
    assert 1.015 <= float(s.irl_target) <= 1.022, f"irl_target fuera de rango FVG: {s.irl_target}"
    assert s.irl_fvg_idx is not None
    assert s.seq_erl_then_irl is True, "secuencia ERL->IRL debe ser True"
    assert s.erl_vol_ratio is not None and s.erl_vol_ratio > 1.0, "volumen sweep debe subir"
    # NO altera precios de la senal (Brecha D)
    assert s.entry == 1.0 and s.stop_loss == 0.99 and s.take_profit == 1.03


def test_flag_no_frames_safe():
    sig = _Sig(direction=1, entry_at=0)
    out = flag_liquidity_irl_erl([sig], None, "M15")
    assert out[0].erl_sweep is None


def test_volume_confirm_ratio():
    df = _ltf_df_with_erl_and_irl()
    r = volume_confirm(df, 30, window=20)
    assert r is not None and r > 1.0
