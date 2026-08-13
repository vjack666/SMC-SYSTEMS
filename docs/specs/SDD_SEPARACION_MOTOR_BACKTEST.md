# SDD — Separación definitiva MOTOR ↔ BACKTEST (HYP-002, misión de frontera)

**Estado:** TESTED · **Autoridad:** SDD de implementación (cadena AGENTS.md §18 → DECISION_BACKTEST_UNICO → engine → SDD_GOVERNANCE)
**Fecha:** 2026-08-12 · **Ejecutor:** Hermes (autónomo, ORDEN DEL DIRECTOR)
**Alcance:** dejar `engine/` como ÚNICA fuente de decisión; `ict_backtest/` solo feed/reloj/adaptadores/simulación/métricas; auditorías en `research/` consumidoras puras.
**Fuera de alcance (por directiva):** WR/PF/edge, Macro/News, estadística, nuevo Market Replay (es misión posterior, no esta).

---

## 1. DoR (Definition of Ready) — superado por inventario

1. **Objetivo claro:** eliminar la superficie de decisión duplicada en `ict_backtest/` y las dependencias `ict_backtest → lógica decisional` y `engine → ict_backtest`.
2. **Relación con tesis:** AGENTS.md §18 + DECISION_BACKTEST_UNICO (motor = única fuente; backtest desechable).
3. **Comportamiento esperado:** `engine/` no importa `ict_backtest/`; `ict_backtest/` no contiene módulos de decisión (solo shims/reexports de `engine.*` o feed/clock/metrics); auditorías en `research/` pasan sin `ict_backtest` en ruta.
4. **Entradas:** grafo de imports real (audit_motor_backtest_boundary.py + análisis AST manual).
5. **Salidas:** auditor PASSED; `run_sequence_backtest`/`run_sequence_parity` verdes; tests de camino real verdes.
6. **Invariantes:** `engine/` NUNCA importa `ict_backtest/` (AST guard); backtest solo consume motor.
7. **Límites:** NO se toca estadística/edge; NO se crea un segundo motor; NO se modifica semántica de decisión (regresión cero).
8. **Casos negativos:** si un módulo a borrar tiene consumidor vivo inesperado, se detiene y reporta (BLOCKED).
9. **Dato faltante:** N/A (no cambia ingestión de datos).
10. **Criterios de falsación:** el auditor sigue BLOCKED, o `run_sequence_backtest` diverge de baseline.
11. **Criterios de aceptación:** auditor PASS + batería de camino real PASS + prueba de destrucción (`ict_backtest` inaccesible) → motor+auditorías PASS.
12. **Impacto:** `ict_backtest/canonical.py`, `run_backtest.py`, `v2/orchestrator.py` (re-enrutamiento a `engine.*`); creación de `engine/po3.py`, `engine/ote.py`, `engine/dealing_range.compute_zone_class`; shims en `ict_backtest/`.
13. **Prohibiciones:** sin ATR/RSI/EMA; sin gate duro en POI; sin lógica de decisión en `ict_backtest/`.

---

## 2. Inventario real (fuente: imports, no documentación)

### 2.1 Camino VIVO (canónico único)
- `ict_backtest/run_backtest.py::run_sequence_backtest` → `canonical.evaluate_signals` → `engine.*` para decisiones y `ict_backtest.simulator` para resultados.
- `ict_backtest/canonical.py::evaluate_signals` → usa `engine.plan`, `engine.execution`, `engine.poi_anchor`, `engine.rr_by_setup`, `engine.silver_bullet`, `engine.turtle_soup`, `engine.liquidity_internal_external`, `engine.killzone`, `engine.sequence` y `engine.trade_levels`.
- `ict_backtest/v2/orchestrator.py::run_sequence_parity` → consume el camino canónico y los contratos del motor.

### 2.2 Superficies de decisión en `ict_backtest/` (resultado de la migración)
| Módulo | ¿Tiene equivalente en engine? | Consumidores vivos | Decisión |
|---|---|---|---|
| `market_structure.py` | SÍ (`engine.market_structure`) | consumidores de compatibilidad | SHIM |
| `dealing_range_motor.py` | SÍ (`engine.dealing_range_eq`) | consumidores de compatibilidad | SHIM |
| `po3_motor.py` | SÍ (`engine.po3`) | consumidores de compatibilidad | SHIM |
| `setups/ote.py` | SÍ (`engine.ote`) | consumidores de compatibilidad | SHIM |
| `plan_attach/plan_driver/plan_fsm` | SÍ (`engine.plan_*`) | compatibilidad | SHIM |
| `rules.py` | checklist UI | `__init__` | UI puro, fuera del motor canónico |
| `structure.py` | clasificación auxiliar | `__init__` | adaptador/UI, fuera del motor canónico |
| `setups/silver_bullet.py` | SÍ (`engine.silver_bullet`) | canonical (engine) | YA shim (en SHIM_FILES) |
| `setups/turtle_soup.py` | SÍ (`engine.turtle_soup`) | canonical (engine) | YA shim (en SHIM_FILES) |

### 2.3 Legacy y herramientas fuera del camino canónico
- Eliminados por no tener consumidores: `bar_by_bar_engine.py` y el comparador ejecutable anterior `_cmp_bos.py`.
- `setups/breaker_block.py`, `setups/smart_money.py` y `setups/smt_divergence.py` quedan aislados para pruebas/investigación; el auditor impide que el backtest activo los importe.
- `optimize.py` permanece como herramienta de backtest: optimiza parámetros sobre datos históricos y consume el motor para generar decisiones; no es un motor alternativo.

---

## 3. Plan de migración por capas (sin cambio semántico — regresión cero)

### Capa 1 — Infraestructura común a engine
- `engine.market_structure`, `engine.dealing_range_eq`, `engine.po3` y `engine.ote` son las fuentes permanentes.

### Capa 2 — Re-enrutamiento del camino vivo
- `canonical.py`, `run_backtest.py`, `optimize.py` y V2 importan las decisiones desde `engine.*` y la simulación desde `ict_backtest.simulator`.
- La interfaz pública (`ICTSignal`, `evaluate_signals`, `latest_plan`) permanece compatible.

### Capa 3 — Shims explícitos
- `ict_backtest/engine.py` y las superficies de compatibilidad reexportan desde `engine.*` o `ict_backtest.simulator`; no contienen implementación decisional.

### Capa 4 — Eliminar o aislar legacy
- Eliminar módulos sin consumidores que dupliquen el loop o ejecuten datos al importarse.
- Mantener herramientas de backtest y detectores experimentales únicamente fuera del camino canónico y con guardas de importación.

### Capa 5 — Guardas en ambos sentidos
- `engine → ict_backtest`: ya cubierto por `tests/test_architecture_motor_autonomy.py` (AST).
- `ict_backtest → lógica decisional`: cubierto por `scripts/audit_motor_backtest_boundary.py` (DECISION_SURFACE + BACKTEST_DECISION_DEPENDENCY). Tras Capa 2/3, el auditor debe dar PASS.

### Capa 6 — Prueba de destrucción
- Ejecutar auditorías + `run_sequence_backtest` + `run_sequence_parity` con `ict_backtest/` temporalmente inaccesible (sys.path sin él) → motor + auditorías PASS; backtest irrelevante.

---

## 4. Criterios de cierre (Definition of Done)
- `scripts/audit_motor_backtest_boundary.py` → PASS.
- `pytest tests/test_architecture_motor_autonomy.py tests/test_functional_lab.py tests/test_operational_continuity.py tests/test_sequence_persistence.py` → verde.
- `run_sequence_backtest` y `run_sequence_parity` ejecutan sin importar `ict_backtest.market_structure`/`plan_*` (usan engine).
- Prueba de destrucción: motor + auditorías PASS sin `ict_backtest`.
- Documentado: este SDD + informe ejecutivo + deuda real.
- **NO commit/push sin autorización expresa de Ruben (regla #12 del orden).**

### Evidencia de esta ejecución
- `engine/signal.py` es la fuente permanente de `ICTSignal`.
- `engine/trade_levels.py` es la fuente permanente de SL estructural y objetivos de liquidez.
- `ict_backtest/simulator.py` contiene reloj/fill/costos/SL-TP/hold y emisión de datos crudos para diagnóstico.
- `ict_backtest/engine.py` solo conserva compatibilidad de imports y el auditor rechaza implementaciones locales allí.
- `bar_by_bar_engine.py` fue retirado porque duplicaba decisiones y no tenía consumidores.

---

## 5. Deuda documentada (fuera de alcance, no bug)
- `ict_backtest/rules.py` / `structure.py`: checklists de UI; si el observador las usa en vivo, quedan como UI puro (no decisión). Si no, se borran en limpieza posterior.
- Adaptador de feed real (fuera-de-orden/duplicados) sigue pendiente de normalización previa al motor (deuda de M4).
