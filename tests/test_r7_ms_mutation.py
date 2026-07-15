"""tests/test_r7_ms_mutation.py — R7 investigacion causa raiz (T3.2B bloqueante).

Objetivo: identificar EXACTAMENTE la instruccion de detect_market_structure
que muta el DataFrame de entrada (columna `atr`), demostrandolo con un test
reproducible. No arregla nada: solo aisa la linea culpable.

Evidencia esperada: el test imprime, tras cada statement del cuerpo de
detect_market_structure, si `frame["atr"]` (el INPUT) cambio. El primer
statement que cambie `frame["atr"]` es la instruccion culpable.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))

import numpy as np
import pandas as pd
import pytest

from ict_backtest.data_feed import load_frames
from ict_backtest.market_structure import (
    detect_market_structure, _swing_points, _label_swings, _atr,
    _consecutive_break, _track_structure, _derive_trend, StructureConfig,
)


def _fresh_h4(n: int = 1500):
    fr = load_frames("XAUUSD", ("D1", "H4"))
    return fr["H4"].iloc[:n].reset_index(drop=True)


def test_identify_exact_mutation_instruction():
    frame = _fresh_h4()
    atr0 = frame["atr"].to_numpy().copy()

    config = StructureConfig()
    # Replica el cuerpo de detect_market_structure, midiendo frame["atr"]
    # tras cada statement.
    log = []

    def snap(label):
        cur = frame["atr"].to_numpy()
        # NaN-safe: el atr del data feed tiene NaN en el periodo de calentamiento;
        # np.array_equal fallaria con NaN. Usamos allclose equal_nan.
        changed = not np.allclose(cur, atr0, equal_nan=True)
        log.append((label, changed))
        return changed

    # --- copia inicial ---
    d = frame.copy().reset_index(drop=True)          # L148
    c = snap("L148 d = frame.copy().reset_index(drop=True)")
    sh, sl = _swing_points(d, config.swing_lookback)  # L149
    c = snap("L149 _swing_points")
    d["swing_high"], d["swing_low"] = sh, sl          # L150
    c = snap("L150 asigna swing_high/low")
    d["swing_label"] = _label_swings(sh, sl)          # L151
    c = snap("L151 swing_label")
    atr = _atr(d, config.atr_period)                  # L152
    c = snap("L152 _atr")
    d["_atr"] = atr.to_numpy()                        # L153
    c = snap("L153 d['_atr'] = atr")
    bull_break = d["close"] > sh.shift(1)             # L157
    c = snap("L157 bull_break")
    bear_break = d["close"] < sl.shift(1)             # L158
    c = snap("L158 bear_break")
    bull_conf = _consecutive_break(bull_break, config.confirm_bars)   # L159
    c = snap("L159 bull_conf")
    bear_conf = _consecutive_break(bear_break, config.confirm_bars)   # L160
    c = snap("L160 bear_conf")
    d["bos_dir"] = np.select([bull_conf, bear_conf], [1, -1], default=0)  # L161
    c = snap("L161 bos_dir")
    d["bos_level"] = np.where(d["bos_dir"] == 1, sh.shift(1),
                     np.where(d["bos_dir"] == -1, sl.shift(1), np.nan))   # L162-163
    c = snap("L162-163 bos_level")
    d["bos_status"], d["bos_age"] = _track_structure(d, config, is_choch=False)  # L165
    c = snap("L165 _track_structure(is_choch=False)")
    last_bos_dir = d["_last_bos_dir"].to_numpy()      # L168
    c = snap("L168 last_bos_dir")
    last_bos_level = d["_last_bos_level"].to_numpy()  # L169
    c = snap("L169 last_bos_level")
    up_choch = (d["close"].to_numpy() > last_bos_level) & (last_bos_dir == -1)  # L170
    c = snap("L170 up_choch")
    dn_choch = (d["close"].to_numpy() < last_bos_level) & (last_bos_dir == 1)   # L171
    c = snap("L171 dn_choch")
    choch_raw = np.select([up_choch, dn_choch], [1, -1], default=0)  # L172
    c = snap("L172 choch_raw")
    d["choch_dir"] = _consecutive_break(
        pd.Series(choch_raw != 0, index=d.index), config.confirm_bars).astype(int) * choch_raw  # L174-176
    c = snap("L174-176 choch_dir")
    d = d.drop(columns=["_last_bos_dir", "_last_bos_level", "_atr"])  # L177
    c = snap("L177 drop temporales")
    d["choch_status"], d["choch_age"] = _track_structure(d, config, is_choch=True)  # L178
    c = snap("L178 _track_structure(is_choch=True)")
    d["trend"] = _derive_trend(d)                    # L179
    c = snap("L179 trend")

    # El input NO debe haber mutado en absoluto.
    mutated = [(lbl, ch) for lbl, ch in log if ch]
    print("\n=== MUTACION DE frame['atr'] POR STATEMENT ===")
    for lbl, ch in log:
        print(f"  {'MUTA' if ch else 'ok  '} <- {lbl}")
    print(f"atr0[:3] = {atr0[:3]}")
    print(f"atr_final[:3] = {frame['atr'].to_numpy()[:3]}")

    assert not mutated, (
        f"detect_market_structure MUTA el input. Primer statement que cambia "
        f"frame['atr']: {mutated[0][0]}. Esto rompe la equivalencia funcional "
        f"(oraculo sobre df fresco vs generate sobre df ya mutado)."
    )
