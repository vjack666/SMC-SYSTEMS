# DEUDA DE INFRAESTRUCTURA — Frontera MOTOR ↔ INFRA (NO-FIX)

**Fecha:** 2026-08-13 · **Registrado por:** CEO (Hermes, modo consejo) · **Estado:** DEUDA ABIERTA, **NO ARREGLAR SIN AUTORIZACIÓN EXPLÍCITA DEL DIRECTOR**
**Origen:** Sesión CEO 2026-08-13 — FASE B (auditoría de infraestructura). Hallazgo del padre `424b060a` reconfirmado y precisado con evidencia de código + datos.

---

## 1. RESUMEN (una frase)

La infraestructura de observación/replay **no reproduce el contexto HTF que el motor necesita**: entrega `trend="RANGING"` forzado en todos los TF superiores porque los parquet crudos no traen `trend`, mientras que el backtest canónico SÍ lo computa desde el OHLC.

Esto **no demuestra que el motor esté mal**. Demuestra que la **frontera MOTOR ↔ INFRA** tiene una deuda de integración.

---

## 2. EVIDENCIA (verificada contra código y datos reales, 2026-08-13)

### 2.1 El motor espera `trend` del contexto HTF
- `engine/multitf_context.py:69` — `extract_htf_layer` lee `layer.get("trend", "RANGING")`.
- `engine/plan.py:49` — `_trend_of` cae a `"RANGING"` si la fila no trae `trend`.
- `engine/sequence.py:358` — `run_sequence` consume `trend` de `est_htf`.

### 2.2 MarketReplay ENTREGA trend degradado
- `market_replay/replay.py:67-85` — `_htf_ctx_fn` hace `row.get("trend", "RANGING")`.
- `market_replay/availability.py:76-89` — `snapshot()` delega en `closed_row_at_time` y devuelve la **fila del parquet tal cual** (solo OHLC).
- `market_replay/feed.py:21` — `OHLC_COLS = (time, open, high, low, close)` → el feed **nunca** trae `trend`.

### 2.3 Los datos reales de replay son OHLC puro (sin trend)
- `data/raw/EURUSD_*.parquet` (D1/H4/H1/M15/M5/M1) → columnas = `['time','open','high','low','close']`, **`has_trend = False`** (verificado con Python314 el 2026-08-13).
- Por tanto `row.get("trend", "RANGING")` → **siempre `"RANGING"`** en la práctica.

### 2.4 El backtest canónico SÍ entrega trend real (asimetría)
- `ict_backtest/canonical.py:196-208` — `est_htf_ctx_fn` llama `build_multitf_context(ms, ...)` donde `ms = {tf: detect_market_structure(df) ...}` (`canonical.py:187`). `detect_market_structure` **computa `trend` desde el OHLC**.
- Resultado: mismo `engine.run_sequence`, alimentado por el backtest canónico, recibe contexto HTF fiel → setups válidos.

### 2.5 Consecuencia observada (citada por el Director)
- Replay sobre datos reales → `0 setups` (contexto HTF degradado → `top_down_allows_trade` rechaza).
- Esto es **deuda de integración de la frontera**, no falla del motor.

---

## 3. CLASIFICACIÓN (SDD_GOVERNANCE §4 / §9 — regla de no-invención)

| Campo | Valor |
|-------|-------|
| Tipo | Defecto de INTEGRACIÓN en capa de infraestructura (MarketReplay / feed / availability) |
| Componente afectado | `market_replay/replay.py`, `market_replay/availability.py`, `market_replay/feed.py` |
| Motor afectado | NO (el motor solo consume lo que le pasan; comportamiento correcto dado su entrada) |
| Severidad | CRÍTICA para el objetivo "replay fiel" (bloquea observación realista), pero **no** para la verificación semántica del motor (FASE A usa el backtest canónico, que SÍ entrega trend real) |
| Linaje IDENTITY/LINK/CAUSALITY | No comprometido (el linaje se fija en el motor desde OHLC; el defecto es solo el contexto HTF de entrada) |

---

## 4. DECISIÓN DE TRATAMIENTO (orden del Director 2026-08-13)

> "Registra como deuda separada los defectos encontrados en las capas de infraestructura/replay. **No los arregles salvo autorización específica**."

- ✅ Registrado aquí como deuda separada y rastreable.
- ⛔ **NO se modifica** `market_replay/`, `availability.py`, `feed.py`, ni `engine/` en esta sesión.
- ⛔ No se crea aún el SDD de infraestructura (se difiere hasta auditar la frontera completa y convocar al Consejo de nuevo).

---

## 5. QUÉ FALTA AUDITAR ANTES DEL SDD DE INFRAESTRUCTURA (FASE B pendiente)

1. **Cobertura de la frontera completa**, no solo `trend`:
   - ¿`sweep_up/down` y `pd_zones` llegan correctos a través de MarketReplay? (hoy `replay.py:80-84` solo pasa `trend/high/low/close`; **NO** pasa `sweep_up/down` ni `pd_zones` → el motor top-down recibe menos contexto que vía backtest canónico).
   - ¿La sincronización temporal (closed-only) es idéntica a `closed_row_at_time` del motor? (sí por delegación, pero falta batería adversarial sobre replay).
2. **Decidir destino del loop operativo vivo** (`orchestration/`, `paper_trading/`, `monitoring/`, `adapters/`): ¿cablearlo a la Ley Fundamental o archivarlo? Hoy está marcado HISTÓRICO en `TRUTH_MATRIX.md`.
3. **Solo entonces** escribir el SDD de infraestructura a partir de evidencia real (no de abstracción previa).

---

## 6. PRINCIPIO RECTOR PARA EL FUTURO SDD (del Director)

> "No: 'funciona más rápido'. Sino: 'funciona igual, demostrablemente, y ahora además funciona más rápido'."

El SDD de infraestructura debe exigir que cualquier optimización/cambio en la capa de transporte (replay, feed, availability) demuestre **equivalencia estructural vela-a-vela** contra el backtest canónico antes de aceptarse (patrón M2-bis ya aplicado en `424b060a`).

---

## 7. TRAZABILIDAD

- Hallazgo padre: commit `424b060a` ("M2: eliminar O(n^2) de infra temporal en replay") — ancestro de HEAD.
- Código citado: `market_replay/replay.py:67-85`, `market_replay/availability.py:76-89`, `market_replay/feed.py:21`, `ict_backtest/canonical.py:187-208`, `engine/multitf_context.py:69`, `engine/plan.py:49`.
- Datos citados: `data/raw/EURUSD_{D1,H4,H1,M15,M5,M1}.parquet` (OHLC puro, sin `trend`).
- Sesión: CEO 2026-08-13, FASE B.
