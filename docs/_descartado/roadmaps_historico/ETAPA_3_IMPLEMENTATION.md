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

> **✅ HISTORICAL** — ETAPA 3 completada 2026-07-17. Output: `IMPLEMENTATION_PLAN.md`.

# ETAPA 3 — PLAN DE IMPLEMENTACIÓN (orden por dependencia)

Objetivo: ordenar cambios por dependencia, no por importancia.

## Estado al armar el plan
Tag `baseline-2026-07-17` (c885ac3), main en 8216e15.

## Orden (cadena de dependencia)
```
CR-1  Fuente unica BOS/CHOCH           -> H4, H5, condiciona H17
  ├-> CR-6  Incluir XAUUSD en MTF      (corolario H14; dato ya existe)
  ├-> CR-3  Cap ventana/seed + quitar w0_agents  (H15)
  ├-> CR-4  ML sobre canonico + allowlist        (H17, H18; requiere CR-1)
  ├-> CR-2  POI anclado + Silver Bullet          (H12, H13; lo mas profundo)
  └-> H16   Aplicar DSR/PBO a la grilla           (requiere CR-3)
CR-5  Tests reproducibles + ciclo import + dead code  (H20/H21/H22; paralelo)
```

## Tareas — COMPLETADAS
- [x] PASO 1 CR-1: unificar BOS/CHOCH en fuente única (market_structure canónico).
- [x] PASO 2 CR-6: quitar exclusión XAUUSD en run_bt_v2_mtf.py:16.
- [x] PASO 3 CR-3: cap por ventana/seed, sacar w0_agents (run.py:412,433-435).
- [x] PASO 4 CR-4: dataset_builder apunta a canónico; train.py allowlist (H17/H18).
- [x] PASO 5 CR-2: POI anclado (C05) + módulo Silver Bullet (H12/H13).
- [x] PASO 6 H16: DSR/PBO en grilla (requiere CR-3).
- [x] PASO 7 CR-5: tests sin auto_download, romper ciclo trend_context, dead code (H20/21/22).

Cada paso: UN commit = UN bug, con tests + backtest + comparación baseline tras el cambio.
Revertir si regresión o desvío >5-10% de métricas.

## Salida
IMPLEMENTATION_PLAN.md con pasos, aceptación y riesgo por ítem.

## Gate de salida
Cumplido: orden por dependencia definido. Listo para ETAPA 4 (corrección de bugs).
