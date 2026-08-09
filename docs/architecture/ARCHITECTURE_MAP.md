# ARCHITECTURE_MAP.md — Cartografía del repositorio SMC-SYSTEMS

> **FASE 1 de la propuesta de arquitectura (2026-08-09).** Solo inventario y
> responsabilidades. **NO se movió ni renombró nada.** Relevado con evidencia de
> dependencias reales (`grep` de imports), no de memoria.
>
> Propósito: servir de base para diseñar la arquitectura objetivo (6 mundos) y una
> migración por fases. Regla de oro: cada carpeta debe responder UNA pregunta.

## 1. Inventario de primer nivel (raíz)

| Carpeta/Archivo | .py | Responsabilidad real (hoy) | Consumido por | Estado |
|-----------------|----:|----------------------------|---------------|--------|
| `engine/` | 29 | Motor causal ICT (bias, BOS, liquidez, POI, sequence, execution, trade mgmt, volumen) | ict_backtest, app_observador, tests, adapters, agents | VIVO (núcleo) |
| `ict_backtest/` | 79 | Backtest canónico (consumidor puro del motor) | tests, scripts | VIVO (núcleo) |
| `detectors/` | 13 | Detectores (displacement, fvg, ob, bos, choch, fib, gaps) | engine/bos, ict_backtest, agents | VIVO (cableado) |
| `ml/` | 13 | Pipeline ML, inferencia, feature importance | ict_backtest/diagnostics, signals, monitoring, risk | VIVO (cableado) |
| `signals/` | 3 | Señales (pipeline, po3) | ict_backtest/po3_motor | VIVO (cableado) |
| `features/` | 2 | Features engine | ict_backtest/data_feed | VIVO (cableado) |
| `adapters/` | 5 | Puente strategy/risk/signals/wyckoff | agents, strategy, risk | VIVO (cableado) |
| `strategy/` | 4 | Confluence scorer, live_grid, scalping | adapters, agents, ict_backtest, app_observador | VIVO (cableado) |
| `risk/` | 6 | Sizer, governor, threshold | adapters, agents, app_observador, ict_backtest | VIVO (cableado) |
| `indicators/` | 2 | Indicadores (¿sospechoso vs Ley cero-indicadores?) | adapters, signals | REVISAR (ver §5) |
| `monitoring/` | 7 | Alerter, dashboard, drift, equity | ml, app | VIVO |
| `integration/` | 8 | mt5_bridge | runtime broker | VIVO |
| `orchestration/` | 1 | Coordinación de agentes | — | VIVO |
| `governance/` | 5 | (es `agents/governance/`, ver abajo) | — | VIVO |
| `agents/` | 7 | Agentes de análisis (ict, wyckoff, structure, decision, orchestrator) + `governance/` | adapters, detectors, strategy, risk | VIVO |
| `app_observador/` | 36 | App UI que consume el motor | runtime humano | VIVO |
| `MQL5/` | 0 | Bridges MT5 (binarios .ex5/.mq5) | broker | VIVO |
| `data/` | 3 | Datos (raw, ml, exports, manifests pendiente) | engine, ict_backtest, features | VIVO |
| `docs/` | 0 | Conocimiento (SDD, tesis, lab, _archivo, _descartado) | humanos | VIVO |
| `results/` | 1 | Salidas de backtest/experimentos (con `_archive/`) | humanos | VIVO |
| `scripts/` | 199 | Herramientas (con `_legacy/`) | operación | VIVO |
| `tests/` | 174 | Verificación | CI | VIVO |
| `knowledge/` | 0 | Personalidad/IA (kos, learnings, theories) | agentes | VIVO |
| `mcps/` | 0 | MCP servers (context7, engram) — IA | agentes | VIVO |
| `models/` | 0 | quality_filter (MLOps) | ml | VIVO |
| `paper_trading/` | 4 | Simulación (funnel) | funnel | VIVO |
| `harness/` | 0 | (legacy, ver §4) | — | LEGACY |
| `geometry_lab/` | 1 | Lab de geometría (experimento) | research futuro | EXPERIMENTO |
| `bin/` | 0 | spec del proyecto | build | VIVO |
| `openspec/` | 0 | Specs | humanos | VIVO |
| `src/` | 0 | (vacío tras mover `_legacy_data` a legacy) | — | VACÍO |
| `legacy/` | 29 | Código muerto del repo (no confundir con `legacy_smc_backup` del disco) | — | LEGACY (en repo) |
| `logs/`, `graphify-out/`, `__pycache__/` | 0 | Generados/cache | — | IGNORADO |

Archivos sueltos en raíz: `conftest.py` (test config), `regime.py`, `trend_context.py`
(usados por adapters/features/ict_backtest), `run_app.py` (launcher de app_observador).

## 2. Grafo de dependencias (quién importa a quién, fuera de sí mismo)

```
engine        -> detectors
ict_backtest   -> engine, detectors, ml, signals
detectors      -> ict_backtest
features       -> (nadie externo a ict_backtest/data_feed)
adapters       -> agents, detectors, indicators, risk, signals
strategy       -> risk
risk           -> (interno)
signals        -> agents, detectors, ict_backtest, indicators
ml             -> agents, features, governance, ict_backtest, monitoring, risk, signals
indicators     -> (interno)
monitoring     -> (interno)
integration    -> (interno)
orchestration  -> (interno)
governance     -> (interno, solo MD)
agents         -> detectors
```

Observación: `detectors` importa `ict_backtest` (el consumidor importa al backtest) —
es una dependencia inversa menor que conviene revisar en FASE 3. `ml` importa `governance`
(ruido: probablemente un test references). `indicators` existe con 2 módulos y es candidato
a revisar contra la Ley cero-indicadores.

## 3. Cumplimiento de la Ley Fundamental

- `engine/` NO importa `ict_backtest/` (confirmado por grep de imports reales: 0 hits).
  Los matches en engine/ son comentarios/docstrings que dicen "NUNCA importa ict_backtest".
- `ict_backtest/` importa `engine/` (consumidor puro). ✅
- **Veredicto: Ley Fundamental CUMPLE en el código.** El riesgo es `detectors -> ict_backtest`.

## 4. Marcadores de legacy / experimento / vacío

- **LEGACY en repo** (`legacy/`, 29 .py): código muerto dentro del repo. Debe salir a
  `legacy_smc_backup` (disco) o purgarse — hoy vive en el repo y ensucia el árbol.
- **LEGACY carpetas**: `harness/` (solo README), `scripts/_legacy/`.
- **EXPERIMENTO**: `geometry_lab/`, `docs/lab/`, `data/exports/`. No hay aún estructura
  uniforme `EXP-NNN/` (tu propuesta de `research/experiments/EXP-071/...`).
- **DESCARTADO** (reversible): `docs/_archivo/`, `docs/_descartado/`, `results/_archive/`.
- **VACÍO**: `src/` (quedó vacío tras mover `_legacy_data`; candidato a eliminar o a ser
  el hogar de `engine/` en migración futura — FASE 2+).

## 5. Mapeo a la propuesta "6 mundos" (tu dibujo)

| Tu mundo | ¿Dónde está hoy? | Veredicto |
|----------|------------------|-----------|
| `docs/` (CONOCIMIENTO) | `docs/` ya existe ✅ | Encaja. Añadir `docs/architecture/` (FASE 2). |
| `src/` (PRODUCTO) | `engine/`, `detectors/`, `features/`, `adapters/` sueltos en raíz | Parcial. Tu regla: **NO mover `engine/` aún** (riesgo imports). Dejar `engine/` en raíz. |
| `backtest/` (EXPERIM. HIST.) | `ict_backtest/` + `results/` + `data/ml/` | Parcial. `ict_backtest/` ya es el backtest; renombrar a `backtest/` es FASE 3. |
| `research/` (LAB) | `geometry_lab/`, `docs/lab/` dispersos | **FALTA** crear `research/{hypotheses,experiments,protocols,studies,archive}`. Alta prioridad. |
| `data/` (DATOS) | `data/` existe (raw, ml, exports) | Encaja. Añadir `data/manifests/` (FASE 2). |
| `results/` (EVIDENCIA) | `results/` existe (con `_archive`) | Encaja. Aplicar regla de IDs (`EXP-071`, `BT-2026-001`). |
| `runtime/` (EJECUCIÓN) | `app_observador/` + `MQL5/` + `integration/` sueltos | Parcial. Agrupar en `runtime/{observer,mql5,integration}` es FASE 3. |
| `scripts/` (HERRAMIENTAS) | `scripts/` ya existe ✅ | Encaja. |
| `tests/` (VERIFICACIÓN) | `tests/` ya existe ✅ | Encaja. |
| `agents/` (ANÁLISIS+GOB) | `agents/` tiene `analysis/` implícito + `governance/` | **Mejorar**: separar `agents/analysis/`, `agents/orchestration/`, `agents/governance/` (FASE 3). |

## 6. Señales de alerta (para FASE 2/3, no para mover hoy)

1. `legacy/` (29 .py) vive EN el repo → debe ir a `legacy_smc_backup` (disco) o purgarse.
2. `indicators/` (2 .py) existe → revisar contra Ley cero-indicadores (¿es legítimo o sospechoso?).
3. `detectors -> ict_backtest` → dependencia inversa; revisar en FASE 3.
4. `research/` no existe → el laboratorio (EXP-NNN, falsación) está disperso. Crear en FASE 2.
5. `src/` vacío → eliminar o decidir su rol en migración arquitectónica futura.
6. `data/manifests/` no existe → añadir para reproducibilidad (tu regla de oro).
7. `results/` sin IDs uniformes → aplicar regla `EXP-/BT-/VAL-` al crecer.

## 7. Conclusión de cartografía

El repo tiene **estructura de crecimiento sólida pero sin contrato de carpetas**. Lo que
falta no es mover archivos, es: (a) `docs/architecture/` con DIRECTORY_CONTRACT +
DEPENDENCY_RULES, (b) crear `research/` uniforme, (c) sacar `legacy/` del repo, (d) regla
de manifests en `data/`, (e) guardrail automático (FASE 4). `engine/` y la separación
motor/backtest ya son correctas y NO se tocan.

> Siguiente paso propuesto (FASE 2): crear `docs/architecture/ARCHITECTURE.md`,
> `DIRECTORY_CONTRACT.md`, `DEPENDENCY_RULES.md` y el guardrail de carpetas. Sin mover nada.
