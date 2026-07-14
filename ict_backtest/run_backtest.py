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
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.data_feed import load_frames  # noqa: E402
from ict_backtest.engine import (build_signals_from_frames, simulate_trade, ICTSignal,  # noqa: E402
                                 calc_structural_sl, _tp_liquidity, STRUCT_SL_MAX_ATR)  # noqa: E402
from ict_backtest.rules import killzone_en  # noqa: E402
from ict_backtest.market_structure import detect_market_structure  # noqa: E402
from ict_backtest.sequence import run_sequence, SequenceConfig, _row_at_time  # noqa: E402


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


def run_sequence_backtest(symbol: str, htf: str, ltf: str, max_hold: int,
                           counter_trend: bool = False, tp_mode: str = "fixed2r",
                           require_displacement: bool = True,
                           displace_gap: int = 6, bos_gap: int = 10,
                           cost: dict | None = None) -> dict:
    """Capa 2: backtest con motor EVENT-SEQUENCE (espera los sucesos en orden)."""
    tfs = tuple(dict.fromkeys([htf, ltf, "D1"]))
    tag = f"SEQ-{'CT' if counter_trend else 'AT'}-{tp_mode}{'-disp' if require_displacement else ''}"
    print(f"[1/3] Cargando frames {symbol} {tfs} + market_structure ...", flush=True)
    t0 = time.time()
    frames = load_frames(symbol, tfs)
    for tf, df in frames.items():
        print(f"      {tf}: {len(df)} velas", flush=True)
    # Market structure con memoria (BOS/CHOCH canonicos) en cada TF
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    print(f"      features en {time.time()-t0:.1f}s", flush=True)

    ltf_df = ms[ltf]
    htf_df = ms.get(htf, ltf_df)

    def est_htf_fn(i):
        t = ltf_df.iloc[i]["time"]
        r = _row_at_time(htf_df, t)
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False))}

    print(f"[2/3] Secuencia EVENT-DRIVEN (sweep->displace->BOS->retorno cuadro) ...", flush=True)
    t0 = time.time()
    raw_sigs, phases = run_sequence(ltf_df, est_htf_fn,
                                    SequenceConfig(counter_trend=counter_trend,
                                                   tp_mode=tp_mode,
                                                   require_displacement=require_displacement,
                                                   displace_gap=displace_gap,
                                                   bos_gap=bos_gap))
    print(f"      fases: {phases}", flush=True)
    print(f"      {len(raw_sigs)} senales en {time.time()-t0:.1f}s", flush=True)

    # Convertir a ICTSignal con SL/TP y simular (ALINEADO A TESIS 18)
    print(f"[3/3] Simulando trades vela a vela (max_hold={max_hold}) ...", flush=True)
    signals = []
    for s in raw_sigs:
        direction = s["direction"]
        entry_at = s["entry_at"]
        entry_row = ltf_df.iloc[entry_at]
        entry = s["entry"]
        atr = float(entry_row.get("atr", 0.0) or 0.0)
        if not (atr > 0):
            continue
        # Filtro killzone (tesis #8): solo London Open / NY AM / NY PM.
        kz = killzone_en(pd.to_datetime(entry_row["time"], utc=True))
        if kz not in ("London Open", "New York AM", "New York PM"):
            continue
        # SL ESTRUCTURAL (tesis #3 / libro 14): anclado a la MECHA del sweep,
        # no a BOS+-ATR ni ATR ciego. Lee el row de la vela del sweep (exec TF).
        sweep_row = ltf_df.iloc[s["sweep_at"]]
        sl = calc_structural_sl(sweep_row, direction, atr)
        if sl is None:
            continue  # tesis: sin nivel estructural -> NO operar
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        # Filtro de tamaño (engine STRUCT_SL_MAX_ATR): sweep gigante rompe RR.
        if risk > STRUCT_SL_MAX_ATR * atr:
            continue
        # TP con RR 1:3 (tesis #7): liquidez opuesta del exec TF si existe.
        liq = _tp_liquidity(entry_row, direction)
        if liq is not None:
            tp = liq
        else:
            tp = entry + 3.0 * risk if direction == 1 else entry - 3.0 * risk
        # Garantizar RR >= 1:3 (TP mas alla del SL en la direccion correcta).
        if direction == 1 and tp <= entry + 2.0 * risk:
            tp = entry + 3.0 * risk
        if direction == -1 and tp >= entry - 2.0 * risk:
            tp = entry - 3.0 * risk
        signals.append(ICTSignal(symbol=symbol, time=s["time"], direction=direction,
                                 entry=entry, stop_loss=sl, take_profit=tp,
                                 model="sequence"))

    pnls: list[float] = []
    exits: dict[str, int] = {}
    total = len(signals)
    for k, sig in enumerate(signals, 1):
        trade, meta = simulate_trade(ltf_df, sig, max_hold, cost=cost)
        if trade is not None:
            pnls.append(trade.pnl_r)
            exits[meta["exit_reason"]] = exits.get(meta["exit_reason"], 0) + 1
        if total and (k % max(1, total // 20) == 0 or k == total):
            pct = 100 * k // total
            bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
            print(f"      [{bar}] {pct}% ({k}/{total})", flush=True)

    m = _metrics(pnls)
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
    tfs = tuple(dict.fromkeys([htf, ltf, "D1"]))  # unicos, D1 para contexto
    tag = f"{'CT' if counter_trend else 'AT'}-{tp_mode}{'-disp' if require_displacement else ''}"
    print(f"[1/3] Cargando frames {symbol} {tfs} + features ICT ...", flush=True)
    t0 = time.time()
    frames = load_frames(symbol, tfs)
    for tf, df in frames.items():
        print(f"      {tf}: {len(df)} velas ({df['time'].min()} -> {df['time'].max()})", flush=True)
    print(f"      features en {time.time()-t0:.1f}s", flush=True)

    print(f"[2/3] Generando senales (modelo={model}, htf={htf}, ltf={ltf}, {tag}) ...", flush=True)
    t0 = time.time()
    signals = build_signals_from_frames(symbol, frames, bias_by_tf={}, model=model,
                                        htf=htf, ltf=ltf, counter_trend=counter_trend,
                                        tp_mode=tp_mode, require_displacement=require_displacement)
    print(f"      {len(signals)} senales en {time.time()-t0:.1f}s", flush=True)

    print(f"[3/3] Simulando trades vela a vela (max_hold={max_hold}) ...", flush=True)
    ltf_df = frames[ltf]
    pnls: list[float] = []
    exits: dict[str, int] = {}
    total = len(signals)
    for k, sig in enumerate(signals, 1):
        trade, meta = simulate_trade(ltf_df, sig, max_hold, cost=cost)
        if trade is not None:
            pnls.append(trade.pnl_r)
            exits[meta["exit_reason"]] = exits.get(meta["exit_reason"], 0) + 1
        if total and (k % max(1, total // 20) == 0 or k == total):
            pct = 100 * k // total
            bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
            print(f"      [{bar}] {pct}% ({k}/{total})", flush=True)

    m = _metrics(pnls)
    print(f"\n===== RESULTADO [{tag}] =====", flush=True)
    print(f"  simbolo      : {symbol}  |  modelo: {model}  |  {htf}->{ltf}", flush=True)
    print(f"  trades       : {m['trades']}", flush=True)
    print(f"  winrate      : {m['winrate']*100:.1f}%", flush=True)
    print(f"  profit factor: {m['pf']:.3f}", flush=True)
    print(f"  expectancy   : {m['expectancy']:.3f} R/trade", flush=True)
    print(f"  total        : {m['total_r']:.1f} R", flush=True)
    print(f"  max drawdown : {m['max_dd_r']:.1f} R", flush=True)
    print(f"  salidas      : {exits}", flush=True)
    return m


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
                         "(ej 0.8,0.5,0.3). Si se omite, sin costos (teorico).")
    ap.add_argument("--no-displacement", action="store_true",
                    help="no exigir vela de displacement (sequence engine)")
    ap.add_argument("--sweep", action="store_true",
                    help="corre las 4 variantes PARTE 2.1 y muestra tabla comparativa")
    ap.add_argument("--displace-gap", type=int, default=6,
                    help="ventana displacement tras sweep (sequence engine)")
    ap.add_argument("--bos-gap", type=int, default=10,
                    help="ventana BOS tras displacement (sequence engine)")
    ap.add_argument("--engine", default="checklist", choices=["checklist", "sequence"],
                    help="checklist=mini-check dashboard (PARTE 2); sequence=event-sequence (Capa 2)")
    args = ap.parse_args()

    cost = None
    if args.cost:
        sp, cp, slp = (float(x) for x in args.cost.split(","))
        cost = {"spread_pips": sp, "commission_pips": cp, "slippage_pips": slp}

    if args.engine == "sequence":
        run_sequence_backtest(args.symbol, args.htf, args.ltf, args.max_hold,
                              counter_trend=args.counter_trend, tp_mode=args.tp_mode,
                              require_displacement=not args.no_displacement,
                              displace_gap=args.displace_gap, bos_gap=args.bos_gap,
                              cost=cost)
        return

    if args.sweep:
        variants = [
            ("V1 AT fixed2r",        dict(counter_trend=False, tp_mode="fixed2r", require_displacement=False)),
            ("V2 AT liquidity+disp", dict(counter_trend=False, tp_mode="liquidity", require_displacement=True)),
            ("V3 CT liquidity+disp", dict(counter_trend=True,  tp_mode="liquidity", require_displacement=True)),
            ("V4 CT fixed2r",        dict(counter_trend=True,  tp_mode="fixed2r",  require_displacement=False)),
        ]
        print("### SWEEP PARTE 2.1 (XAUUSD D1->H4) ###")
        for name, kw in variants:
            print(f"\n----- {name} -----")
            m = run(args.symbol, args.htf, args.ltf, args.model, args.max_hold, cost=cost, **kw)
            print(f">>> {name}: PF={m['pf']:.3f} WR={m['winrate']*100:.1f}% trades={m['trades']} R={m['total_r']:.1f}")
        return

    run(args.symbol, args.htf, args.ltf, args.model, args.max_hold,
        counter_trend=args.counter_trend, tp_mode=args.tp_mode,
        require_displacement=args.require_displacement, cost=cost)


if __name__ == "__main__":
    main()
