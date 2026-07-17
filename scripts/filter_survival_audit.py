"""Signal survival audit — which top-down filters kill flow (not optimize edge).

One load + one sequence pass; apply filter combos on the same raw signals.
Saves matrix to results/bt_v2/{symbol}/filter_survival.json

  python scripts/filter_survival_audit.py --symbol EURUSD
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ict_backtest.costs import resolve_cost
from ict_backtest.data_feed import load_frames
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.run_backtest import _metrics, generate_sequence_signals
from ict_backtest.v2.context_mtf import build_context_stack, top_down_allows_trade
from ict_backtest.v2.contracts import Order
from ict_backtest.v2.nearest_tp import apply_nearest_tp_to_signals
from ict_backtest.v2.simulator import simulate_order


def _to_order(s, i, symbol, max_hold=40):
    return Order(
        order_id=f"surv-{i}",
        plan_id="survival",
        symbol=symbol,
        model_id="survival_audit",
        direction=int(s.direction),
        signal_time=str(s.time),
        stop_loss=float(s.stop_loss),
        take_profit=float(s.take_profit),
        max_hold_bars=max_hold,
        entry_price_ref=float(s.entry),
        entry_at=s.entry_at,
        meta={"sweep_at": s.sweep_at, "bos_at": s.bos_at},
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="EURUSD")
    ap.add_argument("--ltf", default="M15")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    tfs = ("D1", "H4", "H1", args.ltf)
    print(f"[survival] load {args.symbol} {tfs} ...", flush=True)
    frames = load_frames(args.symbol, tfs)
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    if "H1" not in ms:
        try:
            from ict_backtest.data_feed import load_tf

            ms["H1"] = detect_market_structure(load_tf(args.symbol, "H1"))
        except Exception as e:
            print(f"[survival] no H1: {e}", flush=True)

    ltf_df = ms[args.ltf]
    print("[survival] sequence (H4 bias → M15) ...", flush=True)
    raw = generate_sequence_signals(
        args.symbol,
        "H4",
        args.ltf,
        counter_trend=False,
        require_displacement=True,
        frames=frames,
        fill_mode="next_open",
    )
    raw = apply_nearest_tp_to_signals(raw, ltf_df, min_rr=3.0)
    print(f"[survival] raw signals: {len(raw)}", flush=True)

    rows = []
    for s in raw:
        stack = build_context_stack(
            ms,
            s.time,
            tfs=("D1", "H4", "H1", args.ltf) if "H1" in ms else ("D1", "H4", args.ltf),
        )
        rows.append((s, stack, int(s.direction)))

    # H4 bias already inside sequence; require_h4=False skips second H4 gate.
    configs = [
        ("sequence only (no extra gates)", dict(require_d1=False, require_h4=False, require_h1=False, require_pd=False)),
        ("+D1", dict(require_d1=True, require_h4=False, require_h1=False, require_pd=False)),
        ("+H1", dict(require_d1=False, require_h4=False, require_h1=True, require_pd=False)),
        ("+PD", dict(require_d1=False, require_h4=False, require_h1=False, require_pd=True)),
        ("+D1+PD", dict(require_d1=True, require_h4=False, require_h1=False, require_pd=True)),
        ("+D1+H1", dict(require_d1=True, require_h4=False, require_h1=True, require_pd=False)),
        ("+H1+PD", dict(require_d1=False, require_h4=False, require_h1=True, require_pd=True)),
        ("D1+H1+PD (no H4 recheck)", dict(require_d1=True, require_h4=False, require_h1=True, require_pd=True)),
        ("D1+H4+PD (no H1) [Paso2]", dict(require_d1=True, require_h4=True, require_h1=False, require_pd=True)),
        ("D1+H4+H1+PD (full mtf)", dict(require_d1=True, require_h4=True, require_h1=True, require_pd=True)),
    ]

    cost = resolve_cost(args.symbol)
    matrix = []
    for name, kwargs in configs:
        kept = []
        reasons: dict[str, int] = {}
        for s, stack, d in rows:
            ok, reason = top_down_allows_trade(stack, d, counter_trend=False, **kwargs)
            reasons[reason] = reasons.get(reason, 0) + 1
            if ok:
                kept.append(s)
        pnls = []
        exits: dict[str, int] = {}
        for i, s in enumerate(kept):
            order = _to_order(s, i, args.symbol)
            tr, meta = simulate_order(order, ltf_df, cost=cost, event_log=None)
            if tr is None:
                r = str(meta.get("exit_reason", "rej"))
                exits[r] = exits.get(r, 0) + 1
                continue
            pnls.append(tr.pnl_r)
            exits[tr.exit_reason] = exits.get(tr.exit_reason, 0) + 1
        m = _metrics(pnls)
        row = {
            "config": name,
            "flags": kwargs,
            "n_raw": len(raw),
            "n_kept": len(kept),
            "survival_pct": round(100.0 * len(kept) / max(len(raw), 1), 1),
            "reasons": reasons,
            "trades": m["trades"],
            "winrate": round(m["winrate"], 4),
            "pf": m["pf"] if m["pf"] != float("inf") else None,
            "expectancy_r": m["expectancy"],
            "total_r": m["total_r"],
            "max_dd_r": m["max_dd_r"],
            "exits": exits,
        }
        matrix.append(row)
        print(
            f"  {name:32s} kept={len(kept):3d} ({row['survival_pct']:5.1f}%)  "
            f"trades={m['trades']:3d}  WR={m['winrate']*100:5.1f}%  "
            f"expR={m['expectancy']:+.3f}  totalR={m['total_r']:+.1f}",
            flush=True,
        )

    out = (
        Path(args.out)
        if args.out
        else _ROOT / "results" / "bt_v2" / args.symbol / "filter_survival.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "symbol": args.symbol,
        "ltf": args.ltf,
        "n_raw_sequence": len(raw),
        "note": (
            "H4 bias already inside run_sequence. Survival audit measures which "
            "extra gates kill sample size vs change expectancy — not param optimization."
        ),
        "matrix": matrix,
    }
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\n[survival] wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
