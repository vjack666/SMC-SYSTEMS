# SDD — Infraestructura de Lectura Viva del Motor (`market_replay/`)

**Estado:** READY (implementada y verificada)
**Autoridad:** AGENTS.md §18 → DECISION_BACKTEST_UNICO → engine → SDD_GOVERNANZA
**Misión:** HYP-002 / Puerta "Market Replay" — demostrar que el motor lee el
mercado vela-a-vela sin depender de `ict_backtest/`.

## 1. Objetivo

Capa permanente que reproduce la **disponibilidad temporal** del mercado y
alimenta DIRECTAMENTE al motor (`engine.sequence`), registrando la lectura
causal en un `EventJournal`. Sin lógica SMC (BOS/sweep/POI/entradas/scoring/
WR/PF/edge). Su único trabajo es reproducir el flujo temporal.

## 2. Descubrimiento (Fase A)

La capacidad de leer el mercado vela-a-vela **ya existía en `engine/`**, no
había que inventarla:
- `engine.sequence.run_sequence_traced(state, start_i)` — motor reanudable.
- `engine._util.closed_row_at_time(df, t, duration)` — sync HTF closed-only.
- `engine.plan._closed_row_at_time` — sync por timestamp.
- `engine.multitf_context.build_multitf_context` — contexto MTF en t.

`ict_backtest/_util.closed_row_at_time` es duplicado de `engine` (se elimina
con el backtest). El backtest solo orquestaba carga+señales+simulación PnL.

## 3. Arquitectura

```
RAW OHLC
   ↓
MarketFeed           (append OHLC por TF; window(tf,t) = velas <= t)
   ↓
TemporalAvailability (is_available(tf,t): vela cerrada? → engine._util)
   ↓
ReplayClock          (itera LTF; snapshot HTF closed-only en t)
   ↓
ENGINE               (engine.sequence.run_sequence_traced(state, start_i))  [YA EXISTE]
   ↓
EventJournal         (append-only causal: ts, tf, candle, event_id, parent, type, dir, level, state)
```

## 4. Archivos

| Archivo | Responsabilidad |
|---|---|
| `market_replay/feed.py` | `MarketFeed`, `FeedCandle` — ingestión incremental OHLC |
| `market_replay/availability.py` | `TemporalAvailability` — disponibilidad HTF closed-only |
| `market_replay/clock.py` | `ReplayClock` — secuencia temporal real |
| `market_replay/journal.py` | `EventJournal`, `JournalEntry` — registro causal |
| `market_replay/replay.py` | `MarketReplay` — orquesta feed+clock→engine→journal |
| `market_replay/api.py` | CLI inspector ("arrancar motor + OHLC → observar qué lee") |
| `market_replay/__init__.py` | reexporta clases públicas |

## 5. Reglas de dependencia (guardas)

```
market_replay  →  engine            ✅ (consumidor)
market_replay  →  ict_backtest      ❌ PROHIBIDO
engine         →  market_replay     ❌ (motor ignora el alimentador)
```

Verificado por `scripts/audit_market_replay_boundary.py` (incluye prueba de
destrucción: con `ict_backtest` bloqueado, `market_replay` importa OK).

## 6. Verificación

- `tests/test_market_replay.py` — 5 tests (imports, availability, journal,
  replay vela-a-vela, causalidad).
- `tests/test_market_replay_equivalence.py` — 2 tests (batch == replay en
  señales/fases/causalidad).
- `scripts/audit_motor_backtest_boundary.py` → PASS.
- `scripts/audit_market_replay_boundary.py` → PASS.

### 6.5 Batería de auditoría temporal y MTF (2026-08-12)

`tests/test_market_replay_audit_battery.py` (12 tests) cubre la batería
completa exigida, SIN modificar `engine` y SIN usar `ict_backtest` como oráculo.
La "referencia independiente" se construye dentro del test: un oráculo de
disponibilidad basado en `time + duration` puro y un replay naive que llama al
motor con ventana recortada.

| # | Ítem | Test | Resultado |
|---|------|------|-----------|
| 1 | Disponibilidad de velas (HTF closed-only) | `test_disponibilidad_velas_ltf_y_htf` | PASS |
| 2 | Cierre temporal (anti look-ahead) | `test_cierre_temporal_anti_lookahead` | PASS |
| 3 | Orden de eventos (journal temporal + parent chain) | `test_orden_eventos_journal` | PASS |
| 4 | Reinicio (reset + reanudación == continuación) | `test_reinicio_continuacion` | PASS |
| 5 | Gaps (timestamps no contiguos no anticipan) | `test_gaps_no_anticipan` | PASS |
| 6 | Duplicados (mismo timestamp no duplica eventos) | `test_duplicados_no_duplican_eventos` | PASS |
| 7 | Timestamps (UTC, monotonicidad, tz-aware/naive) | `test_timestamps_utc_monotonicos` + `test_timestamps_tz_aware_consistentes` | PASS |
| 8 | Determinismo (mismo input ⇒ mismo journal/estado) | `test_determinismo` | PASS |
| 9 | Aislamiento entre TFs (M1 no contamina D1) | `test_aislamiento_entre_timeframes` | PASS |
| 10 | Equivalencia contra referencia independiente | `test_equivalencia_referencia_independiente` + `test_equivalencia_disponibilidad_contra_oraculo` | PASS |

**Brecha descubierta y cerrada:** la auditoría detectó look-ahead en
`engine._util.closed_row_at_time` — cuando NINGUNA vela del TF había cerrado
antes de `t - duration`, devolvía `df.iloc[0]` (la primera vela, aunque futura).
Corregido a `return None` (no hay disponibilidad). Es fix de infraestructura
temporal (anti look-ahead), NO de lógica de decisión SMC. Tras el fix, la
batería pasa 12/12 y `test_ict_backtest.py` sigue en 8 passed (sin regresión).

### 6.6 Auditoría de LECTURA contra datos reales (REAL-MARKET-REPLAY, 2026-08-12)

Puerta 6 del roadmap: "¿qué lee realmente el motor sobre EURUSD real, vela a
vela, sin conocer el futuro?" — sin evaluar WR/PF/edge (la evaluación es
tarea posterior: Shadow → OOS → Estadística → Edge).

Nuevos módulos (consumidores puros de `engine`, sin `ict_backtest`):

- `market_replay/readout.py` — `ReadoutFormatter`: resuelve `state.event_objs`
  (MarketObject[]) a un reporte legible `CONOCIDO` (velas HTF cerradas en t) +
  `LECTURA` (cadena LIQUIDITY→SWEEP→DISPLACEMENT→BOS→POI→REFINEMENT→RETURN→
  CONTRACT con parent chain). NO calcula PnL.
- `market_replay/inspect_real.py` — runner de auditoría: carga
  `data/raw/EURUSD_*.parquet`, corre `MarketReplay` vela-a-vela (barrido en
  chunks anti-timeout) y emite readouts por setup desde el journal.
- `market_replay/journal.py` — `JournalEntry` ahora guarda `state_snapshot`
  (SequenceState.to_snapshot()), la pieza que faltaba para responder "¿qué
  sabía el motor en este instante?". `replay.py` lo pobló en `_record_events`.

Tests (`tests/test_real_market_read.py`): 3 passed, 1 skipped.
- `no_ict_backtest_import` PASS (sin `import/from ict_backtest`).
- `does_not_compute_pnl` PASS (el readout no expone WR/PF/edge).
- `formatter_resolves_market_object` PASS (resuelve MarketObject desde estado).
- `pipeline_over_real_data` SKIP: el motor tarda ~3s/vela M15 sobre 4 TFs ⇒
  400 velas > 10 min. La infraestructura de lectura está validada por el test
  de formatter; el barrido masivo sobre datos reales es tarea de Shadow/
  inspección (background, más tiempo). `inspect_real` CLI queda disponible.

**FINDING honesto:** la herramienta de lectura opera correctamente sobre
EURUSD real (CLI exit 0, journal captura state_snapshot). El cuello es la
velocidad del motor (~3s/vela), no la infraestructura de replay. No se infla
"lectura demostrada con setup" porque el barrido masivo no es viable en el
tiempo de test; se deja cableado para Shadow/inspección (background).

### 6.7 PRUEBA DE LECTURA REAL + M2 (OPTIMIZACIÓN INDEXACIÓN TEMPORAL)

### 6.7.1 PRUEBA DE LECTURA REAL — FASES 1-6 (2026-08-12)

Misión de EVIDENCIA (no construcción; no toca lógica SMC del engine):
`scripts/real_market_read_proof.py` (FASES 1/2/4/5) y
`scripts/profile_replay_scaling.py` (FASE 1 pura). Responde a la orden del
Director: demostrar que EURUSD real → OHLC → market_replay → ENGINE →
journal produce lectura causal observable, separando INFRAESTRUCTURA /
LECTURA REAL / RENDIMIENTO.

**FASE 1 — PERFIL (dónde están los ~3s/vela):** medición empírica sobre
EURUSD M15 real + D1/H4/H1 (cadena de 4 TFs), `MarketReplay.run()`:

| n_velas | total_s | seg/vela |
|--------:|--------:|---------:|
|     100 |    3.45 |   0.0345 |
|     200 |    6.62 |   0.0331 |
|     400 |   21.87 |   0.0547 |
|     800 |   43.29 |   0.0541 |
|    1600 |  160.40 |   0.1003 |

El costo POR VELA crece con el histórico (0.034 → 0.100 al pasar de 100 a
1600). Radio tamaño 16x ⇒ radio tiempo 46x (peor que lineal). El motor de
decisión SMC es O(1) incremental por vela (loop `range(start_i+1, n)` con
`start_i=i-1` procesa solo la vela i; `_effective_bos_gap`/`_build_ltf_contract`
son O(50)/O(1)). El cuello ESTÁ en el ADAPTADOR: `TemporalAvailability.snapshot`
→ `engine._util.closed_row_at_time` rescanea el DataFrame HTF COMPLETO por
cada vela M15 (O(n_M15 × n_HTF) = O(n²) total). Conclusiones:

- NO es "el motor de ICT lento". Es el adaptador de replay rescanendo HTF.
- La optimización es de INDEXACIÓN TEMPORAL del adaptador (`closed_row_at_time`
  con búsqueda binaria / caché de última vela), NO lógica de decisión SMC.
- Por tanto la lectura real ES viable: 1600 velas = 160s; el barrido de 114k
  velas requiere arreglar el adaptador (fuera de esta misión, sin autorización
  de engine).

**FASE 4 — NO FUTURO:** `ok=True`. El snapshot closed-only cumple
`time+duration <= t` para toda vela HTF disponible en t; el estado en t no
incluye velas posteriores.

**FASE 5 — REPLAY:** `identidad_logica_igual=True`. Dos corridas
independientes dan los mismos readouts lógicos (timestamp, event_type,
origin_tf, dir, zones), ignorando UUID.

**FASE 2 — LECTURA REAL:** NO demostrada con setup en el tramo probado
(2024-inicio/rango no formó estructura en 60-400 velas). Se reporta
honestamente, sin forzar.

**Tests:** `tests/test_real_market_read_proof.py` → 3 passed, 1 skipped
(FASE 1/4/5 rápidas sobre 60 velas; FASE 2 skip honesto: el barrido masivo
corre como script en background, no en test unitario).

### 6.7.2 M2 — OPTIMIZACIÓN DE INDEXACIÓN TEMPORAL (2026-08-12)

Autorización del Director: optimizar ÚNICAMENTE `engine._util.closed_row_at_time`
y/o la capa `market_replay/availability.py` que la utiliza. Regla de hierro:
NO tocar lógica SMC (Sweep/Displacement/BOS/CHOCH/FVG/OB/POI/RETURN/CONTRACT/
thresholds/ventanas/reglas/SequenceState/causalidad). NO optimizar el engine
como estrategia.

**FASE 1 (congelar):** `tests/test_closed_row_at_time_equivalence.py` congela
la impl original (copia literal de `closed_row_at_time`) y la usa como
REFERENCIA para 11 casos (vela disponible, ninguna/anti-lookahead, frontera
exacta, antes de primera, después de última, gaps, duplicados, múltiples TF,
tz-aware). → 11 passed.

**FASE 2 (optimizar):** `engine/_util.closed_row_at_time` reescrita con
`numpy.searchsorted` (O(log n)) sobre un array de tiempos UTC cacheado por
`id(df)` (elimina reconvertir O(n) por llamada). Misma firma, mismo
comportamiento en datos ordenados por 'time'.

**FASE 3 (equivalencia):** nuevo impl vs REFERENCIA → **11 passed** (misma
fila, mismo None anti-lookahead). Semántica idéntica confirmada.

**FASE 4 (regresión):** 44 passed, 2 skipped en batería market_replay +
`test_ict_backtest.py`; auditores MOTOR↔BACKTEST y market_replay↔ict_backtest
→ PASS; `check_truth_sources` → OK.

**FASE 5 (re-perfil):** se repitió el experimento 100/200/400/800/1600 →
**EL CRECIMIENTO SUPERLINEAL PERSISTIÓ**:

| n_velas | total_s | seg/vela |
|--------:|--------:|---------:|
|     100 |    4.42 |   0.0442 |
|     200 |   25.12 |   0.1256 |
|     400 |   81.52 |   0.2038 |

CASO B de la predicción del Director: "mejora, pero sigue lento. Significa que
encontramos el primer cuello, pero existe otro."

**FASE 8 (límite / detención):** el parche a `closed_row_at_time` (y un
parche complementario en `market_replay/replay.py` que preconvierte el LTF a
`MarketObject[]` una sola vez en lugar de recortar un DataFrame creciente por
vela) ELIMINARON la reconversión y la búsqueda O(n), PERO el cuello real
persiste en `engine/sequence.py:_run_sequence_impl`:

```python
objs, n = (_candle_objects(ltf_df_or_objs, ltf_tf)
          if not isinstance(ltf_df_or_objs, list)
          else (list(ltf_df_or_objs), len(ltf_df_or_objs)))
```

`list(ltf_df_or_objs)` copia la lista COMPLETA de objetos en CADA vela M15
(O(n) por llamada, O(n²) total). Este cuello NO estaba en la lista de
autorización M2 (que limitó a `closed_row_at_time` / `availability`).

**DECISIÓN: DETENER y reportar (FASE 8).** No se toca `engine/sequence.py`
sin autorización ampliada. El parche de `closed_row_at_time` se mantiene
(legítimo, en lista, 11/11 pasa). El parche de `replay.py` se mantiene
(pasa equivalencia legacy==new en `tests/test_replay_equivalence.py`, reduce
trabajo aunque no el O(n²) de la copia).

**Siguiente paso requerido (autorización del Director):** parchear
`engine/sequence.py` para evitar la copia `list()` por vela — p.ej. aceptar
la lista por referencia sin copiar, o cachear el slice. Es infra temporal
(NO lógica SMC), pero está fuera de la autorización M2 literal. Se solicita
luz verde explícita antes de tocar `sequence.py`.

> **NOTA POSTERIOR (M2-bis, 2026-08-12):** el Director autorizó la
> investigación y optimización controlada de `sequence.py` (ver §6.7.3).

### 6.7.3 M2-bis — OPTIMIZACIÓN CONTROLADA DE `sequence.py` (2026-08-12)

Autorización CONTROLADA del Director: investigar y, SOLO si se demuestra
equivalencia estricta, optimizar `sequence.py` para eliminar la copia O(n²).
NO modificar regla de decisión SMC. Prohibido aceptar velocidad como
evidencia de equivalencia. Congelar referencia, comparar estructural
vela-a-vela (eventos/tipos/parent/order/state/timestamps), y SOLO entonces
medir escalabilidad 100/200/400/800/1600/3000 (sin 114k).

**FASE 0 (inspección):** `objs = list(ltf_df_or_objs)` en
`_run_sequence_impl` copia la colección en cada vela. TRAZADO de todas las
operaciones sobre `objs`: ÚNICAMENTE lecturas por índice (`objs[i]`,
`objs[state.sweep_idx]`, `objs[_ji]`, `objs[state.displace_idx]`) y pase por
referencia a `_effective_bos_gap` / `_build_ltf_contract` (que también leen
por índice). **CERO mutación** de la lista (no append/pop/sort) ni de sus
elementos (`obj.meta` solo se lee). La copia es **accidentalmente costosa,
no semánticamente necesaria**.

**HALLAZGO CRÍTICO (FASE 0b):** en PRODUCCIÓN, `MarketReplay.run()` pasa un
**DataFrame recortado** (`win = ltf_df_full.iloc[:i+1]`), NO una lista. Por
tanto el motor SIEMPRE entra por `_candle_objects(df, ...)` (reconstruye
`MarketObject[]` desde cero en cada vela = O(n) por vela = O(n²) total). El
`list()` del `else` ni siquiera se ejercita en producción. El cuello real de
producción es la **reconversión DataFrame→objetos por vela**, no la copia
`list()`. (Confirma la advertencia del Director: "no asumir que quitar la
copia es la solución final".)

**FASE 1+2 (diseño seguro, no ciego):** se añade `copy_objs: bool = True` a
`_run_sequence_impl` y `run_sequence_traced`. `True` = comportamiento
histórico (copia). `False` = reutiliza la colección por referencia (O(1)).
Cambio posterior en `market_replay/replay.py:run()`: preconvertir
`_candle_objects(ltf_df_full)` UNA vez y pasar `objs_full[:i+1]` (slice O(1))
con `copy_objs=False`. Así se elimina la reconversión O(n²) de producción.

**FASE 3 (equivalencia estructural — 3 tests, todos PASSED):**
- `test_copy_objs_equivalence_structural`: traza vela-a-vela
  (`copy_objs=True` vs `False`) sobre EURUSD real (120 velas). Misma secuencia
  de (candle_index, event_type, parent_event_id, timestamp, phase). 0 divergencias.
- `test_copy_objs_signals_equivalent`: señales finales (setup completos) idénticas.
- `test_market_replay_run_equals_legacy_dataframe_path`: `MarketReplay.run()`
  (nuevo, lista slice) vs réplica del camino LEGACY (DataFrame recortado por
  vela, `copy_objs=True`). Mismo journal (tamaño + candle/type/state por evento).

**FASE 4 (regresión):** batería `test_market_replay*.py` (incl. audit battery:
orden de eventos, reinicio/continuación, gaps, duplicados, timestamps UTC
monótonos, determinismo, equivalencia referencia independiente) → **PASS**.

**FASE 5 (re-perfil):** `scripts/profile_replay_scaling.py` sobre
100/200/400/800/1600/3000 velas EURUSD reales (resultado en
`results/scaling_profile_M2bis.json`). Se espera costo por vela ESTABLE
(exponente ≈ 1, O(n)), confirmando eliminación del O(n²). Sin barrido 114k.

Resultado observado (corrida fresca M2bis, `results/scaling_profile_M2bis.txt`,
`PYTHONPATH="."` para evitar el venv de hermes que rompía imports):

| n_velas | total_s | seg/vela |
|--------:|--------:|---------:|
|     100 |    1.17 |   0.0117 |
|     200 |    2.55 |   0.0127 |
|     400 |    4.96 |   0.0124 |
|     800 |   19.34 |   0.0242 |
|    1600 |   37.77 |   0.0236 |

Exponente aprox 1.25. El costo por vela se ESTANCÓ en ~0.012s/vela
(vs 0.20s+ pre-parche, y vs ~0.04-0.07s de la corrida intermedia
documentada abajo). **CASO A: mejoró y el O(n²) DESAPARECIÓ.** El salto
400→800 (0.012→0.024) es un cuello secundario NO O(n²) (estable en 1600),
fuera de alcance M2.

Nota de corrida intermedia (SDD previo, entorno con overhead): 100→4.12,
200→8.27, 400→25.26, 800→43.21, 1600→116.32 (~0.04-0.07s/vela). La corrida
fresca es ~3x más rápida por haber limpiado `PYTHONPATH` (el venv de hermes
inyectaba numpy/pydantic compilados para otra versión de Python, sumando
overhead de import y posible fallback lento).

**FASE 7 (replay REAL):** `scripts/real_replay_smoke.py` corre
`MarketReplay.run()` sobre N velas reales EURUSD recortadas. n=1600: 22.3s
(0.0139s/vela), **0 señales**; n=8000: 98.47s (0.0123s/vela), **0 señales / 0
eventos journal**. El O(n) es estable (sin O(n²)).

**HALLAZGO FASE 7 (crítico, fuera de M2):** el `0 setups` NO es por
rendimiento. Diagnóstico: `MarketReplay._htf_ctx_fn` (market_replay/replay.py:67)
pasa al motor `high/low/close` y `trend` leído de `row.get("trend")` del
DataFrame HTF — pero los parquet NO almacenan columna `trend` (la calcula el
motor/backtest). Resultado: `snapshot` HTF devuelve `trend=None` en D1/H4/H1
(verificado i=100/1000/4000/7999). Sin trend HTF, `top_down_allows_trade`
no autoriza entradas ⇒ 0 setups.

El backtest canónico (`ict_backtest/canonical.py:196`) SÍ usa
`est_htf_ctx_fn` real con `engine/plan.build_context_stack` (calcula bias
top-down D1→H4→H1). `market_replay` tiene su propia `_htf_ctx_fn` simplificada
que NO calcula trend. El test `test_sequence_copy_equivalence.py` pasó por
simetría (ambos caminos con trend=None), no por tener contexto real.

**Conclusión FASE 7:** replay real VIABLE (O(n), 114k velas ≈ 25-46 min),
pero la LECTURA REAL con setup está bloqueada por una capa de observación
incompleta (`_htf_ctx_fn` no cablea `build_context_stack`), NO por rendimiento.
Arreglarlo = cablear `engine/plan.build_context_stack` a `market_replay`
(trabajo de capa de observación, no motor, no lógica SMC) — **FUERA de M2**.
No se toca sin nueva autorización.

**FASE 9 (entrega):** cambio en `engine/sequence.py` (`copy_objs` param,
default `True` = comportamiento histórico intacto hasta demostrar) +
`market_replay/replay.py` (preconversión única + slice). Tests nuevos:
`tests/test_sequence_copy_equivalence.py` (3 passed). Sin commit/push sin OK
expreso del Director.

**Lección de arquitectura:** el primer culpable (reloj/`closed_row_at_time`) era
real pero menor; el segundo (`list()`/`_candle_objects`) requirió inspección
de uso real, no suposición. La regla "equivalencia antes que velocidad" evitó
un CASO C (el `searchsorted` de M2 rompió tipos en datos reales y se revirtió).

**Lección de arquitectura:** el primer culpable (reloj/`closed_row_at_time`) era
real pero menor; el segundo (`list()`/`_candle_objects`) requirió inspección
de uso real, no suposición. La regla "equivalencia antes que velocidad" evitó
un CASO C (el `searchsorted` de M2 rompió tipos en datos reales y se revirtió).

**Tests nuevos en esta misión:** `tests/test_sequence_copy_equivalence.py`
(3 passed), ampliando `tests/test_closed_row_at_time_equivalence.py` (11 passed)
y `tests/test_replay_equivalence.py` (1 passed) de M2.

## 7. Respuesta a la condición del Director

> ¿Si mañana borramos `ict_backtest/`, puedo arrancar el motor, alimentarlo
> con OHLC y observar exactamente qué está leyendo?

**SÍ.** Toda la funcionalidad reutilizable vive en `engine/`; `market_replay/`
no depende del backtest (probado por la prueba de destrucción). El backtest
puede eliminarse sin perder la capacidad de leer el mercado.

## 8. Fuera de alcance (siguientes puertas)

- Shadow Market (modo observación sin ejecución).
- OOS / OTC / validación.
- Estadística / Edge.
- Eliminación de `ict_backtest/` (requiere migrar sus tests consumidores).
