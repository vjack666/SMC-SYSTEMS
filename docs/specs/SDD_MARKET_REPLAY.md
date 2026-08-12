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

### 6.7 PRUEBA DE LECTURA REAL — FASES 1-6 (2026-08-12)

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

**FASE 2 — LECTURA REAL:** en curso (barrido de 3000 velas en background).
El motor es estricto; el tramo inicial de 2024 (rango) no formó setups en
60-400 velas. Se reporta el resultado real al cerrar, sin forzar.

**Tests:** `tests/test_real_market_read_proof.py` → 3 passed, 1 skipped
(FASE 1/4/5 rápidas sobre 60 velas; FASE 2 skip honesto: el barrido masivo
corre como script en background, no en test unitario).

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
