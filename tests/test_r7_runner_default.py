"""tests/test_r7_runner_default.py — T3.1 (R7 Fase 3, TDD).

Verifica que `ict_backtest.run_backtest.run` (camino POR DEFECTO, sin --engine)
delega en el motor canonico `sequence.run_sequence` y deja de depender de
`build_signals_from_frames` (motor engine divergente, isla eliminada en R7).

Contrato R7 (DoD #2 / H12): el runner por defecto debe invocar `run_sequence`,
no `build_signals_from_frames`. La migracion no esta terminada si el usuario
corre el backtest por defecto y sigue entrando por engine.

Equivalencia EXIGIDA por la instruccion de T3.1: no basta el numero de trades.
Se comparan senales COMPLETAS: cantidad, time, direction, entry, stop_loss,
take_profit, sweep_at, bos_at y entry_at.

Usa XAUUSD D1->H4 (datos reales, pocas velas, sin OOM del host). El oráculo
sequence replica EXACTAMENTE el camino canonico de `run_sequence_backtest`
(killzone + SL estructural + RR 1:3), de modo que la unica divergencia
legitima es la resuelta en Fase 2 (entry en retorno vs close, RR 1:3 vs 1:2).

Para que el test sea rapido y determinista, se MOCKEA `rb.load_frames` para
devolver frames ya recortados en memoria (evita recargar el parquet real de
10066 velas H4 dentro de `run`).
"""

import sys
from pathlib import Path
from unittest import mock

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.data_feed import load_frames
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.sequence import run_sequence, SequenceConfig
from ict_backtest._util import closed_row_at_time, tf_duration
from ict_backtest.engine import (calc_structural_sl, _tp_liquidity,
                                 STRUCT_SL_MAX_RANGE, ICTSignal)
import ict_backtest.run_backtest as rb


SYMBOL = "XAUUSD"
HTF = "D1"
LTF = "H4"
MAX_HOLD = 40

# Carga UNA vez y recorta en memoria (ENV QUIRK: 50000 velas M15 mueren por
# OOM; aqui solo D1/H4 y recorte agresivo para test rapido).
_FRAMES = load_frames(SYMBOL, (HTF, LTF))
_CUT = {"D1": 300, "H4": 400}
_FRAMES = {tf: df.iloc[:_CUT.get(tf, len(df))].reset_index(drop=True)
           for tf, df in _FRAMES.items()}
_MS = {tf: detect_market_structure(df) for tf, df in _FRAMES.items()}


def _est_htf_fn(ltf_df, htf_df):
    def fn(i):
        t = ltf_df.iloc[i]["time"]
        r = closed_row_at_time(htf_df, t, tf_duration(HTF))
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False))}
    return fn


def _oracle_sequence_signals():
    """Replica EXACTAMENTE el camino canonico de run_sequence_backtest:
    run_sequence -> killzone -> SL estructural -> RR 1:3. Devuelve lista de
    dicts con los campos COMPLETOS de la senal (incl. sweep_at/bos_at/entry_at).
    """
    ltf_df = _MS[LTF]
    htf_df = _MS.get(HTF, ltf_df)
    est_fn = _est_htf_fn(ltf_df, htf_df)
    raw_sigs, _ = run_sequence(ltf_df, est_fn, SequenceConfig(),
                               ltf_tf=LTF)
    out = []
    for s in raw_sigs:
        direction = s["direction"]
        entry_at = s["entry_at"]
        entry_row = ltf_df.iloc[entry_at]
        entry = s["entry"]
        atr = float(entry_row.get("atr", 0.0) or 0.0)
        if not (atr > 0):
            continue
        kz = rb.killzone_en(pd.to_datetime(entry_row["time"], utc=True))
        if kz not in ("London Open", "New York AM", "New York PM"):
            continue
        sweep_row = ltf_df.iloc[s["sweep_at"]]
        sl = calc_structural_sl(sweep_row, direction, atr)
        if sl is None:
            continue
        risk = abs(entry - sl)
        if risk <= 0 or risk > STRUCT_SL_MAX_RANGE * atr:
            continue
        liq = _tp_liquidity(entry_row, direction)
        tp = liq if liq is not None else (
            entry + 3.0 * risk if direction == 1 else entry - 3.0 * risk)
        if direction == 1 and tp <= entry + 2.0 * risk:
            tp = entry + 3.0 * risk
        if direction == -1 and tp >= entry - 2.0 * risk:
            tp = entry - 3.0 * risk
        out.append({
            "time": s["time"], "direction": direction, "entry": entry,
            "stop_loss": sl, "take_profit": tp,
            "sweep_at": s["sweep_at"], "bos_at": s["bos_at"],
            "entry_at": s["entry_at"],
        })
    return out


def _run_under_test_captures_signals():
    """Ejecuta rb.run(...) con load_frames espiado (frames recortados) y
    simulate_trade espiado para capturar las senales (ICTSignal) que el runner
    pasa a la simulacion. Devuelve lista de dicts de senal capturados.
    """
    captured = []

    def fake_sim(ltf_df, sig, max_hold, cost=None):
        captured.append({
            "time": sig.time, "direction": sig.direction, "entry": sig.entry,
            "stop_loss": sig.stop_loss, "take_profit": sig.take_profit,
            "sweep_at": getattr(sig, "sweep_at", None),
            "bos_at": getattr(sig, "bos_at", None),
            "entry_at": getattr(sig, "entry_at", None),
        })
        return None, {"exit_reason": "mock"}

    with mock.patch.object(rb, "load_frames", return_value=_FRAMES), \
         mock.patch.object(rb, "simulate_trade", side_effect=fake_sim):
        rb.run(SYMBOL, HTF, LTF, model="intradia", max_hold=MAX_HOLD,
               counter_trend=False, tp_mode="fixed2r",
               require_displacement=False)
    return captured


def test_run_default_does_not_use_build_signals_from_frames():
    """CHECKPOINT T3.1 (estable tras T3.2A): el runner por defecto ya no expone
    ni alcanza build_signals_from_frames (isla engine eliminada de su alcance).
    """
    assert not hasattr(rb, "build_signals_from_frames"), (
        "run_backtest ya no debe exponer build_signals_from_frames (R7). El "
        "runner por defecto debe delegar en run_sequence_backtest."
    )
    with mock.patch.object(rb, "run_sequence_backtest",
                           wraps=rb.run_sequence_backtest) as spied:
        _run_under_test_captures_signals()
        assert spied.called, (
            "run() por defecto no invoco run_sequence_backtest (motor canonico)."
        )


def test_run_default_delegates_to_run_sequence():
    """CHECKPOINT T3.1 (estable): run() delega en el motor canonico
    (run_sequence via run_sequence_backtest). El flujo real de decision se
    ejecuta (run_sequence NO se desactiva: wraps=).
    """
    with mock.patch.object(rb, "run_sequence_backtest",
                           wraps=rb.run_sequence_backtest) as spied_seq:
        _run_under_test_captures_signals()
        assert spied_seq.called, (
            "run() por defecto no invoco run_sequence_backtest. Debe delegar en "
            "el motor canonico (R7 DoD #2)."
        )


def test_run_default_signals_equivalent_to_sequence_oracle():
    """RED: las senales COMPLETAS que produce run() (camino por defecto) deben
    coincidir campo a campo con el oráculo sequence canonico sobre los mismos
    frames. Hoy falla porque run() usa engine (entry close, RR 1:2).
    """
    oracle = _oracle_sequence_signals()
    captured = _run_under_test_captures_signals()

    assert len(captured) == len(oracle), (
        f"cantidad de senales distinta: run={len(captured)} "
        f"sequence_oracle={len(oracle)}"
    )
    fields = ("time", "direction", "entry", "stop_loss", "take_profit",
              "sweep_at", "bos_at", "entry_at")
    for a, b in zip(captured, oracle):
        for f in fields:
            assert a[f] == b[f], (
                f"senal {f} distinta: run={a[f]} vs sequence_oracle={b[f]} "
                f"(time={a['time']})"
            )


if __name__ == "__main__":
    oracle = _oracle_sequence_signals()
    captured = _run_under_test_captures_signals()
    print(f"ORACLE  : {len(oracle)} senales")
    print(f"RUN     : {len(captured)} senales")
