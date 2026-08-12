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
