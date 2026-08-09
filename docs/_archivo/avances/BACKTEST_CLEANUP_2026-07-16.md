# Limpieza residuos backtest viejo — 2026-07-16

## Borrado (residuos / one-shots)

| Path | Motivo |
|------|--------|
| `ict_backtest/_cmp_bos.py` | Diag CHOCH one-shot |
| `ict_backtest/_diag_signals.py` | Diag señales one-shot |
| `ict_backtest/_smoke.py` | Smoke viejo (reemplazo: tests v2 + CLI v2) |
| `scripts/r4_turtle_v28.py`, `v29_structsl.py`, `r4_chain.py` | Experimentos R4 |
| `scripts/fase0_*.py`, `fase0_*.bat` | Migración event-driven one-shot |
| `results/_quick_backtest.json`, `r6_*.txt`, `runner_progress_smoke-echo.json` | Outputs basura |

## Conservado (NO es residuo)

| Path | Por qué |
|------|---------|
| `ict_backtest/sequence.py`, `engine.py`, `run_backtest.py` | Motor de strategy + helpers usados por **v2** |
| `ict_backtest/v2/*` | Path oficial nuevo |
| `legacy/backtest/*` | Stack scalping/ML + harness (otro producto; no borrado) |
| `optimize.py`, `plot_equity_curve.py` | Aún referenciables; no one-shot basura |

## Path oficial de corrida

```bat
python scripts\runner_monitor.py --window --title "bt-v2" -- python -m ict_backtest.v2.run_v2 --mode mtf --symbol EURUSD
```
