"""scripts/validate_bos_table.py

Reporte de validacion R10: compara el backtest honesto (R6.4 M2: EURUSD M15,
HTF H4) usando la bos_table empirica cargada vs el bos_gap fijo 40.

Corre el motor sequence REAL sobre un recorte de 8000 velas (mismo subconjunto
para ambas variantes, para que la comparacion sea limpia). Costos ON.

Uso:
  python scripts/validate_bos_table.py --symbol EURUSD --ltf M15 --htf H4 --n 8000
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ict_backtest.data_feed import load_frames  # noqa: E402
from ict_backtest.market_structure import detect_market_structure  # noqa: E402
from ict_backtest.run_backtest import generate_sequence_signals, simulate_trade  # noqa: E402
from ict_backtest.costs import resolve_cost  # noqa: E402


def _pf(pnls: list[float]) -> float:
    wins = [p for p in pnls if p > 0]
    losses = [-p for p in pnls if p < 0]
    gp = sum(wins)
    gl = sum(losses)
    return round((gp / gl), 2) if gl > 0 else float("inf")


def run_variant(symbol, htf, ltf, n, bos_gap):
    frames = load_frames(symbol, (ltf, htf, "D1"))
    for tf in frames:
        frames[tf] = frames[tf].iloc[:n].reset_index(drop=True)
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[ltf]
    cost = resolve_cost(symbol)  # costos ON por defecto
    signals = generate_sequence_signals(
        symbol, htf, ltf, frames=frames, bos_gap=bos_gap,
        fill_mode="next_open", cost=cost,
    )
    if not signals:
        return {"trades": 0, "pf": 0.0, "wr": 0.0, "exp": 0.0}
    pnls: list[float] = []
    for sig in signals:
        trade, _meta = simulate_trade(ltf_df, sig, max_hold_bars=16, cost=cost)
        if trade is not None:
            pnls.append(trade.pnl_r)
    wins = sum(1 for p in pnls if p > 0)
    return {
        "trades": len(pnls),
        "pf": _pf(pnls),
        "wr": round(100 * wins / len(pnls), 1) if pnls else 0.0,
        "exp": round(float(np.mean(pnls)), 3) if pnls else 0.0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="EURUSD")
    ap.add_argument("--htf", default="H4")
    ap.add_argument("--ltf", default="M15")
    ap.add_argument("--n", type=int, default=8000)
    args = ap.parse_args()

    base = dict(symbol=args.symbol, htf=args.htf, ltf=args.ltf, n=args.n)

    print(f"[A] bos_gap FIJO 40 (comportamiento canonico) ...")
    a = run_variant(bos_gap=40, **base)
    print(f"    {a}")

    print(f"[B] bos_table EMPIRICA (R10 dinamico, cargada) ...")
    b = run_variant(bos_gap=None, **base)
    print(f"    {b}")

    print("\n=== COMPARACION (mismo subconjunto {args.n} velas) ===")
    print(f"  trades : A={a['trades']}  B={b['trades']}")
    print(f"  PF     : A={a['pf']}  B={b['pf']}")
    print(f"  WR %   : A={a['wr']}  B={b['wr']}")
    print(f"  Exp(R) : A={a['exp']}  B={b['exp']}")
    delta = b["pf"] - a["pf"]
    print(f"  Delta PF (B-A): {delta:+.2f}  -> {'MEJORA' if delta > 0 else 'EMPEORA' if delta < 0 else 'IGUAL'}")


if __name__ == "__main__":
    main()
