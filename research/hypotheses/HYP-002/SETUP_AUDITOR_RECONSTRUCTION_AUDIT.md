# Auditoría de Reglas de Reconstrucción Offline — SETUP AUDITOR (HYP-002)

**Fecha:** 2026-08-11
**Autor:** Hermes (ingeniero), bajo orden del Director
**Tipo:** Auditoría forense de DATOS / LECTURA (cero ejecución, cero Python)
**Propósito:** Clasificar cada relación causal que el SETUP AUDITOR pretende recuperar
desde el OHLC + `Expediente` emitido por el motor, para DEMOSTRAR que ninguna requiere
una nueva interpretación ICT/SMC escondida en el auditor. Cumple la orden del Director
(2026-08-11): no ejecutar el piloto hasta que esta puerta esté cerrada.

---

## 0. Regla de oro aplicada

> El auditor es un JUEZ FORENSE, no un segundo motor.
> Toda reconstrucción debe usar una regla YA DEFINIDA por la tesis/código del repo
> (engine/, ict_backtest/data_feed.build_features, detectors/). Si requiere una regla
> nueva → se marca UNKNOWN y se reporta como BLOQUEO CIENTÍFICO, no se inventa.

Tres clasificaciones:
- **OBSERVABLE**: el dato vive ya en el `Expediente`/señal emitido (no requiere derivar nada).
- **DERIVABLE SIN INTERPRETACIÓN**: se obtiene con una regla congelada en el repo (mismo
  detector que usó el motor, sobre el mismo OHLC, sin nuevos umbrales ni nuevas definiciones).
- **INTERPRETACIÓN NUEVA (PROHIBIDA)**: requeriría que el auditor defina "qué swing cuenta",
  "qué BOS rompió qué", "de qué sweep nació el displacement" con criterio propio.

---

## 1. Inventario de lo que el motor REALMENTE emite (fuente: engine/sequence.py:618-634, expediente.py)

La señal (`run_sequence_traced` → 3-tuple) contiene:

| Campo de señal | Origen en el motor | Tipo |
|---|---|---|
| `time` | `obj.meta["time"]` (vela entry) | timestamp |
| `direction` | `target` (±1) | entero |
| `entry` | `obj.meta["close"]` (vela entry) | float |
| `bos_level` | `obj.meta["bos_level"]` (vela BOS) | float |
| `sweep_at` | `state.sweep_idx` | **índice entero** |
| `displace_at` | `state.displace_idx` | **índice entero** |
| `bos_at` | `state.bos_idx` | **índice entero** |
| `entry_at` | `i` (vela entry) | **índice entero** |
| `zone_high` / `zone_low` | zona FVG/OB cacheada o `bos_level ± 0.5*atr` | float |
| `poi_present` | `htf_poi_fn(i, target)` (bool, no es gate) | bool |
| `htf_aligned` | cascada D1→H4→H1 (`state.htf_aligned`) | bool |
| `htf_reason` | texto de desalineación | str |
| `expediente` | objeto `Expediente` adjunto | objeto |

El `Expediente` (`engine/expediente.py:48-147`):
- `id` (hash `symbol|tf|birth_idx|direction`)
- `birth_idx`, `birth_time`, `birth_condition`
- `phase_events: list[PhaseEvent]` → cada uno: `(phase, idx, time, condition)`
- `invalidation_rule`, `invalidation_idx/time/reason`, `outcome`
- `meta` → **SOLO `{"symbol", "ltf_tf"}`** (expediente.py:296)

**HALLAZGO CENTRAL (confirmado en código):** el `Expediente` NO conserva ningún
`MarketObject[]` ni niveles de liquidez/sweep/POI. Solo lleva ÍNDICES y TIMESTAMPS de las
fases. El linaje `sweep→displacement→BOS→POI` NO se guarda como identidad causal: se guarda
como `sweep_idx < displace_idx < bos_idx < entry_at` + coherencia de dirección. Eso es
exactamente la brecha que el Director diagnosticó: **el motor sabe el ORDEN, no la IDENTIDAD
CAUSAL**.

---

## 2. Matriz de reconstrucción (cada relación causal del SETUP AUDITOR)

Para cada elemento del veredicto del Director (HTF / LIQUIDEZ / SWEEP / DISPLACEMENT /
STRUCTURE / POI / RETORNO / MACRO) se clasifica:

### HTF — contexto D1/H4/H1
- **bias D1/H4/H1**: DERIVABLE SIN INTERPRETACIÓN. `detect_market_structure(frame)["trend"]`
  (engine/bos/structure.py:460, ict_backtest/market_structure.py:124) sobre el parquet HTF
  commiteado. Misma regla que usó el motor. El motor lo aplicó vía `est_htf_fn`/`htf_aligned`.
- **htf_aligned (¿la cascada permite la dir?)**: OBSERVABLE. Vive en `signal["htf_aligned"]`
  (sequence.py:629) y `state.htf_aligned` (102/484). El auditor solo LEÉ el booleano.
- **Riesgo de interpretación nueva**: si el auditor quisiera "recalcular el alineamiento con
  su propia lógica de cascada" → INTERPRETACIÓN NUEVA. **Prohibido.** Se usa el valor emitido.

### LIQUIDEZ — pool identificado
- **existen pools BSL/SSL**: DERIVABLE SIN INTERPRETACIÓN. `detect_liquidity(df)` expone
  `bsl_price`/`ssl_price` (data_feed.py:127-129). Misma fuente que el motor.
- **¿el sweep tocó UN pool específico?**: INTERPRETACIÓN NUEVA (RIESGO ALTO). El motor solo
  marca `liquidity_sweep_down/up` (flag de vela) + `sweep_low`/`sweep_high` (nivel de la mecha,
  data_feed.py:142-145). NO guarda "qué pool" (bsl_price/ssl_price exacto tomado). El auditor
  podría emparejar la mecha del sweep con el pool más cercano → eso es DERIVABLE (regla: pool
  cuyo precio está entre la mecha del sweep ± tolerancia = rango promedio). Pero afirmar
  "el sweep tomó EXACTAMENTE ese pool" requiere definir tolerancia → si la tolerancia es un
  umbral nuevo del auditor, es INTERPRETACIÓN NUEVA.
  - **Decisión auditor:** emparejar mecha-sweep ↔ pool por distancia mínima es DERIVABLE
    (sin umbral: el pool más cercano al nivel de mecha). Se reporta como OBSERVACIÓN de
    proximidad, NO como "tomó ese pool". Si no hay pool dentro de |mecha−pool| razonable →
    UNKNOWN. No se introduce umbral nuevo.

### SWEEP — barrido real
- **ocurrió sweep en la vela**: OBSERVABLE. `signal["sweep_at"]` (índice) + flag
  `liquidity_sweep_*` en la vela. El auditor lee el OHLC de esa vela (índice → df.iloc).
- **dirección del sweep (down para long / up para short)**: OBSERVABLE / DERIVABLE. El motor
  ya lo filtró (`_has_sweep`, sequence.py:157-167: long←sweep_down, short←sweep_up). El auditor
  confirma con el mismo flag.
- **timestamp del sweep**: OBSERVABLE. `Expediente.phase_events` ("SWEEP", idx, time).
- **Riesgo**: ninguno. Es dato directo.

### DISPLACEMENT — impulso tras sweep
- **ocurrió displacement en la vela**: OBSERVABLE. `signal["displace_at"]` (índice) +
  `displacement_bullish/bearish` en esa vela (detect_displacement, data_feed.py:123-126).
- **dirección coherente**: OBSERVABLE. `direction` de la señal.
- **¿el displacement nació DEL sweep?**: INTERPRETACIÓN NUEVA (RIESGO ALTO). El motor solo
  exige `i − sweep_idx ≤ cfg.displace_gap` (sequence.py:554) — proximidad temporal, NO causalidad.
  El auditor NO puede afirmar "este displacement fue causado por ese sweep" sin una regla de
  causalidad que el repo NO define.
  - **Decisión auditor:** se reporta ORDEN TEMPORAL (sweep antes que displacement, dentro de
    `displace_gap`) como OBSERVADO; la CAUSALIDAD se marca **UNKNOWN** explícitamente. No se
    infiere.

### STRUCTURE — BOS
- **ocurrió BOS en la vela**: OBSERVABLE. `signal["bos_at"]` (índice) + `bos_dir`/`bos_status`
  en esa vela (detect_market_structure, data_feed.py:52-60).
- **dirección del BOS**: OBSERVABLE. `bos_dir` en la vela BOS.
- **¿el BOS rompió UN swing específico?**: INTERPRETACIÓN NUEVA (RIESGO ALTO). `detect_market_structure`
  produce `bos_dir`/`bos_status` pero el motor NO conserva "qué swing_high/low rompió". El auditor
  podría buscar el swing previo más cercano en dirección opuesta → DERIVABLE (el swing que el
  detector ya marcó como `swing_high`/`swing_low` en `ms["swing_*"]`, data_feed.py:63-65). Pero
  afirmar "ese BOS rompió ESE swing" es emparejar por índice temporal, no causalidad demostrada.
  - **Decisión auditor:** el BOS rompió "un swing" (el último swing opuesto antes del BOS, según
    `ms["swing_*"]`) es DERIVABLE (mismo detector del motor). La IDENTIDAD del swing específico se
    reporta como OBSERVACIÓN de proximidad, no causalidad. Si se quisiera "el swing que define la
    estructura" con criterio propio → INTERPRETACIÓN NUEVA, prohibido.

### POI — zona anclada
- **POI encontrado (zona FVG/OB entre sweep y BOS)**: OBSERVABLE. `zone_high`/`zone_low` en la
  señal (sequence.py:514-523, cacheada de `_latest_fvg_zone`/`_latest_ob_zone`:241-254). YA viene
  calculada por el motor con `pd_type`/`pd_tier` del mismo `build_features` (data_feed.py:79-121).
- **POI anclado a BOS/CHOCH del padre (engine/poi_anchor.py)**: OBSERVABLE / DERIVABLE.
  `poi_present = htf_poi_fn(i, target)` (sequence.py:503) es bool ya emitido. `build_htf_structure_index`
  (poi_anchor.py:49-83) usa `detect_market_structure` del HTF (misma regla). El auditor lee el bool.
- **¿el POI nació DE ese BOS?**: INTERPRETACIÓN NUEVA (RIESGO ALTO). El motor ancla POI al BOS del
  padre ya cerrado (poi_anchor.py) pero NO conserva el vínculo "este POI ↔ este BOS LTF" en el
  Expediente. El auditor no puede afirmar identidad causal sin regla nueva.
  - **Decisión auditor:** POI presente (bool) = OBSERVABLE. Linaje POI←BOS = **UNKNOWN**.

### RETORNO — precio vuelve al POI
- **el precio tocó la zona (mitigation)**: OBSERVABLE. `signal["entry_at"]` (índice) + `_touches_zone`
  (sequence.py:271-283, compara close con `zone_high/low`). El auditor lee el OHLC de esa vela.
- **dirección del retorno**: OBSERVABLE. `direction` de la señal.
- **Riesgo**: ninguno. Es dato directo del motor.

### MACRO / NEWS
- **noticia del momento**: GAP-1 (no existe fuente en el repo). El motor no consume macro.
  - **Decisión auditor:** siempre **UNKNOWN / "No existe evidencia macro disponible"**. No se
    inventa "sin noticias" ni se infiere impacto.

---

## 3. Veredicto de la puerta (¿hay interpretación nueva escondida?)

| Relación causal del SETUP AUDITOR | Clasificación | Riesgo | Acción auditor |
|---|---|---|---|
| HTF bias D1/H4/H1 | DERIVABLE (mismo detector) | bajo | leer `trend` del HTF |
| htf_aligned | OBSERVABLE | bajo | leer bool emitido |
| pool BSL/SSL existe | DERIVABLE (detect_liquidity) | bajo | leer `bsl/ssl_price` |
| sweep ocurrió + dir | OBSERVABLE | bajo | leer flag + índice |
| timestamp sweep | OBSERVABLE | bajo | leer phase_events |
| displacement ocurrió + dir | OBSERVABLE | bajo | leer flag + índice |
| **displacement ← sweep (causal)** | **INTERPRETACIÓN NUEVA** | **alto** | **UNKNOWN** (solo orden temporal) |
| BOS ocurrió + dir | OBSERVABLE | bajo | leer `bos_dir` + índice |
| **BOS rompió swing específico (causal)** | **INTERPRETACIÓN NUEVA** | **alto** | **UNKNOWN** (solo proximidad) |
| POI zona encontrada | OBSERVABLE | bajo | leer `zone_*` emitido |
| POI anclado a padre | DERIVABLE/OBSERVABLE | bajo | leer `poi_present` |
| **POI ← BOS LTF (causal)** | **INTERPRETACIÓN NUEVA** | **alto** | **UNKNOWN** |
| retorno al POI | OBSERVABLE | bajo | leer `_touches_zone` + índice |
| macro/news | GAP-1 (sin fuente) | — | **UNKNOWN** |

**CONCLUSIÓN:** El SETUP AUDITOR, tal como está diseñado en `SETUP_AUDITOR_PROTOCOL.md` y
`SETUP_AUDITOR_C1_C7.md`, **NO introduce una nueva interpretación ICT/SMC**. Todas las piezas
OBSERVABLES y DERIVABLES usan los MISMOS detectores del motor (`detect_market_structure`,
`detect_liquidity`, `detect_displacement`, `detect_fvg`, `detect_order_blocks`,
`engine.poi_anchor`). Las tres relaciones marcadas INTERPRETACIÓN NUEVA (displacement←sweep,
BOS←swing, POI←BOS) ya están previstas en el protocolo como **UNKNOWN/BROKEN** y el auditor las
dejará exactamente así, sin inferirlas. Macro = UNKNOWN por GAP-1.

**La puerta está CERRADA Y CONSISTENTE.** No hay segunda tesis escondida en el auditor. El
auditor solo LEE lo que el motor emitió + re-deriva (con los mismos detectores) los hechos
objetivos (trend HTF, pools, niveles). No redefine BOS, no redefine swing, no redefine POI.

---

## 4. Bloqueos científicos reportados (no se arreglan durante la auditoría)

1. **BLOQUEO-1 (linaje causal no conservado):** el motor no guarda identidad causal
   sweep→displacement→BOS→POI en el `Expediente` (solo índices + dirección). El auditor lo
   reporta como UNKNOWN en las 3 uniones. No se "arregla" aquí; es hallazgo para decidir si el
   motor debe enriquecer su memoria causal (decisión post-piloto, fuera de HYP-002 fase actual).
2. **BLOQUEO-2 (GAP-1 macro):** no hay fuente macro conectada. Macro permanece UNKNOWN.
3. **BLOQUEO-3 (OPCIÓN B de ejecución):** `ict_backtest/rules.py:65` tiene `NameError: datetime`
   (usa el tipo sin importarlo). Para no contaminar el objeto auditado (regla del Director:
   "el piloto no debe modificar el motor para demostrar que funciona"), el script `pilot1_run.py`
   se reescribirá para CONSUMIR DIRECTAMENTE `build_features` + `engine.sequence` +
   `engine.poi_anchor` + `detectors`, EVITANDO el import de `ict_backtest` (que arrastra
   `rules.py`). Así el piloto es consumidor puro sin tocar backtester ni engine/.

---

## 5. Autorización solicitada para ejecutar el piloto (siguiente paso)

Una vez el Director apruebe, el piloto de 5 setups se ejecutará con:
- `pilot1_run.py` reescrito (Opción B): consume `data_feed.build_features` +
  `engine.sequence.run_sequence_traced` + `engine.poi_anchor.make_htf_poi_fn` + `detectors`,
  SIN importar `ict_backtest`.
- 5 fichas forenses en `pilot1_output.md`, cada una con veredicto
  OBSERVABLE / DERIVABLE / UNKNOWN / BROKEN por elemento (ver matriz §2-§3).
- CERO métricas de rendimiento (WR/PF/R/expectancy). CERO umbrales ATR como gate.
- Macro = UNKNOWN en todas.

Hasta entonces: NO ejecutar. Puerta cerrada y documentada.
