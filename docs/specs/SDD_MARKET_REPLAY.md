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
