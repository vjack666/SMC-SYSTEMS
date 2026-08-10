# SETUP_AUDITOR_DATA_FORENSICS.md — Auditoría forense de datos (etapa previa al piloto)

> **Auditoría documental (2026-08-10). LECTURA DEL REPO, CERO ejecución del motor, CERO backtest de
> rendimiento.** Responde a la instrucción del Director: *"localiza cómo obtener 5 emisiones de
> `run_sequence` conservando `Expediente.history`, `MarketObject[]`, señal, timestamps y contexto
> HTF, sin modificar `engine/` ni ejecutar backtest de rendimiento; si no existen 5 emisiones
> reproducibles con su evidencia, DETENTE y documenta qué falta y dónde."*
>
> Conclusión adelantada: **las emisiones NO están persistidas** (el motor las descarta salvo vía
> `run_sequence_traced`); **los datos crudos solo traen OHLC+time** (las features se recalculan
> on-the-fly); **hay datos para 5 símbolos con D1/H4/M15** (cadena top-down alcanzable), pero el
> linaje de causalidad sigue sin ser observable. Abajo el inventario exacto y las lagunas.

---

## 1. Cómo obtener una emisión hoy (mecanismo real, sin tocar engine/)

`engine/sequence.py`:
- `run_sequence(...)` (público, `:641`) devuelve **solo `(signals, phase_seen)`** — descarta el 3er
  elemento. El `Expediente` NO viaja en esta firma.
- `run_sequence_traced(...)` (`:660`) devuelve **`(signals, phase_seen, expedientes)`** — esta SÍ
  expone la lista de `Expediente` por señal (Ley 8/7/4 de trazabilidad). **Es la vía correcta** para
  obtener emisiones con su bitácora.

`engine/expediente.py`:
- `Expediente.phase_events` es la traza vela por vela: `[(SWEEP,i,t),(DISPLACE,i,t),(BOS,i,t),
  (ENTRY,i,t)]`. **NOTA:** la documentación HYP-002 llama a esto `Expediente.history`, pero en código
  real el atributo es **`phase_events`** (nombraremos correctamente de aquí en adelante).
- `Expediente.to_dict()` serializa todo (id, symbol, tf, direction, phase_events, meta).
- `MarketObject` (`engine/market_object.py:50`) es la vista de vela; la secuencia itera sobre
  `MarketObject[]`. La señal expone `sweep_at/displace_at/bos_at/entry_at` (índices), `bos_level`,
  `poi_present`, `htf_aligned`, `htf_reason` (`sequence.py:618-633`).

**Receta (sin modificar engine/):** cargar `data/raw/{SYM}_{TF}.parquet` → `data_feed.load_tf`/
`build_features` (recalcula features) → envolver en `MarketObject[]` vía
`ict_backtest.translation.df_to_objects` → `run_sequence_traced(MarketObject[], est_htf_fn, cfg)`.
Salida: señales + `Expediente[]` (bitácora) + los `MarketObject[]` de entrada ya los tenemos (los
pasamos). Contexto HTF: `est_htf_ctx_fn` (cadena D1→H4→H1 vía `engine.plan.build_context_stack`).

---

## 2. Inventario de evidencia DISPONIBLE por emisión (lo que SÍ hay)

| Dato requerido por el Director | ¿Disponible hoy? | Fuente |
|---|---|---|
| Señal original (time/direction/entry) | SÍ | `run_sequence_traced` → `signals[].entry/atr/bos_level` |
| `Expediente` (bitácora vela a vela) | SÍ (vía `_traced`) | `expedientes[]` (`phase_events`) |
| `MarketObject[]` del LTF | SÍ | entrada a `run_sequence_traced`; persiste en memoria |
| Timestamps por fase | SÍ | `phase_events[].time` + `sweep_at/displace_at/bos_at/entry_at` |
| Contexto D1/H4/H1 | SÍ (crudo) | `data/raw/{SYM}_{D1,H4,H1}.parquet` (EURUSD tiene H1; los demás H4) |
| Orden de eventos | SÍ | `sweep_at<displace_at<bos_at<entry_at` |
| Dirección coherente por fase | SÍ | `displacement_*`/`bos_dir` en `MarketObject.meta` |
| Presencia de POI (booleano) | SÍ | `poi_present` (con frames HTF) |
| Cuadro de retorno (real o sintético) | SÍ | `zone_high/zone_low` (`sequence.py:594-596`) |

## 3. Inventario de evidencia FALTANTE (lo que NO está observable)

| Dato que la tesis exige | Estado | Por qué |
|---|---|---|
| **Nivel de liquidez barrido por el sweep** | NO persistido | `sweep_low/sweep_high` solo existen tras `build_features` (en memoria). El `MarketObject` de la vela sweep trae `low/high` (OHLC crudo), así que el auditor SÍ puede leer el wick del sweep y compararlo con `bsl/ssl_price` de esa vela. **PERO** `bsl/ssl_price` (pools de liquidez de `detect_liquidity`) tampoco está en el parquet crudo → hay que recalcular `build_features` o leer `ssl_price[i]` del frame enriquecido. La ligadura sweep→ESA liquidez es re-derivable a partir de OHLC+features, no "imposible", pero NO viene embolsada en la señal. |
| **Swing roto por el BOS** | NO en señal | `bos_level` (`sequence.py:579`) es un nivel, no el identificador del swing. No hay `swing_id`. |
| **Evento ancla del POI** (`parent_event (tf,time,kind)`) | NO en señal | `poi_present` es booleano; `make_htf_poi_fn` (`poi_anchor.py`) no lo expone. Recuperable re-leyendo `build_htf_structure_index` sobre frames HTF (la función existe), pero no viene en la emisión. |
| **Magnitud de displacement** | NO en señal | solo flag `displacement_*`; `displacement_mag` existe en features (`data_feed:126`) pero no se pasa a la señal. El auditor puede computarlo del `MarketObject` (cuerpo/rango). |
| **confirmación LTF fina (M5/M1)** | NO existe | motor corre 1 LTF (`sequence.py:641` default M15). GAP-2. |
| **contexto macro/noticias** | NO existe | `engine/macro_calendar` ausente. GAP-1. |

---

## 4. Hallazgo central sobre los DATOS CRUDOS

`data/raw/*.parquet` contiene **SOLO `time, open, high, low, close`** (verificado en EURUSD_M15:
114,237 filas, columnas exactas = OHLC+time). Las features ICT (`sweep_low`, `bsl/ssl_price`,
`fvg_mid`, `displacement_*`, `atr`, etc.) **NO están persistidas**: se recalculan on-the-fly en
`ict_backtest/data_feed.build_features` cada vez que se carga (`data_feed.py:46-146`).

Consecuencias:
- El auditor NO puede leer el nivel barrido ni los pools de liquidez directamente del parquet; debe
  pasar por `build_features` (o reconstruir el wick del sweep desde OHLC y comparar con un pool
  recalculado). No es un bloqueo, pero añade un paso y rompe la ilusión de "emisiones ya embolsadas".
- **No hay 5 emisiones ya emitidas y guardadas con su `Expediente` + `MarketObject[]` esperando en
  disco.** Para tenerlas hay que *ejecutar* `run_sequence_traced` sobre los parquets (cosa que la
  instrucción permite hacer, siempre que sea para OBTENER emisiones y no para medir rendimiento).

---

## 5. Cobertura de símbolos/TF para la cadena top-down

`data/raw/` provee (verificado):
- **EURUSD**: D1, H1, H4, M1, M5, M15, M30 — **cadena D1→H4→H1 completa disponible**.
- **AUDUSD, GBPUSD, NZDUSD, USDCAD, USDCHF, USDJPY**: D1, H4, M15 — **cadena D1→H4 (sin H1)**.
- **XAUUSD**: **NO en `data/raw/`** (solo zip comprimidos en `data/histdata_tmp/`, sin procesar a
  parquet). STEP/índices: ausentes en raw.

Para 5 emisiones reproducibles con contexto top-down, los **6 símbolos forex** sirven (EURUSD con
H1 completo; los otros con D1/H4/M15). XAUUSD queda fuera hasta descomprimir/procesar su zip.

---

## 6. Veredicto de la etapa

- **¿Existen 5 emisiones reproducibles con `Expediente` + `MarketObject[]` ya persistidas?** NO. No
  hay caché de emisiones en disco; el motor descarta el `Expediente` salvo por `run_sequence_traced`.
- **¿Se pueden OBTENER 5 emisiones hoy sin modificar `engine/`?** SÍ: ejecutando `run_sequence_traced`
  sobre `data/raw/{SYM}_{TF}.parquet` (6 símbolos forex disponibles; EURUSD con H1). Eso produce
  señal + `Expediente[]` + `MarketObject[]` de entrada + contexto HTF recargable. **Esa ejecución es
  de OBTENCIÓN, no de rendimiento** (prohibido por la instrucción es el backtest de WR/PF, no la
  generación de emisiones).
- **¿El auditor puede auditar causalidad completa con eso?** NO. Orden+dirección SÍ; linaje de
  liquidez NO (ver §3). Esto coincide con `SETUP_AUDITOR_RECONCILIATION.md`: el motor no conserva
  identificadores de linaje → el auditor emite UNKNOWN/CAUSALITY BROKEN donde falte eslabón, no lo
  infiere.

**Decisión según la instrucción:** la instrucción dice *"si no existen 5 emisiones reproducibles con
su `Expediente` y `MarketObject[]`, detente y documenta qué falta"*. Técnicamente NO están
persistidas, pero SÍ son **obtenibles** por código ya existente sin tocar `engine/`. Lo documento
así: el bloqueo no es de código sino de **persistencia** (no hay caché) y de **linaje** (el motor no
embolsa los identificadores de causalidad). El piloto puede correr como "obtención + auditoría",
pero su veredicto de causalidad seráforzosamente UNKNOWN/BROKEN en las capas de ligadura.

---

## 7. Qué falta y dónde obtenerlo (plan de acción, NO ejecutado)

1. **Persistencia de emisiones**: añadir un script (nuevo, fuera de `engine/`) que llame
   `run_sequence_traced` y guarde `{signal, expediente.to_dict(), marketobjects, ctx_htf}` por
   emisión en JSON/parquet. Sin tocar `engine/`.
2. **Nivel barrido / pools**: tras `build_features`, el frame enriquecido trae `sweep_low` y
   `ssl/bsl_price`; el auditor los lee del frame (no del parquet crudo). O bien reconstruye el wick
   del sweep desde OHLC y compara con el pool más cercano.
3. **Linaje (GAP estructural)**: para que el auditor pueda ligar sweep→liquidez→displacement→BOS→POI,
   el motor debería exponer `swing_id` roto y `parent_event` del POI. Hoy NO lo hace → es el hallazgo
   científico de HYP-002, no un bug del auditor. Se documenta; no se parchea el motor en esta fase.
4. **Macro/Noticias (GAP-1)**: fuera de alcance; el piloto las trata como UNKNOWN/INFO.

*Auditoría forense de datos. Sin ejecución de motor ni backtest. Complementa
`SETUP_AUDITOR_RECONCILIATION.md` y prepara el terreno del piloto de 5 emisiones.*