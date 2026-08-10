# PILOT_PREP_MATRIX.md — Matriz de preparación del piloto: ¿puede el SETUP AUDITOR demostrar causalidad sin inventarla?

> **Auditoría documental (2026-08-10). LECTURA DEL REPOSITORIO, CERO código, CERO ejecución.**
> Responde a la orden del Director: antes del piloto, determinar si el SETUP AUDITOR puede
> demostrar "ESTE sweep produjo ESTE displacement que produjo ESTE BOS que creó ESTE POI".
> Verificado en `engine/sequence.py` (máquina de estados + `_has_*`), `engine/poi_anchor.py`,
> `engine/market_object.py`, `ict_backtest/bos_table_builder.py`, `ict_backtest/data_feed.py`.

---

## 0. Cómo enlaza el motor hoy (hecho de código, no suposición)

La máquina de estados (`sequence.py:525-637`) guarda en `state` **SOLO ÍNDICES ENTEROS**:
`sweep_idx`, `displace_idx`, `bos_idx`, `entry_at` (`sequence.py:529,561,577,613`). NO guarda
referencias a `MarketObject`, ni `swing_id` roto, ni `parent_event` del POI.

Los `MarketObject` de entrada (`market_object.py:50`) SÍ tienen `parent_object` / `related_objects`
y `bar_index`/`bar_time`, PERO la secuencia NO los usa para ligar sweep→displacement→BOS→POI. El
anclaje de POI (`poi_anchor.py`) empareja por **dirección + timestamp cross-TF** (BOS/CHOCH de HTF
ya cerrado ≤ time LTF), NO por identidad de swing roto.

Conclusión estructural: el motor demuestra **orden temporal + dirección coherente + anclaje HTF por
timestamp**. NO demuestra identidad causal 1:1 (este sweep → este displacement → este BOS → este POI).

---

## 1. Matriz por transición

### LIQUIDEZ → SWEEP
- **Evidencia existente:** `obj.meta["liquidity_sweep_up/down"]` (bool) o `est_htf["sweep_up/down"]`
  (`sequence.py:164-166`). OHLC de la vela (wick del sweep).
- **Dato NO existe:** el **nivel de liquidez barrido** (precio exacto del SSL/BSL tocado) no está
  embolsado en la señal ni en el `MarketObject` del sweep. El parquet raw es SOLO OHLC; el nivel de
  pool se recalcula en `build_features` y no se persiste.
- **Puede demostrar:** que hubo un evento de sweep en dirección opuesta al setup (flag bool + wick
  del OHLC que tocó un extremo).
- **Solo puede inferir:** QUÉ liquidez específica se barrió (debe re-derivar el pool de swings del
  OHLC y emparejar por timestamp — posible leyendo objetos existentes, pero no viene embolsado).
- **Debe quedar UNKNOWN:** si no hay `MarketObject` de `sweep_idx` → UNKNOWN.
- **Falso PASS:** flag `liquidity_sweep_*` presente por ruido de mecha sin pool real de liquidez
  detrás → PASS espurio. Mitigación: el auditor debe verificar el wick contra un pool re-derivado,
  no solo el bool.
- **Falso FAIL:** pool de liquidez válido pero el detector no marcó el flag → FAIL injusto.

### SWEEP → DISPLACEMENT
- **Evidencia existente:** `sweep_idx < displace_idx` (`sequence.py:554` `i - state.sweep_idx`);
  `displacement_bullish/bearish` bool (`sequence.py:179-185`).
- **Dato NO existe:** que el displacement **nació del mismo nivel barrido**. El motor solo exige
  orden temporal (`displace_at > sweep_at`) y dirección. No hay `swing_id` ligado.
- **Puede demostrar:** orden temporal + dirección coherente (displacement en dir del setup, posterior
  al sweep).
- **Solo puede inferir:** que el displacement partió del nivel del sweep (requiere re-derivar el
  nivel del sweep del OHLC y comprobar que el cuerpo del displacement abre más allá de él).
- **Debe quedar UNKNOWN:** si no hay `MarketObject` de `displace_idx` → UNKNOWN.
- **Falso PASS:** cualquier displacement en dir correcta tras el sweep cuenta, aunque no esté
  ligado al nivel barrido (sweep y displacement pueden ser eventos independientes).
- **Falso FAIL:** displacement fuerte pero el flag no se activó (umbral de mecha) → FAIL injusto.

### DISPLACEMENT → BOS/CHOCH
- **Evidencia existente:** `displace_idx < bos_idx` (`sequence.py:566`); `bos_dir`/`choch_dir`
  (`sequence.py:211-220`); `bos_level` en la señal (`sequence.py:579,622`).
- **Dato NO existe:** el **swing roto por el BOS** (`swing_id`). El `MarketObject` del BOS no lleva
  el identificador del swing que rompió. `build_bos_table` (`bos_table_builder.py:124`) devuelve
  buckets de mitigación, no ligadura swing→BOS.
- **Puede demostrar:** orden temporal + dirección + nivel del BOS (`bos_level`).
- **Solo puede inferir:** que el BOS rompió el swing formado por el displacement (requiere
  re-derivar swings del OHLC y emparejar por timestamp/nivel — posible leyendo objetos existentes).
- **Debe quedar UNKNOWN:** si no hay `bos_level` finito → UNKNOWN.
- **Falso PASS:** BOS en dir correcta tras displacement, aunque rompa un swing distinto al del
  impulso (no hay identidad).
- **Falso FAIL:** BOS válido pero `bos_dir` no anotado → FAIL injusto.

### BOS/CHOCH → POI
- **Evidencia existente:** `htf_poi_fn(i, target)` (`poi_anchor.py:111`) → True si hay BOS/CHOCH de
  HTF en la MISMA dirección, ya cerrado (time ≤ LTF). `poi_present` bool en la señal
  (`sequence.py:503,628`). Zona FVG/OB del LTF memorizada (`zone_high/zone_low`).
- **Dato NO existe:** el **`parent_event`** del POI (qué BOS/CHOCH de HTF específico lo ancla). El
  anclaje empareja por dirección+timestamp, NO por identidad. Tampoco hay POI `MarketObject`
  enlazado al BOS LTF.
- **Puede demostrar:** que existe un POI de HTF en dir del setup (anclaje por timestamp cross-TF) +
  zona LTF delimitada.
- **Solo puede inferir:** cuál BOS/CHOCH de HTF ancla exactamente este POI LTF (hay ventana de
  `window_n=20` eventos; no identidad única).
- **Debe quedar UNKNOWN:** si `htf_poi_fn` devuelve True por "sin eventos padre cargados"
  (`poi_anchor.py:116` → no bloquea histórico) → eso es **ausencia de anclaje verificable**, debe
  marcarse UNKNOWN/BROKEN, no PASS silencioso. Si no hay zona FVG/OB finita → cae al fallback
  geométrico → WARNING (C5).
- **Falso PASS:** `htf_poi_fn=True` por defecto histórico (sin padres) se interpreta como POI
  presente; o POI de HTF en dir correcta pero sin relación con ESTE BOS LTF.
- **Falso FAIL:** POI real existe pero no se cargó el frame HTF → FAIL injusto.

### POI → RETORNO
- **Evidencia existente:** `_touches_zone(zone_high, zone_low, entry_at)` (`sequence.py:607,271`).
- **Dato NO existe:** que el retorno sea al POI **anclado** y no a un nivel arbitrario (si se usó el
  fallback geométrico, no hay POI real).
- **Puede demostrar:** que el precio tocó el cuadro memorizado (FVG/OB real o fallback).
- **Solo puede inferir:** si el cuadro era POI real o respaldo geométrico (viene en `zone_*` de
  `state`, recuperable de la señal/Expediente).
- **Debe quedar UNKNOWN:** si no hay `zone_high/zone_low` finitos ni `close[entry_at]` → UNKNOWN.
- **Falso PASS:** toque del fallback geométrico `bos_level ± 0.5·rango` interpretado como POI real →
  C5 lo convierte en WARNING (no PASS).
- **Falso FAIL:** toque real pero `zone_*` no finito por bug de memoria → FAIL injusto.

### HTF → SETUP
- **Evidencia existente:** `est_htf_ctx_fn` → `top_down_allows_trade` (`sequence.py:477`);
  `est_htf` dict con `trend`, `sweep_*`, `displacement_*`, `fvg_*/ob_*`.
- **Dato NO existe:** justificación narrativa de POR QUÉ el HTF permite el trade más allá de
  tendencia+anclaje direccional.
- **Puede demostrar:** alineación de cascada D1→H4→H1 con la dirección objetivo (con
  `est_htf_ctx_fn` presente); `htf_aligned`/`htf_reason` en la señal.
- **Solo puede inferir:** sesgo institucional profundo (premium/discount del HTF no está embolsado
  en la señal como veredicto).
- **Debe quedar UNKNOWN:** si `est_htf_ctx_fn is None` (modo legacy) → el HTF no se audita → UNKNOWN
  por falta de contexto. Si el llamador no pasa frames HTF → HTF no evaluate.
- **Falso PASS:** `top_down_allows_trade` pasa por alineación direccional aunque el POI no esté
  anclado (el POI es bonus, no veto — `require_pd=False`, `sequence.py:479`).
- **Falso FAIL:** sesgo HTF válido pero `top_down_allows_trade` lo rechaza por regla de cascada
  estricta → FAIL injusto (depende de config).

### MACRO/NEWS → SETUP
- **Evidencia existente:** **NINGUNA** en `engine/` ni en la señal. El motor no consume macro/noticias.
- **Dato NO existe:** cualquier dato macro/news. GAP-1 fuera de alcance del motor y del auditor.
- **Puede demostrar:** NADA.
- **Solo puede inferir:** NADA (no hay fuente).
- **Debe quedar UNKNOWN:** SIEMPRE para esta transición. El auditor marca MACRO/NEWS = UNKNOWN
  explícito (no se inventa contexto).
- **Falso PASS:** imposible a menos que el auditor invente contexto → PROHIBIDO por la regla
  superior (reconstrucción retrospectiva = UNKNOWN/BROKEN).
- **Falso FAIL:** no aplica (no hay datos que fallen).

---

## 2. Matriz resumida (formato pedido)

| TRANSICIÓN | EVIDENCIA EXISTENTE | CAUSALIDAD DEMOSTRABLE | UNKNOWN NECESARIO | RIESGO DE FALSO PASS | BLOQUEADOR |
|---|---|---|---|---|---|
| LIQUIDEZ→SWEEP | flag sweep + wick OHLC | nivel de pool barrido (re-derivable del OHLC) | sin MarketObject sweep | flag por ruido de mecha | nivel de pool no embolsado (recuperable de OHLC) |
| SWEEP→DISPLACEMENT | orden temporal + flag dir | NO (solo orden+dir) | sin MarketObject displace | displacement suelto tras sweep cuenta | swing_id ligado al sweep NO existe |
| DISPLACEMENT→BOS | orden + bos_dir + bos_level | NO (solo orden+dir+nivel) | sin bos_level finito | BOS rompe swing distinto | swing roto por BOS NO embolsado |
| BOS/CHOCH→POI | htf_poi_fn (dir+timestamp) + zona LTF | NO (anclaje por dir+ts, no identidad) | htf_poi_fn=True por defecto histórico | POI de HTF genérico cuenta como ancla | parent_event del POI NO existe |
| POI→RETORNO | _touches_zone | toque del cuadro (real o fallback) | sin zona/close finitos | fallback geométrico como POI real | distinción real/fallback solo en zone_* |
| HTF→SETUP | est_htf_ctx_fn + est_htf dict | alineación cascada D1→H4→H1 | est_htf_ctx_fn=None → UNKNOWN | pasa sin POI anclado (bonus) | sesgo profundo no embolsado |
| MACRO/NEWS→SETUP | NADA | NADA | SIEMPRE UNKNOWN | inventar contexto = PROHIBIDO | GAP-1: fuente macro inexistente en motor |

---

## 3. Decisión

**PILOTO LISTO** — pero con la salvedad científica explícita:

El SETUP AUDITOR **NO puede demostrar causalidad 1:1** (este sweep → este displacement → este BOS →
este POI) con los datos que el motor embolsa hoy. Eso NO es un bloqueo del piloto: es el **hallazgo
central de HYP-002**. El piloto debe ejecutarse precisamente para CUANTIFICAR dónde la cadena se
rompe, emitiendo UNKNOWN/BROKEN donde falte identidad causal (según la regla superior de la
Reconciliación y el ATR Audit).

**Qué SÍ puede demostrar el piloto (sin inventar):**
- Orden temporal correcto de las 5 fases (sweep→displacement→BOS→POI→retorno).
- Dirección coherente en cada eslabón.
- Presencia de anclaje HTF por timestamp (si `est_htf_ctx_fn` se pasa).
- Presencia de zona FVG/OB real vs fallback geométrico (C5).
- Cuándo el linaje NO puede demostrarse → UNKNOWN/BROKEN.

**Qué NO puede demostrar (debe quedar UNKNOWN/BROKEN, no FAIL ni PASS):**
- Identidad del nivel de liquidez barrido (re-derivable del OHLC, pero no embolsado).
- Que el displacement nació del sweep (solo orden+dir).
- Que el BOS rompió el swing del displacement (swing_id no existe).
- Qué BOS/CHOCH de HTF ancla el POI (anclaje por dir+ts, no identidad).
- Cualquier contexto macro/news (GAP-1).

**Datos del repo para ejecutar el piloto (verificados en DATA_FORENSICS):**
- `Expediente` (vía `run_sequence_traced`, atributo `phase_events`) ✅
- `MarketObject[]` de entrada ✅ (pero sin ligaduras internas usadas por la secuencia)
- Índices HTF ✅ (D1/H4/M15 en 6 forex; EURUSD+H1)
- Zonas FVG/OB ✅ (en `zone_high/zone_low` de `state`/señal)
- Timestamps ✅ (`obj.meta["time"]` por fase en el Expediente)
- Datos macro/noticias ❌ (GAP-1, fuera de alcance)

**Bloqueador de datos: NINGUNO para el piloto.** Los 6 símbolos forex con TF suficientes alcanzan
las 5 emisiones. El "bloqueo" es de **linaje causal**, no de datos ni de código.

**Recuperabilidad sin tocar engine/:** los 3 eslabones rotos (nivel de liquidez, swing roto,
parent_event POI) SON recuperables RE-DERIVANDO del OHLC de `data/raw/*.parquet` (swings + pools +
niveles), sin modificar `engine/`. Es trabajo del auditor (post-proceso de la emisión), no del motor.
Por tanto el piloto puede ejecutarse y el auditor puede enriquecer la causalidad off-line leyendo los
objetos existentes — sin tocar `engine/`, sin backtest, sin WR/PF.

---

## 4. Veredicto final

**PILOTO LISTO** (condición: el auditor emite UNKNOWN/BROKEN donde la identidad causal no se demuestre,
nunca PASS por orden temporal solo, y MACRO/NEWS = UNKNOWN siempre).

No se modifica `engine/`. No se modifica backtest. No se ejecuta el piloto en esta auditoría. No se
crea EXP-READ-001.

*Matriz de preparación del piloto. Complementa `SETUP_AUDITOR_ATR_AUDIT.md`,
`SETUP_AUDITOR_DATA_FORENSICS.md`, `SETUP_AUDITOR_RECONCILIATION.md`,
`SETUP_AUDITOR_C1_C7.md`.*