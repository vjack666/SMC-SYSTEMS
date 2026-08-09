> ⚠️ **DOCUMENTO HISTÓRICO (recuperado 2026-08-05 del commit d0a5f20).**
>
> NO es fuente de verdad. La fuente de verdad viviente es:
> `AGENTS.md` + `docs/tesis/` (tesis del trader humano) + `engine/` (motor permanente)
> + `docs/bitacora/bitacora_trabajo.md` (estado real verificado).
>
> Este roadmap describe el estado al 2026-07-21, cuando el trabajo estaba medido
> en el **backtest** (`ict_backtest/`). El motor (`engine/`) se construyó DESPUÉS
> y está en otro punto. Ver `docs/planificacion/INDICE_PLANES.md` y el diff en
> `docs/planificacion/_roadmap_historico/PUNTO_DEL_ROADMAP_2026-08-05.md`.
>
> Recuperado selectivamente (solo hitos/fases/decisiones, SIN código de backtest
> ni libro 13) por petición del trader humano para ubicar el punto actual.

> **✅ HISTORICAL** — ETAPA 0 completada 2026-07-17. Tag creado. Sin acciones pendientes.

# ETAPA 0 — BASELINE (Congelar estado actual)

Objetivo: línea base reproducible del sistema ANTES de cualquier cambio.

## Estado al iniciar (2026-07-17)
- HEAD de referencia original: commit `104964c` (main). Sin tags.
- Había ~60 archivos modificados/sin commitear (docs nuevos, código fuente, datos, borrados
  previos). Todos congelados en commits atómicos C1..C7.

## Tareas de la etapa — COMPLETADAS (2026-07-17)
- [x] T0.1 Tag `baseline-2026-07-17` creado sobre `c885ac3` (REQUIERE OK de Ruben: concedido).
- [x] T0.2 Commits atómicos de congelación:
  - C1 `b2e...` docs de gobierno + auditorías (PLAN_IMPLEMENTACION_ETAPAS, DECISION_LOG,
    ETAPA_0/1, AUDITORIA_COMITE_TECNICO, INFORME_CONVERGENCIA).
  - C2 `9f1e850` código fuente suelto (app_observador, agents, AGENTS).
  - C3 `4555836` datos/ml parquets + model_registry + .atl cache.
  - C4 `8a31941` data/raw parquets.
  - C5 `2738b39` fuente modificado (ict_backtest, legacy, risk, monitoring, scripts, docs).
  - C6 `—` archivos nuevos (tests v2 mtf, bos_table, runner_monitor, docs backtest pro,
    app_observador core/ui, MQL5, data/histdata_tmp).
  - C7 `c885ac3` borrados previos (integration/mt5_bridge, scripts r4_*, monitoring/alerter,
    tests, egg-info).
- [x] T0.3 Resultados actuales de backtest: R6.4 / v2 mtf / A12 ya documentados en
  docs/METRICS_CANON.md y docs/avances/ (no se regeneran; son el estado conocido).
- [x] T0.4 Configuración actual documentada en el informe de convergencia (Fase 3 / matriz).

## Verificación de reproducibilidad
- `ict_backtest/v2/orchestrator.py` EXISTE en el tag (resuelve Falla 1 de la forense:
  el módulo ahora es versionable y reproducible desde clon limpio).
- Único resto sin commitear: `results/ml_pipeline_status.json` (ignorado por .gitignore,
  runtime — fuera del baseline por diseño).

## Salida
Baseline completamente reproducible. Tag `baseline-2026-07-17` = commit `c885ac3`.

## Gate de salida
Desde un clon limpio en el tag `baseline-2026-07-17`, los backtests de baseline son
reproducibles y sus números están archivados en results/baseline/. Hasta que no exista el
tag, el baseline de facto = commit 104964c.

## Nota de cumplimiento (Ruben)
La creación del tag y cualquier commit de baseline requiere OK expreso de Ruben y que
CRONOGRAMA_Y_ROADMAP.md + ROADMAP_BIBLIOTECA_Y_APLICACION.md estén al día en el mismo commit.
