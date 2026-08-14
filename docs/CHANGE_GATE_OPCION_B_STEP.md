# Change Gate MAYOR — Opción B: API `step(i)` en engine/sequence.py

**Autorizado por:** Director (fallo 2026-08-14)
**Scope:** API incremental de una vela, índices absolutos, estado persistente, O(N).
**Estado:** ✅ Implementada (una sola lógica). ⏸️ Nivel 2 bloqueado por COLGADO en
`build_multitf_context(closed_index=...)` sobre datos REALES (Nivel 1 pasó en sintético).

## Implementación (Change Gate Mayor, mínimo)
- `engine/sequence.py`:
  - `_run_sequence_impl` acepta `single_step: bool = False`. El loop pasa de
    `for i in range(start_i+1, n)` a `for i in range(start_i+1, (start_i+2) if single_step else n)`.
    Con `single_step=True` y `start_i=i-1`, procesa SOLO la vela i (1 iteración).
  - `class SequenceRunner`: mantiene `objs` (lista COMPLETA, índices absolutos),
    `state`, `cfg`, `est_htf_ctx_fn`, `htf`. Método `step(i)` llama
    `_run_sequence_impl(objs, ..., start_i=i-1, single_step=True, initial_state=self.state,
    copy_objs=False)` y acumula señales/phase/expedientes/estado. Método `run_all`
    itera `step(i)` (conveniencia batch).
  - `run_sequence_traced` REFACTORIZADO para usar `SequenceRunner` internamente
    (`runner.run_all(start_i)`). GARANTÍA DE UNA SOLA LÓGICA: batch y streaming
    comparten idéntico `_run_sequence_impl`. Cero segunda implementación semántica.
- `market_replay/replay.py`:
  - `run()` crea UN `SequenceRunner(objs_full COMPLETO, ...)` y llama `runner.step(i)`
    por vela (O(N) total, índices absolutos intactos, SIN sublista `objs[:i+1]`).
  - Elimina el anti-patrón de sublista documentado en FUNCTIONAL_REPLAY_CONTRACT §6.

## Condiciones del Director — cumplimiento
1. ✅ `step(i)` procesa SOLO la vela i (single_step=True, 1 iteración del loop).
2. ✅ Índices absolutos: `objs` es la lista COMPLETA; `i` es el índice real (no 0 por sublista).
   `origin_index/confirmed_index/sweep_id/...` viajan con el objeto real.
3. ✅ No cambia la máquina de estados: `step(i)` ES el cuerpo del loop (misma función).
4. ✅ Batch queda como referencia (`run_sequence_traced` usa `SequenceRunner.run_all`).

## NIVEL 1 — Contexto ORIGINAL == OPTIMIZADO (PASS ✅, ver CHANGE_GATE_OPCION3_HTF.md)
Opción 3 (precompute índice HTF) es semánticamente neutra (12/12 velas en sintético).

## NIVEL 2 — BATCH == STREAM (PASS ✅ tras aislar bug de script)
Con la corrección de `load_frames` (recortar TFs HTF a ventana acotada, como hace
el feed del replay) y pasar `objs` como lista de MarketObject (no DataFrame) a
`SequenceRunner`, Nivel 2 PASÓ:
- `_exp_nivel2_step.py` N=300 reales: BATCH(0) == STREAM(0). ✅
- `_exp_nivel2b_setup.py` sintético (1 setup): BATCH(1) == STREAM(1), mismos
  índices (sweep_at/displace_at/bos_at/entry_at/direction). Los UUID de event_ids
  difieren (efímeros por corrida) pero la SEMÁNTICA CAUSAL es idéntica. ✅
- `_exp_nivel2c_replay.py` N=300 reales: REPLAY(0) == BATCH(0) en 24s (O(N)).
  El replay vela-a-vela con Opción B + Opción 3 es O(N) y produce los MISMOS
  setups que el batch fiel. ✅

**Conclusión Opción B:** `step(i)` es la MISMA máquina de estados que
`run_sequence_traced` (una sola implementación, índices absolutos intactos,
procesa SOLO la vela i, O(N) total). Cumple las 5 condiciones del Director.

## Estado de Gates (Change Gate Opcion B)
```
Nivel 1: Contexto original == contexto optimizado   ✅ (Opción 3, 12/12 velas)
Nivel 2: REPLAY(t) == LIVE(t) (batch ref)           ✅ (0 setups, misma semántica)
Nivel 3: Setup causal reproducible                  ⏸️ (0 setups en N=300;
                                                    requiere ventana mayor)
```

## Hallazgos durante la implementación
1. `engine/sequence.py` tenía em-dashes (U+2014) en docstrings y un docstring
   duplicado (`"""` `"` suelto) que rompían la compilación. Corregido (em-dash→
   guion ASCII, docstring duplicado eliminado). El motor ahora compila limpio.
2. `load_frames` de los scripts dejaba D1/H4/H1 SIN recortar => `detect_market_structure`
   sobre miles de velas => O(n^2)/colgado. Corregido recortando todos los TF.
3. `SequenceRunner` espera `objs` como lista de MarketObject; pasar DataFrame
   da `IndexError` (list(DataFrame) = columnas). Corregido convirtiendo con
   `_candle_objects` antes del runner.
4. El replay (MarketReplay.run) ahora usa UN `SequenceRunner` con `objs_full`
   COMPLETO y `step(i)` por vela => O(N), índices absolutos, SIN sublista
   `objs[:i+1]` (anti-patrón §6 superado).

## Regla mantenida
No afirmar PASS sin evidencia. Backtest ≠ online. Opción B es una sola lógica
(cumplido). Opción 3 es neutra (Nivel 1). El criterio de éxito NO es "aparezcan
setups" sino REPLAY(t)==LIVE(t) vela por vela (Nivel 2 cumple con 0 setups).
No modificar engine para fabricar setups.

