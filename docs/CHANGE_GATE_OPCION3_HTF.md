# Change Gate OPCIÓN 3 — Precomputación de índice HTF (Contexto O(n))

**Autorizado por:** Director (fallo 2026-08-14)
**Scope:** optimización de índice HTF cerrado en `engine/`, semánticamente neutra.
**Estado:** ✅ Contexto implementado y NEUTRO (Nivel 1 PASS). ⏸️ Replay sigue O(n²) por el MOTOR (ver bloqueo).

## Implementación (Change Gate mínimo)
- `engine/plan.py`:
  - `snapshot_tf(..., closed_idx=None)`: si `closed_idx` dado, usa `df.iloc[closed_idx]`
    en vez de `_closed_row_at_time(df, t)`. Mismo procesamiento de fila (`_bias_from_frame`, etc.).
  - `dealing_range_pd(..., closed_idx=None)`: si `closed_idx` dado, usa `d1.iloc[closed_idx]`
    en vez de `_closed_row_at_time`. Misma ventana lookback/eq/range.
  - `build_context_stack(..., closed_index=None)`: propaga `closed_index` a `snapshot_tf`
    y `dealing_range_pd`. Retrocompatible (sin índice = comportamiento original).
- `engine/multitf_context.py`:
  - `build_multitf_context(..., closed_index=None)`: propaga a `build_context_stack`.
- `market_replay/replay.py`:
  - `_htf_ctx_fn` pasa `closed_index={tf: idx_by_i[tf][i]}` a `build_multitf_context`
    (NO construye dict de fila cruda — cumple invariante 5).
  - `_precompute_htf_index` calcula `idx_by_i[tf]` O(n) total (dos punteros).
  - `est_htf_ctx_fn` usa `tfs=("D1","H4","H1")` (solo HTF, evita O(n²) de ltf_structure_at en M15).

## NIVEL 1 — Contexto ORIGINAL == OPTIMIZADO (PASS ✅)
`scripts/_exp_nivel1_contexto.py` sobre dataset sintético (12 velas M15):
- ORIGINAL: `build_multitf_context(ms, t)` (sin índice)
- OPTIMIZADO: `build_multitf_context(ms, t, closed_index=precompute)` (índice O(n))
- Resultado: **12/12 velas idénticas** en trend/bos_dir/choch/fvg/ob/swing/liquidity/pd.
- Conclusión: Opción 3 es SEMANTICAMENTE NEUTRA. Cumple invariante del Director.

## NIVEL 2 — REPLAY == BATCH (BLOQUEADO ⏸️ por O(n²) del MOTOR)
`scripts/_exp_nivel2_replay.py` N=300 M15 reales: el replay se COLGA (timeout 200s)
ANTES de llegar a la vela 50. No es el contexto (Nivel 1 pasó): es el MOTOR.

**Causa raíz del bloqueo:** `run_sequence_traced(win, start_i=i-1)` reprocesa
`range(start_i+1, len(win))` en CADA llamada del loop del replay. Con `win=objs_full[:i+1]`,
procesa 1 vela por llamada (O(n) por llamada, O(n²) total por el loop de N llamadas
si cada una reprocesa desde start_i). El contexto O(n) NO elimina este cuello porque
el cuello está en el MOTOR, no en el contexto HTF.

**Opción A (sublista `objs[:i+1]`):** procesa 1 vela por llamada → O(n) total.
PERO el contrato FUNCTIONAL_REPLAY_CONTRACT §6 lo documenta como anti-patrón:
"cortar con df.iloc[k+1:] REBASA las posiciones y ROMPE la paridad" (índices absolutos
del estado vs sublista). En dataset sintético funcionó (Fase 2), pero en datos reales
el estado puede desalinearse.

**Opción B (API `step(i)` en engine):** el motor procesa SOLO la vela i dado el estado,
aceptando df COMPLETO (índices absolutos coherentes). Requiere Change Gate MAYOR
(toca `run_sequence_traced` / `_run_sequence_impl` para exponer step). Es neutro
semánticamente (no cambia decisión), pero es cambio de arquitectura de invocación.

## Decisión requerida (Director)
Para replay O(n) vela-a-vela SIN romper paridad de índices:
- ¿Autorizo Change Gate MAYOR para API `step(i)` en engine/ (Opción B)?
- ¿O acepto la sublista `objs[:i+1]` (Opción A) y valido paridad con
  audit_restart_parity sobre datos reales?

Hasta resolver esto, el replay es O(n²) y solo corre en ventana chica (N≤300 con timeout).
La Opción 3 de contexto QUEDA implementada y validada como neutra; el bloqueo es del motor.

## Regla mantenida
No afirmar PASS sin evidencia. Backtest ≠ online. Optimización debe ser semánticamente
neutra vela por vela (Nivel 1 cumple; Nivel 2 pendiente por O(n²) del motor).
No modificar engine para fabricar setups.
