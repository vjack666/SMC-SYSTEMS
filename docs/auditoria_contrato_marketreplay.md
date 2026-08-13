# AUDITORÍA DE CONTRATO — MarketReplay vs Arquitectura Existente

**Fecha:** 2026-08-13 · **Modo:** DESCUBRIR / MEDIR / DOCUMENTAR / ENTENDER. **NO-FIX.**
**Contrato:** no se modifica `engine/`, `ict_backtest/`, `market_replay/`, ni contratos.
El GAP POI=0 de FASE A **NO se trata como fallo del motor** (ver §4).

---

## 0. Veredicto de dirección (corto)

No necesitamos un nuevo SDD. No necesitamos elegir A/B/C como si la arquitectura estuviera indefinida. **La arquitectura ya está definida** (`SDD_MARKET_REPLAY`, `SDD_SEPARACION_MOTOR_BACKTEST`, `MDS_BIAS_HTF`, `MDS_B1_POI_ANCLADO`). Lo encontrado es una **implementación de MarketReplay por debajo del contrato que ya existe**.

MarketReplay es la "ambulancia" (disponibilidad temporal). El engine es el "cirujano" (construye contexto con sus propias autoridades). Hoy la ambulancia llega y dice "tengo precio y no sé la tendencia" — el error es de **cableado de transporte**, no de cirugía faltante en el motor.

---

## 1. CONTRATO ACTUAL (lo que hay)

### MarketReplay (`market_replay/replay.py`)
- `_htf_ctx_fn(t)` → delega en `avail.snapshot(t)` → por TF devuelve fila cerrada → la reduce a `{trend, high, low, close}` (replay.py:79-84).
- `run()` llama `run_sequence_traced(win, self._htf_ctx_fn, self.cfg, ltf_tf=..., initial_state=..., start_i=..., copy_objs=False)` (replay.py:120-128).
- **NO pasa** `htf_poi_fn` ni `htf_pd_index` (ver secuencia.py:1098-1113 que SÍ los acepta).
- `trend` viene de `row.get("trend", "RANGING")` sobre parquet OHLC puro (sin columna trend) → **siempre "RANGING"**.

### Engine (`engine/sequence.run_sequence_traced`)
- Acepta: `est_htf_fn`, `cfg`, `htf_poi_fn=None`, `htf_pd_index=None`, `ltf_map`, `est_htf_ctx_fn` (secuencia.py:1098-1113).
- USA `htf_poi_fn(i, target)` para anotar `poi_present` (secuencia.py:780-786, 902) — si es `None`, comportamiento histórico (no anota).
- USA `est_htf_ctx_fn(i)` → `extract_htf_layer` → lee `trend` (secuencia.py:729-739). Si `trend=RANGING` → `state.reset(); continue` → **rechaza setup**.

### Backtest canónico (`ict_backtest/canonical.py:196-208`)
- `est_htf_ctx_fn` retorna `build_multitf_context(ms, t, tfs=CADENA, anchored_pd_zones=...)`.
- `canonical.py` SÍ cablea `htf_poi_fn=make_htf_poi_fn(ltf_df, htf_frames)` (línea 234) y `est_htf_ctx_fn`.
- O sea: el backtest respeta el contrato completo; MarketReplay no.

---

## 2. CONTRATO OBJETIVO (lo que dictan los SDD/MDS existentes)

### A) Datos que DEBE transportar MarketReplay (su misión, `SDD_MARKET_REPLAY` §1/§3)
- RAW OHLC por TF (ya lo hace vía `MarketFeed`/`TemporalAvailability`).
- Disponibilidad temporal closed-only por TF (ya lo hace).
- **NO debe calcular nada de SMC** (BOS, sweep, POI, FVG, OB, CHOCH, dirección, entrada) — `SDD_MARKET_REPLAY` §1 y `SDD_SEPARACION_MOTOR_BACKTEST` lo prohíben explícitamente.

### B) Contexto que DEBE calcular el ENGINE (sus autoridades existentes)
- **Bias HTF**: `engine/bias/narrative.py` → `compute_htf_bias` (MDS_BIAS_HTF ✅ HECHO). Entrada: OHLC cerrado D1/H4/H1.
- **Estructura / trend**: `engine.bos.structure.detect_market_structure` (única fuente).
- **POI anclado**: `engine/poi_anchor.make_htf_poi_fn` + `engine/htf_pd_index.HtfPdIndex` + `engine/zone_authority` (MDS_B1_POI_ANCLADO ✅ HECHO). Entrada: frames OHLC por TF.
- **MultiTFContext**: `engine/multitf_context.build_multitf_context` / `engine/plan.build_context_stack` (ya existen, las usa el backtest canónico).

### C) Lógica PROHIBIDA mover a MarketReplay (`SDD_SEPARACION_MOTOR_BACKTEST`, `SDD_MARKET_REPLAY` §5)
- ❌ Reimplementar sesgo / BOS / sweep / POI / FVG / OB / CHOCH.
- ❌ Ser oráculo de decisión.
- ✅ Solo: transportar OHLC cerrado + disponibilidad + cablear las autoridades del engine.

---

## 3. GAP (contrato actual → objetivo), campo por campo

| Ítem | Contrato actual | Contrato objetivo (SDD/MDS) | GAP |
|------|----------------|------------------------------|-----|
| Transporte OHLC | ✅ SÍ | ✅ SÍ | IGUAL |
| Disponibilidad closed-only | ✅ SÍ | ✅ SÍ | IGUAL |
| `trend` HTF | RANGING forzado (parquet sin columna) | Engine lo calcula vía `detect_market_structure` (backtest lo hace) | **FALTANTE en M.R.**: M.R. no invoca la autoridad de bias del engine |
| `est_htf_ctx_fn` | M.R. usa `_htf_ctx_fn` propio (dict plano trend/high/low/close) | M.R. debe pasar la infra de contexto del engine (`build_multitf_context`/`build_context_stack`) igual que el backtest | **TRANSFORMADO**: dict plano vs MultiTFContext |
| `htf_poi_fn` | M.R. **NO lo pasa** a `run_sequence_traced` | M.R. debe cablear `make_htf_poi_fn` (el motor ya lo acepta en secuencia.py:1099) | **FALTANTE** (causa del POI=0 en replay) |
| `htf_pd_index` | M.R. **NO lo pasa** | M.R. debe cablear `HtfPdIndex` (motor lo acepta) | **FALTANTE** |
| `sweep_up/down` / `pd_zones` / `fvg_*` / `ob_*` | M.R. no los transporta | Engine los deriva de `ms` (backtest lo hace vía `build_multitf_context`) | **FALTANTE en M.R.** (el engine los necesita para POI/autoridad) |
| look-ahead | ✅ closed-only | ✅ closed-only | IGUAL |
| HTF→LTF alignment | ✅ (closed_row_at_time) | ✅ | IGUAL |

**Conclusión de GAP:** MarketReplay transporta OHLC bien, pero **no cablea las autoridades de contexto del engine** que el backtest canónico sí cablea. Por eso el motor, alimentado por replay, ve `trend=RANGING` y `poi=None` y rechaza/anoNO-ancla setups. El motor NO está roto: en FASE A (backtest canónico) dio `A VALIDADA` con POI anclado funcionando vía `htf_poi_fn`.

---

## 4. El GAP POI=0 de FASE A — reinterpretación

Mi reporte FASE A marcó `POI anclado HTF = 0` como GAP. Tras leer `MDS_B1_POI_ANCLADO` y `sequence.py`, **ya no lo trato como fallo del motor**:

- El motor SÍ tiene toda la autoridad POI (`engine/poi_anchor.py`, `htf_pd_index.py`, `zone_authority.py`, estado ✅ HECHO).
- El backtest canónico la cablea (`canonical.py:234` `htf_poi_fn=make_htf_poi_fn(...)`).
- Mi runner ligero (FASE A) llamó `run_sequence_traced` **sin** `htf_poi_fn` → por eso `poi_present` no se anotó → POI=0 en mi reporte.
- MarketReplay igual: `run()` no pasa `htf_poi_fn` (replay.py:120-128).

**Por tanto POI=0 es un GAP de CABLEADO del consumidor, no del motor.** El motor puede anclar POI; mis dos consumidores (runner ligero y MarketReplay) no le pasaron la closure. Esto es coherente con tu lectura: "el replay simplemente no está proporcionando el camino completo que el motor necesita para demostrarlo".

---

## 5. ¿Por qué MarketReplay usa `_htf_ctx_fn` propio en vez de la infra del engine?

Evidencia en `SDD_MARKET_REPLAY` §6.7.2 FASE 7 (líneas 339-358): el hallazgo ya estaba documentado ahí — `_htf_ctx_fn` simplificada "NO calcula trend", y el arreglo propuesto era "cablear `engine/plan.build_context_stack` a market_replay" (trabajo de capa de observación, **FUERA de M2**).

O sea: **no es un diseño nuevo, es una deuda ya conocida y explícitamente fuera de autorización**. Mi auditoría campo por campo solo la cuantifica y la amplía (no solo `trend`, también `sweep/pd_zones/fvg/ob/poi`).

---

## 6. Estado documental de `SDD_M2_LINEAGE.md` (deuda documental)

`SDD_M2_LINEAGE.md` describe como PENDIENTE: "agregar `event_objects` a `run_sequence_traced`".
**Eso YA NO es el estado del repo**: FASE A se validó justamente porque `run_sequence_traced` **ya emite** `event_objects`/`event_ids` (sequence.py:1037/1069). El SDD quedó **SUPERSEDED** por el código actual.

Según `SDD_GOVERNANCE` §0, un spec debe reflejar el código real y puede marcarse `SUPERSEDED`. `SDD_M2_LINEAGE.md` requiere una limpieza documental (marcar SUPERSEDED / actualizar al estado actual), **sin re-ejecutar su implementación** (ya está hecha).

---

## 7. MAPA: CONTRATO ACTUAL → OBJETIVO → GAP → NO-FIX

```
CONTRATO ACTUAL (MarketReplay)
  transporta: OHLC + disponibilidad closed-only
  contexto HTF: {trend:RANGING, high, low, close}  [propio, degradado]
  pasa a run_sequence_traced: est_htf_fn + cfg
  NO pasa: htf_poi_fn, htf_pd_index, est_htf_ctx_fn(MultiTFContext)
        │
        ▼ GAP
CONTRATO OBJETIVO (SDD_MARKET_REPLAY + MDS_BIAS_HTF + MDS_B1_POI_ANCLADO)
  transporta: OHLC + disponibilidad closed-only        [IGUAL, ya cumple]
  contexto HTF: lo construye EL ENGINE vía sus autoridades
                (build_multitf_context / build_context_stack / make_htf_poi_fn /
                 HtfPdIndex) — igual que el backtest canónico lo hace
  pasa a run_sequence_traced: est_htf_ctx_fn + htf_poi_fn + htf_pd_index
        │
        ▼ ACCIÓN (NO-FIX hasta decisión del Consejo)
  - MarketReplay debe CABLEAR (no implementar) las autoridades del engine.
  - El engine ya sabe hacer todo (bias, estructura, POI, contexto MTF).
  - No se mueve lógica SMC a market_replay (prohibido por SDD_SEPARACION).
```

---

## 8. CLASIFICACIÓN FINAL (claim-vs-code, para Consejo)

- `trend` en M.R.: **TRANSFORMADO→INCORRECTO** (RANGING forzado; el engine puede real).
- `est_htf_ctx_fn` en M.R.: **TRANSFORMADO** (dict plano vs MultiTFContext del engine).
- `htf_poi_fn`: **FALTANTE** en M.R. (motor lo acepta, backtest lo cablea, M.R. no).
- `htf_pd_index`: **FALTANTE** en M.R.
- `sweep_up/down`, `pd_zones`, `fvg_*`, `ob_*`: **FALTANTE** en M.R. (engine los deriva de `ms`).
- OHLC / disponibilidad / look-ahead / alignment: **IGUAL** (cumple).
- POI=0 en FASE A: **NO es fallo del motor**; es GAP de cableado del consumidor (runner ligero y M.R. no pasan `htf_poi_fn`).
- `SDD_M2_LINEAGE.md`: **SUPERSEDED** por el código (ya hay `event_objects`).

---

## 9. NOTAS DE GOBIERNAZA

- Solo auditoría. NO se modificó `engine/`, `ict_backtest/`, `market_replay/`, ni contratos.
- NO se implementa ningún fix. La corrección (cuando el Consejo la autorice) es **cablear** las autoridades del engine en MarketReplay, no escribir lógica SMC en replay.
- El SDD existente `SDD_MARKET_REPLAY` debe recibir un addendum (§9 Frontera de contexto HTF) que cite esta auditoría y marque el contrato objetivo. No se crea SDD nuevo.
- `SDD_M2_LINEAGE.md` debe marcarse SUPERSEDED (limpieza documental, no código).
- Run completo nube `31740419288` sigue `in_progress` (Camino 1, no tocado). FASE A sigue cerrada.
