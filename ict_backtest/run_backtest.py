"""ict_backtest/run_backtest.py — Runner PARTE 2: backtest ICT end-to-end.

Opcion A (default): HTF=D1, LTF=H4 (mas datos historicos).
Carga datos -> features ICT -> senales (mini-check dashboard) -> simulacion
vela a vela -> metricas (PF, winrate, expectancy, maxDD en R).

Uso:
  python ict_backtest/run_backtest.py --symbol XAUUSD --htf D1 --ltf H4
  python ict_backtest/run_backtest.py --symbol XAUUSD --htf H4 --ltf H4 --model intradia

NO ejecuta nada pesado en import; solo al correr como script.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _write_runner_progress(
    *,
    current: str,
    done: int | None = None,
    total: int | None = None,
    unit: str = "items",
) -> None:
    """Real progress for Hermes Runner Monitor (HERMES_PROGRESS_FILE).

    No fake %: only write when we know done/total or at least a current stage.
    """
    path = (os.environ.get("HERMES_PROGRESS_FILE") or "").strip()
    if not path:
        return
    payload: dict = {"current": current, "unit": unit}
    if done is not None:
        payload["done"] = int(done)
    if total is not None:
        payload["total"] = int(total)
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass

from ict_backtest.data_feed import load_frames  # noqa: E402
from ict_backtest.costs import resolve_cost  # noqa: E402
from ict_backtest.engine import simulate_trade, ICTSignal  # noqa: E402
from ict_backtest.market_structure import detect_market_structure  # noqa: E402
from ict_backtest.canonical import (  # noqa: E402
    evaluate_signals,
    load_bos_table,
)


def _metrics(pnls: list[float]) -> dict[str, float]:
    n = len(pnls)
    if n == 0:
        return {"trades": 0, "winrate": 0.0, "pf": 0.0, "expectancy": 0.0,
                "max_dd_r": 0.0, "total_r": 0.0}
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    # equity curve en R para maxDD
    equity, peak, max_dd = 0.0, 0.0, 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    return {
        "trades": n,
        "winrate": len(wins) / n,
        "pf": pf,
        "expectancy": sum(pnls) / n,
        "max_dd_r": max_dd,
        "total_r": sum(pnls),
    }


def generate_sequence_signals(symbol: str, htf: str, ltf: str,
                               counter_trend: bool = False,
                               tp_mode: str = "fixed2r",
                               require_displacement: bool = True,
                               displace_gap: int = 6,
                               bos_gap: int | None = 10,
                               bos_table: dict | None = None,
                               frames: dict | None = None,
                               fill_mode: str = "next_open") -> list:
    """R7 thin wrapper — all decision logic lives in ``ict_backtest.canonical``."""
    return evaluate_signals(
        symbol,
        htf,
        ltf,
        counter_trend=counter_trend,
        tp_mode=tp_mode,
        require_displacement=require_displacement,
        displace_gap=displace_gap,
        bos_gap=bos_gap,
        bos_table=bos_table,
        frames=frames,
        fill_mode=fill_mode,
    )


def run_sequence_backtest(symbol: str, htf: str, ltf: str, max_hold: int,
                           counter_trend: bool = False, tp_mode: str = "fixed2r",
                           require_displacement: bool = True,
                           displace_gap: int = 6, bos_gap: int | None = 10,
                           bos_table: dict | None = None,
                           cost: dict | None = None,
                           fill_mode: str = "next_open") -> dict:
    """Capa 2: backtest con motor EVENT-SEQUENCE (espera los sucesos en orden)."""
    tag = f"SEQ-{'CT' if counter_trend else 'AT'}-{tp_mode}{'-disp' if require_displacement else ''}"
    print(f"[1/3] Cargando frames {symbol} + market_structure ...", flush=True)
    _write_runner_progress(
        current=f"[1/3] load+structure {symbol} {htf}->{ltf}",
        done=0,
        total=3,
        unit="stages",
    )
    t0 = time.time()
    frames = load_frames(symbol, tuple(dict.fromkeys([htf, ltf, "D1"])))
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[ltf]
    _write_runner_progress(
        current=f"[2/3] sequence signals {symbol}",
        done=1,
        total=3,
        unit="stages",
    )
    signals = generate_sequence_signals(symbol, htf, ltf,
                                        counter_trend=counter_trend,
                                        tp_mode=tp_mode,
                                        require_displacement=require_displacement,
                                        displace_gap=displace_gap,
                                        bos_gap=bos_gap, frames=frames,
                                        bos_table=bos_table,
                                        fill_mode=fill_mode)
    print(f"      features en {time.time()-t0:.1f}s", flush=True)
    print(f"[2/3] Secuencia EVENT-DRIVEN (sweep->displace->BOS->retorno cuadro) ...", flush=True)
    print(f"      {len(signals)} senales", flush=True)

    print(f"[3/3] Simulando trades vela a vela (max_hold={max_hold}) ...", flush=True)
    pnls: list[float] = []
    exits: dict[str, int] = {}
    total = len(signals)
    _write_runner_progress(
        current=f"[3/3] simulate trades {symbol}",
        done=0,
        total=max(total, 1),
        unit="signals",
    )
    # Update monitor ~20 times max (same cadence as console bar)
    step = max(1, total // 20) if total else 1
    for k, sig in enumerate(signals, 1):
        trade, meta = simulate_trade(ltf_df, sig, max_hold, cost=cost)
        if trade is not None:
            pnls.append(trade.pnl_r)
            exits[meta["exit_reason"]] = exits.get(meta["exit_reason"], 0) + 1
        if total and (k % step == 0 or k == total):
            pct = 100 * k // total
            bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
            print(f"      [{bar}] {pct}% ({k}/{total})", flush=True)
            _write_runner_progress(
                current=f"[3/3] simulate {symbol} {k}/{total}",
                done=k,
                total=total,
                unit="signals",
            )

    m = _metrics(pnls)
    _write_runner_progress(
        current=f"done {symbol} PF={m['pf']:.3f} n={m['trades']}",
        done=total if total else 1,
        total=total if total else 1,
        unit="signals",
    )
    print(f"\n===== RESULTADO [{tag}] =====", flush=True)
    print(f"  simbolo      : {symbol}  |  Capa2 sequence  |  {htf}->{ltf}", flush=True)
    print(f"  trades       : {m['trades']}", flush=True)
    print(f"  winrate      : {m['winrate']*100:.1f}%", flush=True)
    print(f"  profit factor: {m['pf']:.3f}", flush=True)
    print(f"  expectancy   : {m['expectancy']:.3f} R/trade", flush=True)
    print(f"  total        : {m['total_r']:.1f} R", flush=True)
    print(f"  max drawdown : {m['max_dd_r']:.1f} R", flush=True)
    print(f"  salidas      : {exits}", flush=True)
    return m


def run(symbol: str, htf: str, ltf: str, model: str, max_hold: int,
        counter_trend: bool = False, tp_mode: str = "fixed2r",
        require_displacement: bool = False, cost: dict | None = None) -> dict:
    """Backtest POR DEFECTO (sin --engine) sobre el motor canonico sequence.

    R7 T3.1 (DoD #2 / H12): el camino por defecto delega en `run_sequence`
    (motor canonico), NO en `build_signals_from_frames` (isla engine
    divergente: entry en close, RR 1:2). El parametro `model` se portara a
    `SequenceConfig` en T3.3; aqui el motor canonico es event-sequence
    (tesis 18: entry en retorno al cuadro, RR 1:3, SL estructural).
    """
    return run_sequence_backtest(symbol, htf, ltf, max_hold,
                                 counter_trend=counter_trend,
                                 tp_mode=tp_mode,
                                 require_displacement=require_displacement,
                                 cost=cost)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--htf", default="D1")
    ap.add_argument("--ltf", default="H4")
    ap.add_argument("--model", default="intradia", choices=["intradia", "scalping", "po3"],
                    help="po3 = SOLO ciclo PO3 completo (R4 E2, medicion aislada)")
    ap.add_argument("--max-hold", type=int, default=16)
    ap.add_argument("--counter-trend", action="store_true")
    ap.add_argument("--tp-mode", default="fixed2r", choices=["fixed2r", "liquidity"])
    ap.add_argument("--require-displacement", action="store_true")
    ap.add_argument("--cost", default=None,
                    help="costos en pips 'spread,commission,slippage' "
                         "(ej 0.8,0.5,0.3). Override de la tabla por simbolo. "
                         "Por defecto usa COST_BY_SYMBOL del simbolo (costos ON).")
    ap.add_argument("--no-cost", action="store_true",
                    help="modo teoria: SIN costos (no usar en produccion).")
    ap.add_argument("--no-displacement", action="store_true",
                    help="no exigir vela de displacement (sequence engine)")
    ap.add_argument("--sweep", action="store_true",
                    help="corre las 4 variantes PARTE 2.1 y muestra tabla comparativa")
    ap.add_argument("--displace-gap", type=int, default=6,
                    help="ventana displacement tras sweep (sequence engine)")
    ap.add_argument("--bos-gap", type=int, default=10,
                    help="ventana BOS tras displacement (sequence engine)")
    ap.add_argument("--engine", default="sequence", choices=["sequence", "checklist"],
                    help="R7: only sequence is canonical. 'checklist' is an alias to sequence.")
    args = ap.parse_args()

    cost = resolve_cost(args.symbol, override=args.cost, no_cost=args.no_cost)

    # R7: checklist alias removed — always sequence.
    if args.sweep:
        variants = [
            ("V1 AT fixed2r",        dict(counter_trend=False, tp_mode="fixed2r", require_displacement=False)),
            ("V2 AT liquidity+disp", dict(counter_trend=False, tp_mode="liquidity", require_displacement=True)),
            ("V3 CT liquidity+disp", dict(counter_trend=True,  tp_mode="liquidity", require_displacement=True)),
            ("V4 CT fixed2r",        dict(counter_trend=True,  tp_mode="fixed2r",  require_displacement=False)),
        ]
        print("### SWEEP (R7 sequence only) ###")
        for name, kw in variants:
            print(f"\n----- {name} -----")
            m = run(args.symbol, args.htf, args.ltf, args.model, args.max_hold, cost=cost, **kw)
            print(f">>> {name}: PF={m['pf']:.3f} WR={m['winrate']*100:.1f}% trades={m['trades']} R={m['total_r']:.1f}")
        return

    run_sequence_backtest(
        args.symbol, args.htf, args.ltf, args.max_hold,
        counter_trend=args.counter_trend, tp_mode=args.tp_mode,
        require_displacement=not args.no_displacement,
        displace_gap=args.displace_gap, bos_gap=args.bos_gap,
        cost=cost,
    )


if __name__ == "__main__":
    main()
