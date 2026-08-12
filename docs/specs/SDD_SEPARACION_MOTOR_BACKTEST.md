# SDD — Separación definitiva MOTOR ↔ BACKTEST (HYP-002, misión de frontera)

**Estado:** READY · **Autoridad:** SDD de implementación (cadena AGENTS.md §18 → DECISION_BACKTEST_UNICO → engine → SDD_GOVERNANCE)
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

### 2.1 Camino VIVO (canónico único, consume motor + duplicados)
- `ict_backtest/run_backtest.py::run_sequence_backtest` → `canonical.evaluate_signals`.
- `ict_backtest/canonical.py::evaluate_signals` → YA usa `engine.plan`, `engine.execution`, `engine.poi_anchor`, `engine.rr_by_setup`, `engine.silver_bullet`, `engine.turtle_soup`, `engine.liquidity_internal_external`, `engine.killzone`, `engine.sequence`.
  PERO TAMBIÉN importa duplicados de `ict_backtest/`:
  - `ict_backtest.market_structure.detect_market_structure`
  - `ict_backtest.dealing_range_motor.compute_zone_class`
  - `ict_backtest.po3_motor.compute_po3_complete`
  - `ict_backtest.setups.ote` (`is_ote_entry`, `flag_ote`)
  - `ict_backtest.plan_attach` / `plan_driver` / `plan_fsm` (capa plan legacy)
  - `ict_backtest.rules`, `ict_backtest.structure` (solo `__init__`)
- `ict_backtest/v2/orchestrator.py::run_sequence_parity` → consume `run_backtest` + `market_structure` + `strategy_legacy`.

### 2.2 Superficies de decisión en `ict_backtest/` (flagueadas por el auditor)
| Módulo | ¿Tiene equivalente en engine? | Consumidores vivos | Decisión |
|---|---|---|---|
| `market_structure.py` | SÍ (`engine.bos.detect_market_structure`) | canonical, run_backtest, optimize, plot, v2/orch, setups/ote, _cmp_bos, _diag | MIGRAR a engine + shim |
| `dealing_range_motor.py` | PARCIAL (`engine.dealing_range`) | canonical | MIGRAR compute_zone_class a engine + shim |
| `po3_motor.py` | NO | canonical | MIGRAR a `engine/po3.py` + shim |
| `setups/ote.py` | NO | canonical | MIGRAR a `engine/ote.py` + shim |
| `plan_attach/plan_driver/plan_fsm` | SÍ (`engine.plan`) | run_backtest, canonical(no) | REDIRIGIR a engine + shim o BORRAR |
| `rules.py` | checklist UI | solo `__init__` | DEJAR como UI puro o BORRAR |
| `structure.py` | `engine.bos` cubre | `__init__`, `_smoke` | REDIRIGIR/BORRAR |
| `setups/silver_bullet.py` | SÍ (`engine.silver_bullet`) | canonical (engine) | YA shim (en SHIM_FILES) |
| `setups/turtle_soup.py` | SÍ (`engine.turtle_soup`) | canonical (engine) | YA shim (en SHIM_FILES) |

### 2.3 Muertos (0 consumidores → BORRAR)
`bar_by_bar_engine.py`, `setups/breaker_block.py`, `setups/smart_money.py`, `setups/smt_divergence.py`, `_cmp_bos.py`, `_diag_signals.py`, `optimize.py`.

---

## 3. Plan de migración por capas (sin cambio semántico — regresión cero)

### Capa 1 — Infraestructura común a engine
- `engine/bos.detect_market_structure` ya existe → el shim `ict_backtest/market_structure.py` reexporta devolviendo `.frame` (misma firma DataFrame que hoy).
- Crear `engine/dealing_range.compute_zone_class` (mover de `dealing_range_motor`).
- Crear `engine/po3.py` (`compute_po3_complete`, `Po3MotorConfig`).
- Crear `engine/ote.py` (`is_ote_entry`, `flag_ote`).

### Capa 2 — Re-enrutar el camino vivo a engine
- `canonical.py`: cambiar imports `ict_backtest.market_structure` → `engine.bos`, `ict_backtest.dealing_range_motor` → `engine.dealing_range`, `ict_backtest.po3_motor` → `engine.po3`, `ict_backtest.setups.ote` → `engine.ote`, `ict_backtest.plan_*` → `engine.plan` (o borrar si no usados en runtime).
- `run_backtest.py` / `v2/orchestrator.py`: eliminar imports de `market_structure`, `plan_driver`, `plan_fsm` (usar engine vía canonical).
- Interfaz PÚBLICA idéntica (`ICTSignal`, `evaluate_signals`, `latest_plan`) → observador sigue igual.

### Capa 3 — Shims explícitos
- `ict_backtest/market_structure.py`, `dealing_range_motor.py`, `po3_motor.py`, `setups/ote.py` → shims `from engine.X import Y` (sin lógica).
- Añadir estos a `SHIM_FILES` en `scripts/audit_motor_backtest_boundary.py`.
- `plan_attach/plan_driver/plan_fsm`: si tras Capa 2 nadie los llama en runtime, BORRAR.

### Capa 4 — Eliminar muertos
- Borrar los 7 módulos de §2.3.

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

---

## 5. Deuda documentada (fuera de alcance, no bug)
- `ict_backtest/rules.py` / `structure.py`: checklists de UI; si el observador las usa en vivo, quedan como UI puro (no decisión). Si no, se borran en limpieza posterior.
- Adaptador de feed real (fuera-de-orden/duplicados) sigue pendiente de normalización previa al motor (deuda de M4).
