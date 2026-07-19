"""FASE G — Backtest comparativo (canonico vs legacy) post-migracion.

Corre run_backtest en EURUSD H4->M15 y vuelca metricas: PF, WR, DD,
n señales, n trades, exp R, total R. Solo lectura de resultados; no
toca el motor.

Uso:
    python scripts/fase_g_backtest_compare.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ict_backtest.run_backtest import run_sequence_backtest  # noqa: E402


def main() -> None:
    m = run_sequence_backtest(
        symbol="EURUSD",
        htf="H4",
        ltf="M15",
        max_hold=4,
        counter_trend=True,
        tp_mode="R",
        require_displacement=True,
        displace_gap=2,
        bos_gap=2,
        fill_mode="next_open",
        enable_pd_index=True,
        window_months=24,
    )
    print("=== BACKTEST (canonico) ===")
    for k in ("profit_factor", "win_rate", "max_drawdown", "num_trades",
              "num_signals", "expectancy_r", "total_r"):
        print(f"  {k}: {m.get(k)}")


if __name__ == "__main__":
    main()
