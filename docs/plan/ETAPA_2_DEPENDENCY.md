> **✅ HISTORICAL** — ETAPA 2 completada 2026-07-17. Output: `DEPENDENCY_TREE.md`.

# ETAPA 2 — ÁRBOL DE DEPENDENCIAS (causa raíz)

Objetivo: encontrar causas raíz y encadenamientos. No prioridades.

## Estado al armar el árbol
Tag `baseline-2026-07-17` (c885ac3), main en 8216e15.

## Tareas — COMPLETADAS
- [x] CR-1: dos stacks (signals/detectors vs ict_backtest/market_structure) sin fuente única → H4/H5/H17.
- [x] CR-2: motor simplificado 2 TF sin ancla HTF → H12/H13.
- [x] CR-3: cap por confianza determinístico → H15 (arrastra H16).
- [x] CR-4: ML en stack distinto + allowlist débil → H17/H18 (arrastra H16).
- [x] CR-5: tests auto_download + ciclo import + dead code → H20/H21/H22.
- [x] CR-6: filtro XAUUSD MTF obsoleto (run_bt_v2_mtf.py:16) siendo el dato ya existe.
- [x] Hallazgo nuevo: `signals/pipeline.py:12` importa `detectors` (Stack A USADO en diagnóstico);
  `run_backtest.py:103` usa canónico (Stack B). Bifurcación real confirmada.

## Salida
DEPENDENCY_TREE.md con árbol por componente + 6 causas raíz consolidadas.

## Gate de salida
Cumplido: cada hallazgo tiene causa raíz + encadenamiento. Listo para ETAPA 3.
