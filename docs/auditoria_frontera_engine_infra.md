# AUDITORÍA DE FRONTERA — ENGINE ↔ INFRA/REPLAY (Camino 3, solo descubrimiento)

**Fecha:** 2026-08-13 · **Modo:** DESCUBRIR / MEDIR / DOCUMENTAR / ENTENDER. **NO-FIX.**
**Contrato:** no se modifica `engine/`, `ict_backtest/`, `MarketReplay`, ni contratos.
No se agrega ningún campo. No se programa. Solo se documenta el contrato real vs lo entregado.

---

## 0. Contratos en juego (lectura del código real)

### A. Lo que el motor ESPERA (consumidor: `run_sequence` / `run_sequence_traced`)
`engine/sequence.py:729-739` reduce el contexto vía `extract_htf_layer(_ctx, htf)`.
`extract_htf_layer` (`engine/multitf_context.py:55-73`) entrega un dict con:
- `trend` (sequence.py:735,358)
- `sweep_up` / `sweep_down` (sequence.py:147-149 implícito; leídos en `_htf_has_poi`/búsqueda de liquidez)
- `pd_zones` (sequence.py:381/409-413, anotación POI Fase C)

Además, el motor lee de la capa HTF (vía `extract_htf_layer` / `build_context_stack`):
- `_htf_has_poi` (sequence.py:387-402) lee `fvg_bullish/ob_bullish` o `fvg_bearish/ob_bearish` de `est_htf`.
- `top_down_allows_trade` (sequence.py:754-765) consume el **MultiTFContext completo** (D1→H4→H1) para la cascada.

### B. Lo que entrega el BACKTEST CANÓNICO (`ict_backtest/canonical.py:196-208`)
`est_htf_ctx_fn` retorna `build_multitf_context(ms, t, tfs=(D1,H4,H1,M15,M5,M1), anchored_pd_zones=anchored)`.
`build_multitf_context` → `build_context_stack` (`engine/plan.py:147-163, 367-368`) pone en cada capa:
`trend, close, high, low, sweep_up, sweep_down, bos_dir, choch, fvg_state, ob_dir, time` + `pd_zones` (ancladas).

### C. Lo que entrega MARKETREPLAY (`market_replay/replay.py:67-85` + `availability.py:76-89`)
`_htf_ctx_fn` delega en `avail.snapshot(t)` → por TF devuelve la fila cerrada, y `replay.py:79-84` la reduce a:
**SOLO** `{trend, high, low, close}`.
NO pasa `sweep_up`, `sweep_down`, `pd_zones`, `fvg_*`, `ob_*`, `bos_dir`, `choch`, `time` (por TF).

---

## 1. CUADRO CLAIM-vs-CODE (clasificación por campo)

Leyenda: IGUAL · FALTANTE · TRANSFORMADO · INCORRECTO · NO NECESARIO

| Campo | Motor lo usa (dónde) | Backtest canónico (B) | MarketReplay (M) | Veredicto M vs B |
|-------|----------------------|-----------------------|-------------------|-------------------|
| `trend` | seq:735/358 (bias) | ✅ SÍ (real, `detect_market_structure`) | ⚠️ SÍ pero `row.get("trend","RANGING")` — parquet OHLC **no trae `trend`** → cae a `"RANGING"` siempre | **TRANSFORMADO→INCORRECTO** (B: real; M: RANGING forzado por ausencia de columna) |
| `high` | disponibilidad/POI | ✅ | ✅ | IGUAL |
| `low` | disponibilidad/POI | ✅ | ✅ | IGUAL |
| `close` | disponibilidad | ✅ | ✅ | IGUAL |
| `timestamp` (time por TF) | `build_context_stack` lo pone (`plan.py:162`); motor usa para `closed_row_at_time` | ✅ (time de la fila HTF) | ❌ NO lo pasa (solo high/low/close) | **FALTANTE** |
| `sweep_up` (`liquidity_sweep_up`) | `_htf_has_poi`/búsqueda de liquidez en HTF | ✅ SÍ (`plan.py:154`) | ❌ NO | **FALTANTE** |
| `sweep_down` (`liquidity_sweep_down`) | idem | ✅ SÍ (`plan.py:155`) | ❌ NO | **FALTANTE** |
| `pd_zones` (POI ancladas HTF) | seq:381/409-413 (anotación POI) | ✅ SÍ (`plan.py:367-368`, ancladas por `build_htf_structure_index`) | ❌ NO | **FALTANTE** |
| `fvg_bullish/ob_bullish` (POI HTF) | `_htf_has_poi` seq:399 | ✅ SÍ (en capa HTF del contexto) | ❌ NO | **FALTANTE** |
| `fvg_bearish/ob_bearish` | `_htf_has_poi` seq:401 | ✅ SÍ | ❌ NO | **FALTANTE** |
| `bos_dir` / `choch` | `top_down_allows_trade` (cascada) | ✅ SÍ (`plan.py:156,160`) | ❌ NO | **FALTANTE** |
| HTF→LTF alignment | `closed_row_at_time` por TF (anti look-ahead) | ✅ (build_context_stack delega en `closed_row_at_time`) | ✅ (availability.snapshot delega en `closed_row_at_time`) | IGUAL (mecanismo idéntico) |
| look-ahead | cerrado-only por construcción | ✅ (closed-only) | ✅ (closed-only) | IGUAL |
| ausencia/precencia info futura | no hay por diseño | ✅ (ninguna vela > t) | ✅ (ninguna vela > t) | IGUAL |
| contexto MultiTFContext completo (D1/H4/H1) | `top_down_allows_trade` (seq:754) | ✅ SÍ (objeto completo) | ❌ NO (dict plano por TF, sin cascada) | **TRANSFORMADO** (M entrega dict plano por TF; B entrega MultiTFContext con cascada D1→H4→H1) |

---

## 2. QUÉ NECESITA REALMENTE CADA CONSUMIDOR

| Consumidor | Necesita de `est_htf_ctx_fn` | MarketReplay lo da? |
|-----------|------------------------------|---------------------|
| `run_sequence_traced` (motor, FASE A) | `trend` REAL por capa HTF + `MultiTFContext` para `top_down_allows_trade` | ❌ trend=RANGING, sin MultiTFContext → motor ve RANGING, rechaza setups |
| `evaluate_signals` (backtest, vista trading) | `est_htf_ctx_fn` (ctx) + `est_htf_fn` legacy (dict) | n/a (no usa replay) |
| `run_sequence_backtest` (backtest completo) | `est_htf_ctx_fn` = MultiTFContext canónico | n/a (usa canonical, no replay) |

---

## 3. DIFERENCIAS REPLAY vs BACKTEST CANÓNICO (claim-vs-code)

1. **`trend`**: B = REAL (computado por `detect_market_structure` sobre OHLC). M = `"RANGING"` forzado porque `data/raw/*.parquet` es OHLC puro sin columna `trend`.
2. **`sweep_up/down`**: B = presentes (de `liquidity_sweep_up/down` del `ms`). M = ausentes (replay.py:80-84 solo copia trend/high/low/close).
3. **`pd_zones` / POI HTF**: B = ancladas por `build_htf_structure_index`. M = ausentes.
4. **`fvg_*` / `ob_*` / `bos_dir` / `choch`**: B = en capa HTF. M = ausentes.
5. **Forma del contexto**: B = `MultiTFContext` (dict por TF con cascada). M = dict plano por TF sin cascada.
6. **`timestamp` por TF**: B = lo incluye (`plan.py:162`). M = no lo pasa.

---

## 4. ¿PUEDE LA INFRA ACTUAL REPRODUCIR FIELMENTE EL CONTEXTO DEL MOTOR?

**NO.** MarketReplay entrega un subconjunto estricto y degradado:
- El `trend` es RANGING forzado (no real) → el motor asume "sin sesgo" y **rechaza todos los setups** (0 setups en replay real, confirmado en esta sesión y en el hallazgo `424b060a`).
- `sweep_up/down`, `pd_zones`, `fvg_*/ob_*` (POI HTF) están **FALTANTES** → la dimensión de Autoridad de niveles (POI anclado) no puede auditararse en replay.
- El `MultiTFContext` completo (cascada D1→H4→H1) no se construye → `top_down_allows_trade` no tiene la cascada.

El backtest canónico SÍ reproduce fielmente el contexto (es la fuente de verdad de la FASE A: `A VALIDADA`).

**Conclusión de auditoría:** la frontera MOTOR↔INFRA tiene una deuda de **transformación de contexto** (no de lógica de motor). El motor es correcto; MarketReplay le miente sobre el contexto HTF. Esto es la **Deuda 1** de `docs/infra_deuda_frontera.md`, ahora cuantificada campo por campo.

---

## 5. CONTEXTO DE ALINEACIÓN (lo que el motor lee de `est_htf`, línea por línea)

- `sequence.py:735` `htf_trend = est_htf.get("trend","RANGING")` → si RANGING, `state.reset(); continue` (línea 737-739). **Punto crítico**: trend=RANGING mata el setup.
- `sequence.py:379` `_htf_has_poi` lee `fvg_bullish/ob_bullish` de `est_htf`. MarketReplay no los trae → POI HTF = False siempre.
- `sequence.py:754` `top_down_allows_trade(_ctx, ...)` consume el `MultiTFContext` completo. MarketReplay pasa dict plano → la cascada no evalúa.

---

## 6. MAPA REAL DE CONTRATOS (entregable para el Consejo)

```
Motor (engine/sequence.run_sequence_traced)
   espera: est_htf_ctx_fn(i) -> MultiTFContext
           capa[htf] = {trend(REAL), high, low, close, sweep_up, sweep_down,
                        bos_dir, choch, fvg_*, ob_*, time, pd_zones(ancladas)}
   consume: extract_htf_layer(ctx, htf) -> {trend, sweep_up, sweep_down, pd_zones}
            + top_down_allows_trade(ctx) [cascada D1->H4->H1]

Backtest canonico (ict_backtest/canonical.est_htf_ctx_fn)
   entrega: build_multitf_context(ms, t, tfs=CADENA, anchored_pd_zones)
   => CONTRATO CUMPLIDO (100% fiel)

MarketReplay (_htf_ctx_fn)
   entrega: {tf: {trend(RANGING forzado), high, low, close}}
   => CONTRATO ROTO: trend TRANSFORMADO/INCORRECTO, sweep_up/down FALTANTE,
      pd_zones FALTANTE, fvg_*/ob_* FALTANTE, time FALTANTE, MultiTFContext TRANSFORMADO
```

---

## 7. CLASIFICACIÓN FINAL (resumen ejecutivo para Consejo)

- `trend`: **TRANSFORMADO→INCORRECTO** (B real, M RANGING forzado).
- `high/low/close`: **IGUAL**.
- `timestamp` por TF: **FALTANTE** en M.
- `sweep_up/down`: **FALTANTE** en M.
- `pd_zones` (POI ancladas): **FALTANTE** en M.
- `fvg_*/ob_*` (POI HTF): **FALTANTE** en M.
- `bos_dir/choch`: **FALTANTE** en M.
- `MultiTFContext` (cascada): **TRANSFORMADO** en M (dict plano vs objeto completo).
- HTF→LTF alignment / look-ahead / anti-futuro: **IGUAL** (mecanismo closed-only idéntico).

**Veredicto de auditoría:** la infraestructura de replay **NO puede reproducir fielmente** el contexto que recibe el motor. El backtest canónico sí. La deuda es de transporte de contexto, no de motor.

---

## 8. NOTAS DE GOBIERNAZA

- Este documento es SOLO auditoría. No hay FIX. No se modificó ningún archivo de código.
- El SDD de infraestructura se redacta SOLO después de que el Consejo decida sobre este mapa (tu orden: DESCUBRIR→MEDIR→DOCUMENTAR→ENTENDER→DECIDIR→RECIÉN FIX).
- El run completo de nube `31740419288` sigue `in_progress` (Camino 1, no tocado).
- FASE A sigue cerrada y sin tocar.
