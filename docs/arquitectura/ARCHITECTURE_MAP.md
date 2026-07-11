# Mapa de Arquitectura — SMC-SYSTEMS

Generado con graphify sobre el grafo de código (1705 nodos, 4557 edges, 98 comunidades).
Grafo construido 2026-07-09 desde commit `bd335a8b`. Este documento es un resumen
de navegación: para el grafo interactivo ver `graphify-out/graph.html`.

## Subsistemas principales (comunidades de mayor cohesión)

| Comunidad | Cohesión | Archivo raíz | Rol |
|-----------|---------:|--------------|-----|
| 8 | 0.16 | `signals/pipeline.py` | **Núcleo de detectores SMC** — `build_scalping_context()`, `detect_choch()`, `detect_order_blocks()`, `AgentOrchestrator`, `ScalpingConfig` |
| 30 / 27 / 29 | — | `backtest/engine.py` | **Motor de backtest** — `run_combined_backtest()`, `CombinedBacktestConfig`, `_build_signals_from_context()` |
| 10 | 0.12 | `risk/governor.py` | **Risk Governor** — `GovernorState`, `GovernorPool`, `GovernorConfig`, `next_state()` |
| 2 | 0.06 | `harness/` | **Adapters de ensamblaje** — `RiskGovernorAdapter`, `SignalAdapter`, `BacktestAdapter` (conectan pipeline→engine→governor) |
| 3 | 0.06 | `adapters/feature_enrichment_adapter.py` | Enriquecimiento de features + indicadores (`add_atr`, `add_ema`, `add_rsi`) |
| 5 / 4 / 13 / 18 | — | `ml/` | **ML** — `build_ml_dataset()`, `trainer.py`, `walk_forward.py`, `PurgedKFold`, validación estadística |
| 7 / 12 | — | `integration/mt5_bridge/` | **Integración MT5** — `MT5BridgeAdapter`, `MT5Receiver`, `MT5BacktestRunner`, `SignalMessage` |
| 14 | 0.14 | `orchestration/backtest_validation_graph.py` | **Orquestación/validación** — `build_validation_graph()`, `compare_results()`, `generate_report()` |
| 16 | 0.10 | `detectors/` (ICT LuxAlgo ports) | Niveles ICT — `fib_levels()`, `detect_killzones()`, `detect_nwog_ndog()` |
| 1 | 0.07 | `monitoring/` | Monitoreo — `AutoReportGenerator`, `Alerter`, `DriftDetector` |

## God Nodes (abstracciones centrales, por nº de conexiones)

1. `FeatureEngine` (`src/features/engine.py`) — 59 edges
2. `PaperTradingRunner` (`paper_trading/runner.py`) — 59 edges
3. `AgentOrchestrator` (`agents/orchestrator.py`) — 44 edges
4. `run_combined_backtest()` (`backtest/engine.py`) — 44 edges
5. `build_scalping_context()` (`signals/pipeline.py`) — 44 edges
6. `WyckoffAgent` (`agents/wyckoff_agent.py`) — 43 edges
7. `ScalpingConfig` (`signals/pipeline.py`) — 43 edges
8. `SignalMessage` (`integration/mt5_bridge/schema.py`) — 39 edges
9. `TestFeatureEngine` — 37 edges
10. `GovernorState` (`risk/governor.py`) — 36 edges

## Flujo de datos (pipeline → engine → governor)

```
_data_legacy.load_frame()            [datos crudos OHLCV]
        │
        ▼
signals/pipeline.build_scalping_context()   [Community 8]
        │   detect_choch / detect_order_blocks / detect_fvg / detect_displacement
        ▼
ScalpingConfig → ScalpingSignal      [estructura de señal SMC]
        │
        ▼
backtest/engine._build_signals_from_context()   [Community 29/30]
        │
        ▼
backtest/engine.run_combined_backtest()         [Community 30]  ← motor
        │
        ├─► harness/SignalAdapter    [Community 2]  → SignalMessage
        │                                  │
        │                                  ▼
        │                          risk/governor.GovernorState   [Community 10]
        │                                  │  (RiskGovernorAdapter)
        │                                  ▼
        │                          next_state() / GovernorPool
        │
        └─► integration/mt5_bridge  [Community 7/12]  → MT5Receiver / MT5BacktestRunner
```

## Conexiones sorprendentes (detectadas por graphify)

- `FeatureEnrichmentAdapter` → `DisplacementConfig` / `ZoneConfig` (INFERRED)
  `adapters/feature_enrichment_adapter.py` consume configs de detectores de desplazamiento y zonas.
- `MQL5EAHarnessAdapter` → `HarnessEvent` (INFERRED)
  El adaptador del EA simulado depende del contrato de eventos del harness.
- `EchoAdapter` → `MQL5EAHarnessAdapter` / `WyckoffAdapter` (INFERRED)
  `harness/__main__.py` enlaza el adapter eco con el EA simulado y el adapter Wyckoff.

## Estado de integridad

- Ciclos de import: **ninguno detectado** (grafo acíclico en imports — buena higiene).
- Calidad de extracción: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS.
- Token cost: 0 (extracción puramente AST, sin LLM).

## Cómo ampliar / refrescar

- Grafo fresco al 2026-07-09; tras cambios de código: `graphify update .` (sin costo de API).
- Query interactivo: `graphify query "<pregunta>"` (usa `graphify-out/graph.json`).
- HTML interactivo: `graphify-out/graph.html`.
