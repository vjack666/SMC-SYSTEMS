# Mapa de Arquitectura — SMC-SYSTEMS

Generado con graphify sobre el grafo de código (3463 nodos, 6338 edges, 240 comunidades).
Grafo construido 2026-07-14 desde commit `46b074e`. Este documento es un resumen
de navegación: para el grafo interactivo ver `graphify-out/graph.html`.

> Fuente de verdad de la topología: `graphify-out/graph.json`. Para refrescar tras
> cambios de código: `graphify update .` (sin costo de API, AST puro).
> Auditoría de separación ICT: `scripts/check_separation.py`.

## Composición del grafo por módulo raíz (nodos)

| Módulo | Nodos | Rol |
|--------|------:|-----|
| `docs/` | 1057 | Biblioteca ICT/Wyckoff + plan (índice de conocimiento, no ejecutable) |
| `tests/` | 477 | Batería de tests (unitarios + harness + integración) |
| `scripts/` | 327 | Launchers, corridas de backtest, diagnóstico, bucles |
| `legacy/` (backtest engine) | 294 | Motor de backtest combinado + ML heredado (`backtest/engine.py`) |
| `app_observador/` | 143 | App de escritorio PySide6 (semáforo, mapa ICT, Wyckoff) |
| `ict_backtest/` | 140 | Motor ICT desde cero (SMC puro, sin ML) |
| `ml/` | 105 | Dataset, trainer XGBoost, walk-forward, validación estadística |
| `integration/` (mt5_bridge) | 94 | Puente MT5 ZeroMQ (NO cableado al loop diario) |
| `agents/` | 78 | ICT / Wyckoff(+stoch exhaustion) / Structure / Decision (voting) |
| `detectors/` | 66 | Niveles ICT LuxAlgo ports (BOS, CHOCH, FVG, OB, killzones, nwog/ndog) |
| `paper_trading/` | 42 | Paper trading runner (heredado) |
| `monitoring/` | 41 | AutoReport, Alerter, DriftDetector |
| `adapters/` | 31 | Enriquecimiento de features + adapters harness/pipeline |
| `risk/` | 27 | Risk Governor (NORMAL→CAUTION→DEFENSIVE→LOCKDOWN) |
| `features/` | 16 | FeatureEngine (30+ features) |
| `orchestration/` | 15 | LangGraph backtest validation graph (7 nodes) |
| `tools/` | 13 | Cumplimiento FundedNext, helpers |
| `signals/` | 12 | Pipeline de confluencia en vivo (`build_scalping_context`) |
| `data/` | 9 | Carga OHLCV Parquet / MT5 |

## God Nodes (abstracciones centrales, por nº de conexiones)

1. `PaperTradingRunner` (`paper_trading/runner.py`) — 59 edges
2. `FeatureEngine` (`features/engine.py`) — 59 edges
3. `ScalpingConfig` (`signals/pipeline.py`) — 56 edges
4. `build_scalping_context()` (`signals/pipeline.py`) — 53 edges
5. `legacy_backtest_engine` (`backtest/engine.py`) — 49 edges
6. `AgentOrchestrator` (`agents/orchestrator.py`) — 44 edges
7. `WyckoffAgent` (`agents/wyckoff_agent.py`) — 43 edges
8. `tests/test_detectors` — 42 edges
9. `run_combined_backtest()` (`backtest/engine.py`) — 39 edges
10. `SignalMessage` (`integration/mt5_bridge/schema.py`) — 39 edges

## Flujo de datos (pipeline → engine → governor)

```
_data_legacy.load_frame()            [datos crudos OHLCV]
        │
        ▼
signals/pipeline.build_scalping_context()   [Community signals]
        │   detect_choch / detect_order_blocks / detect_fvg / detect_displacement
        ▼
ScalpingConfig → ScalpingSignal      [estructura de señal SMC]
        │
        ▼
backtest/engine._build_signals_from_context()   [legacy combine]
        │
        ▼
backtest/engine.run_combined_backtest()         [legacy motor]  ← motor combinado + ML
        │
        ├─► harness/SignalAdapter    → SignalMessage
        │                                  │
        │                                  ▼
        │                          risk/governor.GovernorState   (RiskGovernorAdapter)
        │                                  │
        │                                  ▼
        │                          next_state() / GovernorPool
        │
        └─► integration/mt5_bridge  → MT5Receiver / MT5BacktestRunner  [NO cableado]
```

## Comunidades de mayor cohesión (top por tamaño)

| Comunidad | Tamaño | Módulos dominantes | Rol |
|-----------|------:|--------------------|-----|
| 46 | 76 | scripts + ml + tests | Corridas de diagnóstico / tuning |
| 6 | 75 | tests + features + ml | Tests de features + ML |
| 27 | 57 | scripts + signals + legacy | Pipeline en vivo + launchers |
| 4 | 53 | tests + ml | Tests ML / validación |
| 13 | 42 | tests + ml | Tests ML / stats |
| 9 | 41 | tests + risk + adapters | Risk governor + adapters |
| 83 | 33 | legacy + data | Motor combinado heredado |
| 16 | 32 | detectors + scripts | Detectores ICT + launchers |
| 7 | 32 | integration | Puente MT5 ZeroMQ |

## Fragmentación observada (deuda de arquitectura) — MEDICIÓN 2026-07-14

El grafo confirma que la "misma estrategia ICT" vive en **islas separadas**. Medido
con `scripts/check_separation.py` sobre `graphify-out/graph.json` @ `46b074e`:

| Módulo | Comunidad(es) | Aristas cruzadas |
|--------|---------------|------------------|
| `signals/pipeline.py` | 1 / 2 / 5 / 73 | 0 (isla) |
| `agents/ict_agent.py` | 39 / 62 | 0 (isla) |
| `ict_backtest/sequence.py` | 36 / 70 | 0 (isla) |
| `ict_backtest/rules.py` | 57 | solo con engine (2) |
| `ict_backtest/engine.py` | 18 | solo con rules (2) |

**Hallazgo:** 5 módulos ICT en 6 comunidades distintas. **Solo 2 aristas cruzadas en
todo el sistema**: `engine.py ↔ rules.py` (el motor llama a los checklists). `pipeline.py`,
`ict_agent.py`, `sequence.py` son islas totales (0 aristas cruzadas entre sí y con el resto).

Consecuencia: backtest (`sequence.py`/`engine.py`) y señales en vivo (`pipeline.py`)
salen de motores distintos con pesos que divergen → riesgo de "backtest bueno, vivo malo".

El roadmap (`docs/plan/ROADMAP_BIBLIOTECA_Y_APLICACION.md`, **R7**) planea unificar en
una sola función `evaluate(model=...)` (single source of truth). R1 ya lo hizo para PO3.

## Estado de integridad

- Ciclos de import: **ninguno detectado** (grafo acíclico en imports — buena higiene).
- Calidad de extracción: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS.
- Token cost: 0 (extracción puramente AST, sin LLM).

## Cómo ampliar / refrescar

- Grafo fresco al 2026-07-14 (commit `46b074e`); tras cambios de código:
  `graphify update .` (sin costo de API).
- Query interactivo: `graphify query "<pregunta>"` (usa `graphify-out/graph.json`).
- HTML interactivo: `graphify-out/graph.html`.
