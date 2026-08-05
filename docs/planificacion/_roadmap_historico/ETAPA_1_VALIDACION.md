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

> **✅ HISTORICAL** — ETAPA 1 completada 2026-07-17. Gate pasado. Output: `VALIDACION_DE_HALLAZGOS.md`.

# ETAPA 1 — VALIDACIÓN DE HALLAZGOS (sin modificar código)

Objetivo: demostrar que cada hallazgo realmente existe, con repro paso a paso.
NO se corrige nada en esta etapa.

## Metodología por hallazgo (clasificado A en el informe de convergencia)
Para cada bug: reproducir → medir impacto → demostrar evidencia → indicar archivos afectados.
Formato de entrada en VALIDACION_DE_HALLAZGOS.md:
- ID · Componente · Pasos de repro · Salida medible · Archivo:línea · Conclusión

## Estado al validar
Tag `baseline-2026-07-17` (commit `c885ac3`), main en `ff95230`.

## Tareas — COMPLETADAS
- [x] H3/H14: v2 versionado → RESUELTO (módulo en tag). XAUUSD M15 → EXISTE el parquet (descargado
  hoy); queda validar si el runner MTF lo incluye (ETAPA 2).
- [x] H4 BOS duplicado → `detectors/bos.py:90-91` vs `market_structure.py:157-160`.
- [x] H5 CHOCH duplicado → `detectors/choch.py:14-24` vs `market_structure.py:166-176`.
- [x] H12 POI no anclado → `coverage.py:44-47` (missing) / `:71` (partial).
- [x] H13 Silver Bullet no modelado → ausencia de módulo SB en `ict_backtest/v2/`.
- [x] H15 cap por confianza + w0_agents no-op → `run.py:64,412,433-435` (síntoma 13/21 idénticas).
- [x] H16 sin DSR/PBO en grilla → `stats_validator.py:83,101` no aplicados en `run.py`.
- [x] H17 train/serve skew → `dataset_builder.py:14,234` (legacy) vs `run_backtest.py:103` (canonical).
- [x] H18 features "todo numérico" → `train.py:311-314`.
- [x] H20 tests no terminan + auto-download → pytest >600s; `dataset_builder.py:146-161`.
- [x] H21 ciclo import trend_context → `trend_context.py` ↔ `signals`/`data`.
- [x] H22 dead code → `engine.py:160,229` (`_coerce_ts` duplicada); `strategy_mtf.py:101-103` no-op.

## Correcciones a la forense (halladas al validar)
- H14 (XAUUSD M15 ausente): YA EXISTE el parquet. Falla 4 de datos resuelta por descarga de hoy.
- H3 (v2 no versionado): YA RESUELTO por commits de la forense (Falla 1). Módulo en el tag.

## Salida
VALIDACION_DE_HALLAZGOS.md con una entrada por ID, cada una con repro + archivo:línea + salida
medible. Sin código modificado.

## Gate de salida
Cumplido: todos los hallazgos A tienen repro paso a paso. Listo para ETAPA 2.
