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

> **✅ HISTORICAL** — Fases A–D completadas. Phase E cerrada en `ETAPA_DIAGNOSIS_ENGINE_FASE_E.md`.

# Fase D — Migración multi-TF del Backtest Engine (TradeContext v2)

Fecha: 2026-07-18 · Autor: Hermes (bajo dirección de Ruben)

## Diagnóstico de raíz (Ruben, reglas #1–#7)

El backtest no era "malo porque la estrategia era mala". Era un **simulador de
órdenes** con un registro pobre: solo miraba el mercado con un solo ojo. El
`TradeContext` v1 solo traía `htf_bias` + `zone_authority` (1 capa HTF real;
D1 se cargaba pero no se usaba; H1/M5/M1 ausentes). Con un expediente así,
cualquier estadística (Fase E) sería ruido sobre ruido → regla #7: fidelidad
antes que estadísticas.

## Hallazgo clave (auditoría real, no suposición)

El motor YA sabe leer cualquier TF: `engine._build_estructura` arma
`est[tf]={trend,bos,choch,sweep,fvg,ob}` por cada TF cargado. Y
`ict_backtest/v2/context_mtf.py` YA tiene `build_context_stack` /
`snapshot_tf` / `dealing_range_pd` — **closed-only anti look-ahead**, mapeados
1:1 con el schema pedido (bias/structure/premium_discount/liquidity). Estaba
DESHABILITADO (deuda R3.5 / Fase v30 del CAVEAT). La migración es de CABLEO,
no de rewrite.

## Decisiones (aprobadas por Ruben)

- Cadena completa D1/H4/H1/M15/M5/M1 SIEMPRE que exista en disco.
- TF ausente => `available=False`, campos en `MISSING` (regla #4: nada inventado,
  no se copia de otro TF).
- La lógica de DECISIÓN (R7) NO cambia: sigue usando htf→ltf. La cadena extra
  es OBSERVABILIDAD PURA (regla: "sin cambiar la lógica de entrada todavía").
  R1 (PnL idéntico) se preserva.

## Cambios (TDD, una tarea a la vez)

### Fase A — Data Engine (cargar cadena completa)
- `run_sequence_backtest` carga `TF_CHAIN=(D1,H4,H1,M15,M5,M1)` vía
  `load_frames` (recorta por `window_months` antes de features).
- Por señal, arma `market_stack = build_context_stack(ms, t, tfs=TF_CHAIN)`
  (closed-only, anti look-ahead). Lo pasa a `simulate_trade_with_context`.

### Fase B — Market Analyzer (schema por rol)
- `ict_backtest/diagnostics/mtf_context.py` (nuevo): `normalize_mtf_stack`
  traduce el stack a `{tf: MarketContextFrame}` con los campos de Ruben:
  D1 bias/structure/premium_discount · H4 bias/structure/poi · H1 structure/liquidity
  · M15 setup/sweep/displacement/bos/fvg/ob · M5 confirmation/micro_structure
  · M1 execution/entry_quality. Reusa columnas ya existentes; no recalcula.

### Fase C — TradeContext v2
- `trade_context.py`: nuevo `MarketContextFrame` (@frozen) + campo
  `market_context: dict|None` en `TradeContext`. `CONTEXT_VERSION = "ctx-2.0"`.
  v1 sigue válido (market_context=None). Inmutable preservado.

### Fase D — Validación + AUDIT (este documento / script)
- `scripts/fase_d_validate_mtf.py`: corre 6m EURUSD, congela contexts v2,
  emite `contexts.json` + `audit_report.json` (disponibilidad por TF,
  contexts incompletos). Sin estadísticas (regla #7).

### Fase E — StatisticsEngine (PENDIENTE, recién ahora)
- Solo tras validar que el expediente es fiel. `statistics_engine.py` y
  `correlation_engine.py` como módulos independientes (regla de separación de
  Paso 3): consumen `market_context`, responden las preguntas de Ruben
  (¿D1/H4/H1 alineados funcionan mejor? ¿M5 mejora la entrada? ¿M1 ruido?).
  HypothesisEngine solo consume sus salidas. Reporte incluye "qué NO puede
  concluir" (evidencia insuficiente).

## Tests
- `test_fase_d_mtf_context.py`: schema v2, 6 TF presentes, MISSING si ausente.
- `test_fase_d_mtf_wiring.py`: cableo real emite market_stack, congela en v2,
  R1 preservado (PnL no cambia).

## Estado
- Fases A/B/C/D(código) implementadas y 13 tests verdes.
- Fase D(ejecución 6m EURUSD): primer run = 36 trades, **6 TF al 100% disponibilidad,
  0 incompletos**. Pero prueba empírica del call site reveló 2 campos de CONTENIDO
  UNKNOWN (no inventados, pero pedidos): `D1.premium_discount` y `H4.poi`.
  - Cierre (mismo turno): se enchufó `dealing_range_pd` (ya existente en v2/context_mtf)
    para `pd_side` en D1/H4, y `htf_pd_index` (Fase C) para `poi` anclado en H4/H1.
    Reusa código ya escrito (cero nuevo motor), observabilidad pura (no toca R7).
    Re-run 6m en curso para validar contenido real.
- Fase E: bloqueada hasta validar fidelidad del expediente (regla #7).
