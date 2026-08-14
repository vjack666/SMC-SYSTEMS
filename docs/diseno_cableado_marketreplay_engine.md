# DISEÑO DE CABLEADO — MarketReplay → Engine (pre-FIX, SIN implementación)

**Fecha:** 2026-08-13 · **Estado:** DISEÑO (no ejecutable, no modifica código).
**Autoridad:** Director dicta "diseñar el cableado objetivo sin implementarlo".
**Contrato:** no se toca `engine/`, `ict_backtest/`, `market_replay/`, ni SDD.
No se agrega código. Solo se demuestra, con firmas reales del repo, cómo se
cablearía la autoridad existente del engine en MarketReplay.

---

## 0. Objetivo de esta unidad de trabajo

Unidad pequeña y acotada: **"Contrato de cableado MarketReplay → Engine: diseño
previo al FIX."** No es una fase nueva. FASE A sigue cerrada; no se toca.

Regla que venimos construyendo: descubrir → demostrar → decidir → modificar →
volver a demostrar. Este documento es la fase **DEMOSTRAR** (el diseño), previa a
**DECIDIR** (Consejo/autorización) y **MODIFICAR** (FIX).

---

## 1. Arquitectura objetivo (lo que se propone cablear)

```text
MarketReplay
      │  (disponibilidad temporal OHLC closed-only — YA LO HACE)
      ▼
autoridades EXISTENTES del ENGINE
      ├── engine.multitf_context.build_multitf_context  (contexto MTF)
      ├── engine.plan.build_context_stack               (stack top-down)
      ├── engine.poi_anchor.make_htf_poi_fn             (POI anclado)
      └── engine.htf_pd_index.HtfPdIndex                (PD arrays HTF)
              │
              ▼
        run_sequence_traced(est_htf_ctx_fn=..., htf_poi_fn=..., htf_pd_index=...)
```

MarketReplay sigue siendo **consumidor temporal**: solo ORQUESTA el transporte y
pasa las autoridades del engine al motor. NO calcula SMC.

---

## 2. Las 7 preguntas del Director, respondidas con código real

### P1. ¿Qué función existente debe reutilizarse?

| Autoridad | Firma real (código actual) | Dónde |
|---|---|---|
| Contexto MTF | `build_multitf_context(ms, t, *, tfs=CADENA, anchored_pd_zones=None) -> MultiTFContext` | `engine/multitf_context.py:33` |
| Stack top-down | `build_context_stack(ms, t, tfs=..., anchored_pd_zones=...)` | `engine/plan.py:324` (usada por `build_multitf_context`) |
| POI anclado | `make_htf_poi_fn(ltf_frame, htf_frames, parents=("D1","H4","H1"), window_n=20) -> (i, target) -> bool` | `engine/poi_anchor.py` (MDS_B1 §3.1) |
| PD arrays HTF | `HtfPdIndex(htf_frames)` + `.zones_at(ltf_i, htf_tf, ltf_map)` | `engine/htf_pd_index.py` (MDS_B1 §3.2) |

El backtest canónico YA las usa (`ict_backtest/canonical.py:196-208` pasa
`est_htf_ctx_fn=build_multitf_context(...)` y `canonical.py:234`
`htf_poi_fn=make_htf_poi_fn(ltf_df, htf_frames)`). El motor las acepta en
`run_sequence_traced` (`engine/sequence.py:1098-1113`: `est_htf_ctx_fn`,
`htf_poi_fn`, `htf_pd_index`). **Nada nuevo se inventa.**

### P2. ¿Qué argumentos necesita?

- `build_multitf_context(ms, t, tfs=("D1","H4","H1","M15","M5","M1"), anchored_pd_zones=...)`
  - `ms` = dict de DataFrames OHLC por TF (MarketReplay YA los tiene vía `feed.window(tf)`).
  - `t` = tiempo de la vela LTF (`ltf_df.iloc[i]["time"]`).
- `make_htf_poi_fn(ltf_frame=ltf_df, htf_frames={D1,H4,H1})`
  - MarketReplay tiene `ltf_df_full` y los frames HTF en `self.feed.window(...)`.
- `HtfPdIndex(htf_frames={D1,H4,H1})` + `.build_ltf_map(ltf_df)` + `.zones_at(...)`.

Todos los argumentos son **OHLC cerrado** que MarketReplay ya transporta. No se
requiere información futura.

### P3. ¿Qué dependencia nueva aparecería en MarketReplay?

Hoy `market_replay/replay.py:23` ya importa:
```python
from engine.sequence import SequenceConfig, run_sequence_traced, SequenceState, _candle_objects
```
La dependencia nueva sería añadir (solo lectura de firmas, no ejecución aquí):
```python
from engine.multitf_context import build_multitf_context
from engine.poi_anchor import make_htf_poi_fn
from engine.htf_pd_index import HtfPdIndex
# y posiblemente engine.plan.build_context_stack (ya usada por build_multitf_context)
```
Es decir: `market_replay → engine.multitf_context / engine.poi_anchor / engine.htf_pd_index`.
**NO** a `ict_backtest`. (Ver P4.)

### P4. ¿Viola esa dependencia algún SDD?

`SDD_MARKET_REPLAY` §5 (reglas de dependencia):
```text
market_replay  →  engine            ✅ (consumidor)
market_replay  →  ict_backtest      ❌ PROHIBIDO
engine         →  market_replay     ❌ (motor ignora el alimentador)
```
La nueva dependencia es `market_replay → engine.*` → **PERMITIDA** por la guarda.
Prohibido es solo `→ ict_backtest`. El backtest canónico ya hace exactamente
`ict_backtest → engine.poi_anchor` (consumo), y MarketReplay haciendo
`market_replay → engine.poi_anchor` es el MISMO patrón de consumidor. **No viola.**

Además `SDD_SEPARACION_MOTOR_BACKTEST` establece que el backtest no reimplementa
lógica del motor; el diseño aquí propuesto es lo opuesto: MarketReplay REUTILIZA
autoridades del engine, no las reimplementa. **Coherente.**

### P5. ¿El contexto puede construirse closed-only?

SÍ. `build_context_stack` delega en `closed_row_at_time` por TF (`engine/plan.py`
vía `engine._util`), que ya garantiza anti-look-ahead (MDS_BIAS_HTF §7.2-7.5:
swings con `shift(2).ffill()`, recorte `tail=400`, `index <= ts`). Y
`make_htf_poi_fn` usa `detect_market_structure` (causal) + comparación por
timestamp cross-TF `e.time <= ltf_t` (MDS_B1_POI_ANCLADO §7.1-7.2). `HtfPdIndex`
usa `merge_asof(..., direction="backward")` (solo barra HTF ya cerrada).
**Todo closed-only por diseño.** MarketReplay solo necesita pasar `t` = cierre de
la vela LTF actual (lo ya hace en `run()`).

### P6. ¿Se conserva el anti-look-ahead?

SÍ. MarketReplay sigue pasando `win = objs_full[:i+1]` (velas <= t) y `t` al motor.
Las autoridades del engine reciben `t` y construyen contexto cerrado respecto a `t`.
No hay introducción de velas > t. La guarda `closed_row_at_time(time+duration <= t)`
permanece en la base (`availability.py` ya la usa; `build_context_stack` la reusa).
**El anti-look-ahead se conserva íntegro.**

### P7. ¿MarketReplay sigue siendo consumidor temporal y no un segundo motor?

SÍ, por construcción:
- MarketReplay NO importa `detect_market_structure`, `compute_htf_bias`,
  `detect_fvg`, `detect_order_blocks` directamente para decidir. Solo ORQUESTA:
  llama a `build_multitf_context` / `make_htf_poi_fn` / `HtfPdIndex` y pasa sus
  resultados a `run_sequence_traced`.
- La DECISIÓN (estructura, sesgo, BOS, POI, entrada) sigue 100% dentro de
  `engine/sequence.py`. MarketReplay no lee `state.bos_id` para "decidir" nada;
  solo registra en el `EventJournal` (como hoy).
- Las autoridades invocadas (`build_multitf_context`, `make_htf_poi_fn`,
  `HtfPdIndex`) son **percepción/contexto**, no decisión (MDS_B1 §2: "estos
  módulos son percepción, no decisión"). MarketReplay las usa como proveedoras de
  contexto, no como motor alterno.

**Conclusión P7:** MarketReplay sigue siendo el "transportista de contexto"; el
engine sigue siendo el "cirujano". El diseño no crea un segundo motor.

---

## 3. Contrato de cableado objetivo (resumen)

```text
MarketReplay.run()  [consumidor temporal, SIN lógica SMC]
   │
   ├─ feed.window(tf)  -> ms = {D1,H4,H1,M15,...} OHLC cerrado   [YA LO TIENE]
   │
   ├─ est_htf_ctx_fn(i):
   │      t = ltf_df.iloc[i]["time"]
   │      return build_multitf_context(ms, t, tfs=CADENA,
   │                                   anchored_pd_zones=?)   # reusa engine
   │
   ├─ htf_poi_fn = make_htf_poi_fn(ltf_df, {D1,H4,H1})         # reusa engine
   ├─ htf_pd_index = HtfPdIndex({D1,H4,H1}).build_ltf_map(ltf_df)  # reusa engine
   │
   └─ run_sequence_traced(win, est_htf_ctx_fn, cfg,
                          htf_poi_fn=htf_poi_fn,
                          htf_pd_index=htf_pd_index, ...)
```

vs contrato actual (replay.py:67-85, 120-128): `_htf_ctx_fn` dict plano
{trend,h,low,close} + run_sequence_traced SIN htf_poi_fn/htf_pd_index.

**Delta de cableado:** 3 imports de `engine.*` + 1 closure `est_htf_ctx_fn`
reemplazando `_htf_ctx_fn` + 2 argumentos (`htf_poi_fn`, `htf_pd_index`) en la
llamada. Cero lógica SMC nueva en `market_replay/`.

---

## 4. Riesgos abiertos (para el Consejo, no para el FIX)

1. **`anchored_pd_zones`**: `build_multitf_context` acepta `anchored_pd_zones`.
   El backtest lo pasa desde `build_htf_structure_index` (canonical.py). ¿Debe
   MarketReplay computarlo o pedirlo al engine? → `build_htf_structure_index` ya
   vive en `engine/poi_anchor.py` (MDS_B1 §3.1); MarketReplay podría invocarlo
   (es autoridad del engine, no del backtest). Pendiente decidir en el FIX.
2. **Performance**: construir `build_multitf_context` por vela (vs el dict plano
   actual) añade costo por vela. Ya se optimizó O(n²) en M2-bis; el costo de
   `build_context_stack` debe medirse (no estimarse) antes del FIX.
3. **`copy_objs=False`**: MarketReplay ya lo usa (replay.py:127). Debe conservar
   la semántica al cambiar `est_htf_ctx_fn`.

---

## 5. Veredicto de diseño

Las 7 preguntas del Director tienen respuesta limpia:
- P1-P2: funciones existentes, argumentos OHLC cerrado que MarketReplay ya tiene.
- P3: dependencia `market_replay → engine.*` (ya parcialmente existente).
- P4: NO viola SDD (patrón de consumidor, igual que el backtest).
- P5-P6: closed-only y anti-look-ahead se conservan (las autoridades ya lo son).
- P7: MarketReplay sigue siendo consumidor temporal, no segundo motor.

**El diseño está limpio.** Habilita la decisión del Consejo (autorizar FIX) con
base sólida, y luego la validación (re-ejecutar FASE A sobre replay para confirmar
que POI>0 y trend real sin romper linaje).

---

## 6. GOBIERNANZA

- Documento de DISEÑO. No se implementa. No se modifica `engine/`, `ict_backtest/`,
  `market_replay/`, ni SDD alguno.
- NO se hace addendum a `SDD_MARKET_REPLAY` ni se marca `SDD_M2_LINEAGE` como
  SUPERSEDED (decisión del Director: primero este diseño, luego el FIX, y solo
  DESPUÉS la actualización definitiva de SDD).
- Run completo nube `31740419288` sigue `in_progress` (Camino 1, no tocado).
- FASE A sigue cerrada.
