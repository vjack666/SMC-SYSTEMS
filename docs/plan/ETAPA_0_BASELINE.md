# ETAPA 0 — BASELINE (Congelar estado actual)

Objetivo: línea base reproducible del sistema ANTES de cualquier cambio.

## Estado al iniciar (2026-07-17)
- HEAD de referencia: commit `104964c` (main).
- Sin tags existentes.
- Hay archivos modificados sin commitear (app_observador/*, data/ml/*, AGENTS.md, agents/*):
  trabajos previos NO incluidos en el baseline hasta decisión explícita.

## Tareas de la etapa
- [ ] T0.1 Crear tag `baseline-2026-07-17` sobre 104964c (REQUERE OK de Ruben; no se crea solo).
- [ ] T0.2 Archivar resultados actuales de backtest en `results/baseline/`:
  - R6.4 (EURUSD/GBPUSD/USDCHF/USDCAD, costos ON, PF negativo — ver METRICS_CANON §0).
  - v2 mtf (7 majors, D1→H4→H1→M15, costos ON, OOS 0.3).
  - A12 (no_session × XAUUSD, PF 1.642 — sobre ablación inválida, ver auditoría forense).
- [ ] T0.3 Snapshot de métricas en `docs/METRICS_CANON.md` marcado como "BASELINE 2026-07-17".
- [ ] T0.4 Documentar configuración actual: símbolos, TFs por motor, COST_BY_SYMBOL
  (solo XAU/EUR/GBP calibrados), semillas, MAX_SIGNALS_PER_VARIANT=3000, displace_gap=6,
  bos_gap=10, RR 1:3, fill next_open.

## Salida
Baseline completamente reproducible.

## Gate de salida
Desde un clon limpio en el tag `baseline-2026-07-17`, los backtests de baseline son
reproducibles y sus números están archivados en results/baseline/. Hasta que no exista el
tag, el baseline de facto = commit 104964c.

## Nota de cumplimiento (Ruben)
La creación del tag y cualquier commit de baseline requiere OK expreso de Ruben y que
CRONOGRAMA_Y_ROADMAP.md + ROADMAP_BIBLIOTECA_Y_APLICACION.md estén al día en el mismo commit.
