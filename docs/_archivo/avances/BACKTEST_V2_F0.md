# Backtest v2 — Fase 0 implementada

**Fecha:** 2026-07-16  
**Spec:** `docs/plan/BACKTEST_V2_SPEC.md` v1.1  
**Estado:** F0 código + tests (sin multi-TF D1/H1/M5 aún)

## Qué se entregó

| Pieza | Ruta |
|-------|------|
| Contratos Plan/Order/Trade/Event/Explanation | `ict_backtest/v2/contracts.py` |
| EventLog JSONL | `ict_backtest/v2/event_log.py` |
| Coverage Matrix + Report automático | `ict_backtest/v2/coverage.py` |
| Simulator puro (wrapper) | `ict_backtest/v2/simulator.py` |
| Adapter legacy → TradingPlan | `ict_backtest/v2/strategy_legacy.py` |
| Orquestador legacy_subset | `ict_backtest/v2/orchestrator.py` |
| CLI | `python -m ict_backtest.v2.run_v2` |
| Tests | `tests/test_backtest_v2_f0.py` |

## Pipeline F0

```text
generate_sequence_signals (strategy actual H4→M15)
        ↓
TradingPlan + Orders  (coverage_mode=legacy_subset)
        ↓
simulate_order (sin if ICT)
        ↓
Coverage Report + EventLog + Explanations
```

## Cómo correr (ops)

```bat
python scripts\runner_monitor.py --window --title "bt-v2-EURUSD" -- python -m ict_backtest.v2.run_v2 --symbol EURUSD --htf H4 --ltf M15
```

Artefactos: `results/bt_v2/{symbol}/legacy_subset/`

## Veredicto de métricas

Toda corrida F0 imprime que es **implementación parcial**, no edge de la tesis completa.  
`coverage_pct` sale del registry C0x (no de estimación en chat).

## F1–F5 parcial (2026-07-16) — modo `mtf`

| Capacidad | Estado |
|-----------|--------|
| D1 en decisión (gate) | ✅ |
| H4 bias (sequence HTF) | ✅ |
| H1 no-opone | ✅ (si hay datos H1) |
| Premium/Discount D1 | ✅ |
| Cascada top-down (no bottom-up) | ✅ |
| TP swing más cercano + min RR 3 | ✅ |
| Plan → Orders → Sim | ✅ |
| OOS split cronológico (`--oos 0.3`) | ✅ |
| M5 exec / POI narrative full / BE management | ❌ siguiente |

```bat
python scripts\runner_monitor.py --window --title "bt-v2-mtf-EURUSD" -- python -m ict_backtest.v2.run_v2 --mode mtf --symbol EURUSD --oos 0.3
```

Coverage mode: `v2_partial` (reporte C0x sube vs legacy_subset; no es aún v2_full).
