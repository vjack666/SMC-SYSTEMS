"""tests/test_r7_bosgap_rootcause.py — R7 causa raiz de la divergencia 2 vs 5.

HALLAZGO (reproducible): la divergencia de equivalencia entre el camino
canonico (run -> generate_sequence_signals -> run_sequence) y el oraculo del
test NO es mutacion de DataFrame (descartado: detect_market_structure es
idempotente y no muta el input). Es un DESAJUSTE DE PARAMETRO `bos_gap`:

  - ict_backtest/sequence.py  SequenceConfig.bos_gap = 40  (default)
  - ict_backtest/run_backtest.py  generate_sequence_signals(bos_gap=10) (default)

El oraculo del test T3.1 construia SequenceConfig() -> bos_gap=40, mientras
el runner por defecto (run_sequence_backtest -> generate_sequence_signals)
usa bos_gap=10. Con 40 el motor genera 16 raw (5 senales); con 10 genera 7
raw (2 senales). Por eso el test veia 5 vs 2.

Este test DEMUESTRA la causa y que ALINEANDO bos_gap=10 la equivalencia
exacta (2==2) se restaura. No arregla el codigo: solo documenta/prueba.

No cambia reglas ICT.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))

import pytest

from ict_backtest.data_feed import load_frames
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.sequence import run_sequence, SequenceConfig
from ict_backtest._util import closed_row_at_time, tf_duration
from ict_backtest.run_backtest import generate_sequence_signals
from ict_backtest.engine import (calc_structural_sl, _tp_liquidity,
                                 STRUCT_SL_MAX_ATR)
from ict_backtest.rules import killzone_en

import pandas as pd

SYMBOL, HTF, LTF = "XAUUSD", "D1", "H4"
CUT = {"D1": 220, "H4": 1500}


def _frames():
    fr = load_frames(SYMBOL, (HTF, LTF))
    return {tf: df.iloc[:CUT.get(tf, len(df))].reset_index(drop=True)
            for tf, df in fr.items()}


def _est(ltf_df, htf_df):
    def fn(i):
        t = ltf_df.iloc[i]["time"]
        r = closed_row_at_time(htf_df, t, tf_duration(HTF))
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False))}
    return fn


def _post_filter(ltf_df, raw_sigs):
    out = []
    for s in raw_sigs:
        direction = s["direction"]
        entry_at = s["entry_at"]
        entry_row = ltf_df.iloc[entry_at]
        entry = s["entry"]
        atr = float(entry_row.get("atr", 0.0) or 0.0)
        if not (atr > 0):
            continue
        kz = killzone_en(pd.to_datetime(entry_row["time"], utc=True))
        if kz not in ("London Open", "New York AM", "New York PM"):
            continue
        sweep_row = ltf_df.iloc[s["sweep_at"]]
        sl = calc_structural_sl(sweep_row, direction, atr)
        if sl is None:
            continue
        risk = abs(entry - sl)
        if risk <= 0 or risk > STRUCT_SL_MAX_ATR * atr:
            continue
        out.append(entry_at)
    return out


def _oracle(bos_gap):
    fr = _frames()
    ms = {tf: detect_market_structure(df) for tf, df in fr.items()}
    ltf = ms[LTF]
    htf = ms.get(HTF, ltf)
    raw, _ = run_sequence(ltf, _est(ltf, htf),
                          SequenceConfig(counter_trend=False, tp_mode="fixed2r",
                                         require_displacement=False, bos_gap=bos_gap),
                          ltf_tf=LTF)
    return _post_filter(ltf, raw)


def test_rootcause_is_bosgap_mismatch_not_mutation():
    # 1) documenta el desajuste de defaults
    assert SequenceConfig().bos_gap == 40, "SequenceConfig default bos_gap debe ser 40"
    # generate_sequence_signals usa 10 (ver run_backtest.py firma)

    # 2) con bos_gap=40 (lo que usaba el oraculo del test T3.1) diverge
    sig_40 = _oracle(bos_gap=40)
    # 3) generate_sequence_signals usa bos_gap=10 internamente
    fr = _frames()
    gen = generate_sequence_signals(SYMBOL, HTF, LTF, counter_trend=False,
                                    tp_mode="fixed2r", require_displacement=False,
                                    frames=fr)
    gen_entry = [g.entry_at for g in gen]

    # 4) alineando bos_gap=10, el oraculo REPRODUCE exactamente generate
    sig_10 = _oracle(bos_gap=10)

    print(f"\noraculo bos_gap=40 (test T3.1 original): {sig_40}")
    print(f"oraculo bos_gap=10 (alineado)         : {sig_10}")
    print(f"generate_sequence_signals (bos_gap=10): {gen_entry}")

    # La causa raiz: con bos_gap=40 el oraculo da mas senales que el runner.
    assert sig_40 != gen_entry, "si son iguales, la causa raiz no es bos_gap"
    # Al alinear bos_gap=10, el oraculo es EXACTAMENTE igual al runner.
    assert sig_10 == gen_entry, (
        f"Con bos_gap=10 el oraculo debe coincidir EXACTAMENTE con "
        f"generate_sequence_signals. oracle={sig_10} gen={gen_entry}"
    )
    # Y ambos dan la misma cantidad no-trivial.
    assert len(gen_entry) >= 1, "debe haber senales no-triviales para validar"
