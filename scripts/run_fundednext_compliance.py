"""
Runner: genera trades con el backtest engine EXISTENTE de SMC-SYSTEMS
(us_ml_quality_filter=False para velocidad) y los evalua contra las reglas
de FundedNext Stellar Lite $5K via tools/fundednext_compliance.py.

NO toca produccion. Solo mide cumplimiento de reglas sobre trades reales
que el sistema ya produciria.

Uso:
  python scripts/run_fundednext_compliance.py
  python scripts/run_fundednext_compliance.py --risk-pct 1.0 --symbols EURUSD,GBPUSD,XAUUSD
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from legacy.backtest import CombinedBacktestConfig, run_combined_backtest
from tools.fundednext_compliance import (
    StellarLiteRules, evaluate, report_to_text,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="FundedNext Stellar Lite compliance check")
    ap.add_argument("--risk-pct", type=float, default=1.0,
                    help="riesgo fijo por trade en %% del balance (<=3%%). Default 1.0")
    ap.add_argument("--symbols", type=str, default="EURUSD,GBPUSD,XAUUSD",
                    help="simbolos separados por coma (deben tener M15 en data/raw)")
    ap.add_argument("--timeframe", type=str, default="M15")
    ap.add_argument("--min-confidence", type=float, default=0.52)
    ap.add_argument("--account", type=float, default=5000.0, help="balance inicial Stellar Lite")
    ap.add_argument("--max-bars", type=int, default=None, help="limitar barras (debug)")
    ap.add_argument("--start-time", type=str, default=None,
                    help="ventana temporal inicio (ISO, p.ej. 2025-01-01). Acorta el frame ANTES del contexto.")
    ap.add_argument("--end-time", type=str, default=None,
                    help="ventana temporal fin (ISO)")
    args = ap.parse_args()

    symbols = tuple(s.strip() for s in args.symbols.split(",") if s.strip())

    print(f"[*] Generando trades con backtest engine (symbols={symbols}, "
          f"tf={args.timeframe}, ml_filter=OFF)...")
    cfg = CombinedBacktestConfig(
        data_dir=Path("data/raw"),
        symbols=symbols,
        timeframe=args.timeframe,
        min_confidence=args.min_confidence,
        use_ml_quality_filter=False,
        max_bars=args.max_bars,
        start_time=args.start_time,
        end_time=args.end_time,
    )
    metrics, trades = run_combined_backtest(cfg)
    if trades is None or len(trades) == 0:
        print("[!] El backtest no produjo trades. Revisa datos en data/raw "
              "y min_confidence.")
        return 1

    print(f"[*] Trades generados: {len(trades)}")
    print(f"[*] Backtest WR={metrics.get('win_rate', 0):.2%} "
          f"PF={metrics.get('profit_factor', 0):.2f} "
          f"DD={metrics.get('max_drawdown_pct', 0):.2f}%")

    tdf = trades if isinstance(trades, pd.DataFrame) else pd.DataFrame([asdict(t) for t in trades])
    # Asegurar columnas requeridas por el compliance
    need = ["symbol", "entry_time", "exit_time", "direction", "pnl_r",
            "confidence", "entry", "exit"]
    for c in need:
        if c not in tdf.columns:
            raise SystemExit(f"[!] Falta columna {c} en trades del backtest")
    tdf["entry_time"] = tdf["entry_time"].astype(str)

    rules = StellarLiteRules(initial_balance=args.account)
    rep = evaluate(tdf, rules=rules, risk_pct=args.risk_pct)
    print()
    print(report_to_text(rep))

    # Persistir para analisis posterior
    out_path = Path("results/fundednext_stellar_lite_compliance.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tdf.to_csv(out_path, index=False)
    print(f"\n[*] Trades persistidos en {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
