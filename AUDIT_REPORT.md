# Auditoría Exhaustiva — SMC Successor

> **Fecha**: 2026-07-03
> **Propósito**: Verificar alineación entre roadmap, documentación y código real.
> **Método**: Revisión de código fuente, documentación, harness, tests y git history.

## Acciones Realizadas

Basado en esta auditoría se ejecutaron las siguientes correcciones:

| Acción | Archivo | Detalle |
|--------|---------|---------|
| ✅ Eliminado | `docs/AGENT_COMPLETION_PROTOCOL.md` | Meta-protocolo obsoleto |
| ✅ Eliminado | `docs/ML_DATASET_SPEC.md` | Especificación de dataset v4, reemplazada por código actual |
| ✅ Eliminado | `docs/MULTI_SYMBOL_ML_AUDIT.md` | Auditoría ML antigua, reemplazada por AUDIT_REPORT.md |
| ✅ Eliminado | `docs/TRADING_MODEL_SPEC.md` | Spec de 653 lines desactualizada |
| ✅ Reescribir | `docs/AGENT_ARCHITECTURE.md` | Bugs #1-#3 ya fixeados, data flow corregido, gaps documentados |
| ✅ Reescribir | `harness/README.md` | 10 adapters reales, file tree correcto, tabla actualizada |
| ✅ Reescribir | `COMPLETION_REPORT.md` | Agregadas fases F4-F16 |
| ✅ Reescribir | `MT5_INTEGRATION_REPORT.md` | Paths corregidos, diagrama actualizado |
| ✅ Fix | `adapters/__init__.py` | Export faltante de `MQL5EAHarnessAdapter` |

---

## Resumen Ejecutivo

| Stream | Fases | Rating |
|--------|-------|--------|
| **MT5 Integration (F1-F8)** | 7/8 completas | ⚠️ 1 missing (F8) |
| **Quant Audit (F9-F16)** | 5/8 completas | ⚠️ 3 con gaps significativos |
| **Documentación** | Desactualizada | ❌ README stale, doc paths incorrectos |
| **Harness/Adapters** | 10 registrados, 4 documentados | ❌ Discrepancia mayor |
| **Repo state** | Refactor a medio aplicar | ❌ Working directory sucio |

---

## 1. MT5 Integration Stream (F1-F8)

### F1 — Project Audit
- **Estado**: ⚠️ **Partial**
- **Evidencia**: `scripts/audit_problems.py` (188 lines, 6 tests), findings en `docs/AGENT_ARCHITECTURE.md` (8 findings: 3 HIGH, 1 MED, 4 LOW)
- **Falta**: No existe un audit report formal consolidado. Los hallazgos están dispersos.

### F2 — Research
- **Estado**: ✅ **Complete**
- **Evidencia**: 7 documentos en `docs/` + `MT5_INTEGRATION_REPORT.md` (234 lines) con análisis de conectividad, datos, pipeline, paper/live trading gaps.

### F3 — Target Architecture
- **Estado**: ✅ **Complete** (discrepancia menor)
- **Evidencia**: Diagramas de arquitectura en `MT5_INTEGRATION_REPORT.md` y `docs/AGENT_ARCHITECTURE.md`. La estructura del código coincide.
- **Discrepancia**: Diagrama referencia `data/mt5/connector.py` pero el connector real está en `_data_legacy.py`. Path incorrecto en el diagrama.

### F4 — Data Contracts
- **Estado**: ✅ **Complete**
- **Evidencia**: `integration/mt5_bridge/schema.py` — 7 contratos (SignalAction, OrderType, SignalMessage, TradeResultCode, TradeResult, AccountStatus, Heartbeat) con type hints, serialización JSON y dataclasses.

### F5 — Bridge Module
- **Estado**: ✅ **Complete**
- **Evidencia**: 7 archivos en `integration/mt5_bridge/` con implementaciones reales. ZeroMQ implementado (PUSH/PULL/PUB). Ningún stub.
- **Bug menor**: `Exporter._send_zeromq()` captura `JSONDecodeError` donde nunca ocurriría (es serialización, no deserialización).

### F6 — MQL5 EA
- **Estado**: ✅ **Complete**
- **Evidencia**: 6 archivos MQL5 + `.ex5` compilado. SignalReceiver, OrderManager, JSONParser, AccountMonitor con implementación completa.
- **Bug menor**: `SignalReceiver.Poll()` pierde el primer archivo — llama `FileFindNext()` antes de procesar el resultado de `FileFindFirst()`.

### F7 — Backtest Validation
- **Estado**: ✅ **Complete**
- **Evidencia**: `backtest/validation/` (runner, comparator, report generator) + `orchestration/backtest_validation_graph.py` (564 lines, LangGraph con 7 nodos, routing condicional).

### F8 — Deployment Guide
- **Estado**: ❌ **Missing**
- **Evidencia**: Solo existe guía de instalación del EA MQL5. **No hay** deployment guide para el engine Python, VPS, Docker, systemd, environment variables, ni recovery procedures.

---

## 2. Quant Audit Stream (F9-F16)

### F9 — Robustez Experimento E
- **Estado**: ❌ **Fail**
- **Reclamado**: Validación estadística (Monte Carlo, bootstrap, confidence intervals)
- **Real**: Solo unit tests. **Cero** validación estadística de resultados. No hay simulated annealing, bootstrap, ni tests de significancia.

### F10 — Wyckoff + Stochastic Exhaustion
- **Estado**: ⚠️ **Partial** — Wyckoff ✅, Stochastic ❌
- **Wyckoff**: Completo (304 lines, 12 fases/patrones, alineado con `docs/WYCKOFF_RULEBOOK.md` de 319 lines)
- **Stochastic Exhaustion**: **No existe**. El indicador "stochastic" no aparece en ningún archivo del código. Usa volume-ratio/range-based detection, no estocástico.

### F11 — ML Expansion + Confluence Scoring
- **Estado**: ✅ **Complete** (gap menor)
- **Confluence Scoring**: Real en `signals/pipeline.py` — 6 filtros sumados, configurable via `ScalpingConfig`.
- **ML Pipeline**: Completo — `train.py`, `trainer.py`, `dataset_builder.py`, `validator.py`, `walk_forward.py`.
- **Gap**: Columna `agent_decision_ml_probability` 100% NaN en datasets (el orchestrator no recibe ML probability durante dataset building).

### F12 — Parameter Tuning + Documentación
- **Estado**: ❌ **Fail** — Documentación ✅, Tuning ❌
- **Documentación**: Excelente — 7 docs detallados.
- **Tuning**: **Cero**. No hay Optuna, Hyperopt, GridSearch ni histórico de trials. Todos los hyperparams son hardcoded (`n_estimators=220, max_depth=4, learning_rate=0.05`). El mismo `docs/AGENT_ARCHITECTURE.md` admite: "Confidence levels are NOT tuned."

### F13 — Robust Validation
- **Estado**: ❌ **Fail** — Walk-forward ✅, métodos avanzados ❌
- **Reclamado**: Purged KFold, bootstrap, CVaR, DSR, PBO
- **Real**: `ml/walk_forward.py` (276 lines) con TimeSeriesSplit y walk-forward real. Pero **ninguno** de los métodos específicos está implementado:
  - ❌ PurgedKFold — usa TimeSeriesSplit sin purge gap
  - ❌ Bootstrap — no existe
  - ❌ CVaR — no se computa
  - ❌ Drawdown Duration — no se tracking
  - ❌ DSR (Deflated Sharpe Ratio) — no existe
  - ❌ PBO (Probability of Backtest Overfitting) — no existe

### F14 — Feature Enrichment
- **Estado**: ✅ **Complete**
- **Evidencia**: Detectors reales (BOS, CHOCH, FVG, OB, displacement, zones, trend) + `features/engine.py` (298 lines, 30+ features).
- **Bug fix confirmado**: `detectors/__init__.py` ahora exporta `detect_displacement` y `compute_zones`. Pipeline las llama. Docs están stale (dicen que no están conectadas).
- **Ausencia**: No hay "inducements" explícitos ni "interaction features".

### F15 — Production Monitoring
- **Estado**: ✅ **Complete**
- **Evidencia**: 7 archivos — drift_detector (PSI), alerter (UUID + persistencia), equity_telemetry (Sharpe/Sortino/Calmar), dashboard, performance_tracker, harness_adapter, config. Ningún stub.

### F16 — Governance & Automation
- **Estado**: ✅ **Complete**
- **Evidencia**: 5 archivos — model_registry (versionado + delta), retraining_scheduler (trigger por trade count + Sharpe degradation), auto_report_generator (multi-sección), harness_adapter, config. Ningún stub.

---

## 3. Documentación vs Realidad

### `harness/README.md` — Stale

| Lo que dice | Realidad |
|---|---|
| 4 adapters (echo, signal, risk, backtest) | **10 adapters registrados** en `__main__.py` |
| File tree con 6 fixtures | **12 fixtures** existentes |
| File tree con 3 escenarios | **12 escenarios** existentes |
| "backtest: All scenarios pass" | **No existe ningún escenario** para backtest |
| `benchmarks/`, `golden_tests/`, `datasets/` con contenido | Solo tienen `__init__.py` — vacíos |

### `docs/AGENT_ARCHITECTURE.md` — Parcialmente stale

- **HIGH #1** (displacement no exportado): ✅ YA FIX - `detectors/__init__.py` exporta `detect_displacement` y `DisplacementConfig`
- **HIGH #2** (zones no exportado): ✅ YA FIX - `detectors/__init__.py` exporta `compute_zones` y `ZoneConfig`
- **HIGH #3** (displacement/zones no llamados en pipeline): ✅ YA FIX - pipeline.py los llama en `build_scalping_context()`
- **El documento no refleja estos fixes** — los enumera como bugs activos

### `MT5_INTEGRATION_REPORT.md` — Path incorrecto

- Diagrama referencia `smc_successor/data/mt5/connector.py` — ruta que ya no existe tras el flatten refactor.

---

## 4. Harness & Adapters — Hallazgos

| Hallazgo | Gravedad |
|---|---|
| **Backtest adapter no tiene scenarios** — README claim falso | 🔴 HIGH |
| **README documenta 4/10 adapters** | 🔴 HIGH |
| **6 módulos sin tests** (mt5_bridge, mt5_ea, monitoring, governance, orchestration, trend_context) | 🟡 MED |
| **`adapters/__init__.py` no exporta `MQL5EAHarnessAdapter`** — import directo en `__main__.py` | 🟢 LOW |
| **feature_enrichment harness tarda 19s** (sin datos aislados de test) | 🟢 LOW |
| **mt5_bridge adapter arranca bridge real en import** — puede colgar full run | 🟡 MED |
| **2 test files requieren datos reales** (test_ml_dataset, test_ml_trainer) | 🟢 LOW |

---

## 5. Estado del Repo

| Aspecto | Estado |
|---|---|
| **Último commit** | `b3e51d3` — flatten refactor (2026-07-02) |
| **Working directory** | Sucio — ~100 archivos modificados/eliminados/untracked |
| **smc_successor/ old** | Staged for deletion (D) |
| **Archivos en raíz** | Untracked (??) — esperando commit |
| **Test files** | Modified (M) — imports actualizados |

El refactor de flattening está **a medio aplicar**: los archivos viejos están staged para borrar y los nuevos están sin trackear. Tests modificados pero sin commit.

---

## 6. Discrepancias Críticas (Prioritarias)

1. **F8 (Deployment Guide) no existe** — sin deployment guide no hay go-live posible
2. **Backtest adapter sin scenarios** — el README miente al decir que pasa
3. **README documenta 4 de 10 adapters** — desactualización mayor
4. **F9/F12/F13 no cumplen lo reclamado** — falta validación estadística, tuning, y métodos robustos
5. **F10 (Stochastic Exhaustion) no implementado** — Wyckoff sí, stochastic no
6. **`docs/AGENT_ARCHITECTURE.md` enumera bugs ya fixeados** — confunde
7. **Repo sucio con flattening a medio aplicar** — riesgo de merge conflicts

---

## 7. Recomendaciones

### Inmediatas
1. **Commitear el flatten refactor** — estabilizar el working tree
2. **Actualizar `harness/README.md`** — reflejar los 10 adapters reales
3. **Actualizar `docs/AGENT_ARCHITECTURE.md`** — marcar bugs #1-#3 como resueltos
4. **Crear escenario YAML para backtest** o remover el adapter del README

### Corto plazo
5. **F8 (Deployment Guide)** — crear guía de deploy: VPS, systemd, variables de entorno, recovery
6. **F10 (Stochastic Exhaustion)** — implementar o renombrar la fase
7. **Agregar tests** para los 6 módulos sin cobertura
8. **F12 (Parameter Tuning)** — integrar Optuna/Hyperopt

### Mediano plazo
9. **F13 (Robust Validation)** — implementar PurgedKFold, CVaR, DSR, PBO
10. **F9 (Estadísticas)** — bootstrap de métricas, confidence intervals
11. **Fix SignalReceiver.Poll()** — no perder el primer archivo
12. **Fix catch tipo en exporter.py** — JSONDecodeError no aplica en serialización

---

*Generado por auditoría automática el 2026-07-03. Basado en revisión de ~80 archivos del código fuente.*
