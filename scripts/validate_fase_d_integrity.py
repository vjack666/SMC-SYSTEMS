"""Fase D — VALIDACION de integridad de TradeContext (PRE-Paso 3).

NO es el Diagnosis Engine. Es una auditoria de integridad: verifica que la
infraestructura del Paso 2 realmente captura el contexto correctamente, ANTES
de construir Statistics/Correlation/Hypothesis (Paso 3).

Objetivo (Ruben 2026-07-18): no buscar PF alto, sino validar que por cada
trade se genera EXACTAMENTE UN TradeContext con toda la metadata esperada.

No genera hipotesis. No interpreta. Solo cuenta y reporta integridad.

Uso:
  python scripts/validate_fase_d_integrity.py --symbol EURUSD --months 6
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from ict_backtest.run_backtest import run_sequence_backtest  # noqa: E402
from ict_backtest.diagnostics.context_builder import (  # noqa: E402
    RawDiagnosticData, build_trade_context,
)


def _authority_bucket(z: dict | None) -> str:
    if z is None:
        return "NONE"
    if not z.get("has_htf_anchor"):
        return "SIN_ANCLA"
    lvl = z.get("level", "Baja")
    return {"Alta": "Alta", "Media": "Media", "Baja": "Baja"}.get(lvl, "Baja")


def validate(symbol: str, months: int, htf: str, ltf: str) -> dict:
    backtest_id = f"BT-VAL-{symbol}-{months}M"
    m = run_sequence_backtest(
        symbol, htf, ltf, max_hold=96,
        require_displacement=False,
        enable_pd_index=True,
        backtest_id=backtest_id,
        window_months=months,
    )
    contexts = m["contexts"]
    n_trades = m["trades"]
    n_ctx = len(contexts)

    # Congelar cada raw -> TradeContext (esto es lo que hara Paso 3)
    frozen = []
    for raw in contexts:
        assert isinstance(raw, RawDiagnosticData)
        frozen.append(build_trade_context(raw))

    # --- Matriz de cobertura ---
    missing = 0
    f_zone = 0
    f_bias = 0
    f_phase = 0
    f_sig = 0
    f_ids = 0
    f_ts = 0
    auth_counts: dict[str, int] = {}
    signal_ids: set[str] = set()
    trade_ids: set[str] = set()
    for ctx in frozen:
        if ctx.zone_authority is None:
            f_zone += 1
        else:
            missing += 0
        if ctx.htf_bias is None or ctx.htf_bias == "RANGING":
            f_bias += 1
        if not ctx.phase_log:
            f_phase += 1
        if not ctx.signal_id:
            f_sig += 1
        else:
            signal_ids.add(ctx.signal_id)
        if not ctx.trade_id:
            f_ids += 1
        else:
            trade_ids.add(ctx.trade_id)
        if not ctx.context_created_at:
            f_ts += 1
        b = _authority_bucket(ctx.zone_authority)
        auth_counts[b] = auth_counts.get(b, 0) + 1

    coverage = {
        "trades": n_trades,
        "trade_contexts": n_ctx,
        "integrity_1to1": (n_trades == n_ctx),
        "zone_authority": n_ctx - f_zone,
        "htf_bias_real": n_ctx - f_bias,
        "phase_log": n_ctx - f_phase,
        "signal_id": n_ctx - f_sig,
        "trade_id": n_ctx - f_ids,
        "context_created_at": n_ctx - f_ts,
        "backtest_id_unique": len({ctx.backtest_id for ctx in frozen}),
        "unique_signal_ids": len(signal_ids),
        "unique_trade_ids": len(trade_ids),
        "missing_fields": f_zone + f_bias + f_phase + f_sig + f_ids + f_ts,
        "authority_distribution": auth_counts,
    }

    # --- Imprimir reporte (humano) ---
    print("\n=== Diagnosis Coverage ===\n")
    print(f"Trades....................{n_trades}")
    print(f"TradeContext..............{n_ctx} ({100*n_ctx//max(n_trades,1)}%)")
    print(f"ZoneAuthority............{coverage['zone_authority']} ({100*(n_ctx-f_zone)//max(n_ctx,1)}%)")
    print(f"HTF Bias (real).........{coverage['htf_bias_real']} ({100*(n_ctx-f_bias)//max(n_ctx,1)}%)")
    print(f"Phase Log................{coverage['phase_log']} ({100*(n_ctx-f_phase)//max(n_ctx,1)}%)")
    print(f"Signal ID................{coverage['signal_id']} ({100*(n_ctx-f_sig)//max(n_ctx,1)}%)")
    print(f"Trade ID.................{coverage['trade_id']} ({100*(n_ctx-f_ids)//max(n_ctx,1)}%)")
    print(f"Context Created At.......{coverage['context_created_at']} ({100*(n_ctx-f_ts)//max(n_ctx,1)}%)")
    print(f"Backtest ID (unique)....{coverage['backtest_id_unique']}")
    print(f"Unique Signal IDs.......{len(signal_ids)}")
    print(f"Unique Trade IDs........{len(trade_ids)}")
    print(f"Missing fields...........{coverage['missing_fields']}")
    print("\n--- Authority distribution (sin conclusion) ---")
    for k in ("Alta", "Media", "Baja", "SIN_ANCLA", "NONE"):
        if k in auth_counts:
            print(f"  {k}: {auth_counts[k]}")
    print("\n--- Traditional metrics (contexto, no objetivo) ---")
    print(f"  PF={m['pf']:.3f}  WR={m['winrate']*100:.1f}%  N={n_trades}  R={m['total_r']:.1f}")
    ok = coverage["integrity_1to1"] and coverage["missing_fields"] == 0
    print("\n" + ("✔ INTEGRIDAD OK" if ok else "✘ INTEGRIDAD FALLA — detener Paso 3"))

    # --- Guardar artefactos ---
    out_dir = ROOT / "results" / "backtests" / f"{datetime.now(timezone.utc):%Y-%m-%d}_{months}m" / symbol
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps({
        "backtest_id": backtest_id,
        "symbol": symbol, "htf": htf, "ltf": ltf, "window_months": months,
        "pf": m["pf"], "winrate": m["winrate"], "trades": n_trades,
        "expectancy": m["expectancy"], "total_r": m["total_r"],
        "max_dd_r": m["max_dd_r"],
        "exits": {c.exit_reason: sum(1 for x in frozen if x.exit_reason == c.exit_reason)
                   for c in frozen},
    }, indent=2))
    ctx_records = [__import__("dataclasses").asdict(c) for c in frozen]
    (out_dir / "contexts.json").write_text(json.dumps(ctx_records, default=str, indent=2))
    eq = pd.DataFrame({"pnl_r": [c.pnl_r for c in frozen]})
    eq.to_csv(out_dir / "equity.csv", index=False)
    (out_dir / "coverage.json").write_text(json.dumps(coverage, indent=2))
    # diagnostics/ vacio pero preparado
    (out_dir / "diagnostics").mkdir(exist_ok=True)
    print(f"\nArtifacts en: {out_dir}")
    return {"coverage": coverage, "ok": ok, "out_dir": str(out_dir)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="EURUSD")
    ap.add_argument("--months", type=int, default=6)
    ap.add_argument("--htf", default="H4")
    ap.add_argument("--ltf", default="M15")
    args = ap.parse_args()
    r = validate(args.symbol, args.months, args.htf, args.ltf)
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()
