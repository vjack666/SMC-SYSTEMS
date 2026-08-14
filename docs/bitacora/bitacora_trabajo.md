# Bitácora de Trabajo — SMC-SYSTEMS

Registro cronológico de sesiones, decisiones y estado del proyecto. Fuente de
verdad viviente junto con AGENTS.md y la tesis (docs/tesis/). El backtest es
desechable; el motor (engine/) es permanente.

## 2026-08-05 — Sesión: cierre de brechas B/A1 + orden de documentación

### Decisiones del trader humano (Ruben)
- Cuenta correcta del proyecto: **FundedNext** (ForexClub descartado).
- Auto-arranque con Windows **ELIMINADO**: el sistema corre solo bajo demanda
  (pedir "dame el bias de hoy" / "analiza la gráfica"). Hermes.lnk movido a
  `scripts/DisabledStartup/`.
- **Ley arquitectónica**: motor (engine/) = lectura del humano hecha código,
  PERMANENTE y autónoma; backtest (ict_backtest/) = desechable, solo demuestra
  la tesis. El backtest puede importar el motor; el motor NUNCA importa el
  backtest. El observador en vivo lee del motor, no del backtest.
- Ante duda: "qué camino escogería el trader humano y le diría al ingeniero que
  construya" — la lógica del humano va al MOTOR, el backtest solo la demuestra.

### Trabajo ejecutado (verificado con ejecución real)
1. **Recuperación de archivos**: 164 archivos borrados en la historia de git,
   de carpetas vivas (app_observador/, detectors/, ict_backtest/, scripts/,
   tests/, ml/, strategy/, adapters/), restaurados a su carpeta original vía
   `git checkout` del último commit donde existieron. 0 fallidos.
   - Fuera de alcance (purga probable de Ruben, no tocados): docs/ (91),
     modules/ (85), smc_successor/, automation/ — 176 archivos.
2. **Motor — brecha B (POI anclado) CERRADA**:
   - `engine/poi_anchor.py` (nuevo): `build_htf_structure_index` +
     `make_htf_poi_fn(i, target)->bool`. Ancla POI a BOS/CHOCH del TF padre ya
     cerrado, con anti look-ahead por timestamp. Solo importa `engine.bos`/
     `engine.bias` (Ley OK).
   - `engine/htf_narrative.py`: `build_htf_narrative` marca `poi["anchored"]`.
   - `tests/test_engine_poi_anchor.py`: 5 tests (passed).
3. **Motor — brecha A1 (3 capas reales) CERRADA**:
   - `engine/plan.py` (nuevo): `build_context_stack` + `top_down_allows_trade`
     + `snapshot_tf` + `dealing_range_pd`. Lectura top-down D1→H4→H1→M15 con
     premium/discount y anti look-ahead. Usa `engine.bos`, NO importa backtest.
   - `engine/data_feed.py` (nuevo): `load_frames` del motor (lee parquet crudos
     de data/raw). El motor carga sus propios datos.
   - `ict_backtest/v2/context_mtf.py`: re-exporta desde `engine.plan` (el
     backtest CONSUME el motor, sin duplicar).
4. **Observador desacoplado del backtest**:
   - `app_observador/core/engine.py::_canonical_plan` ahora lee del motor
     (`engine.data_feed` + `engine.plan` + `engine.htf_narrative`), no de
     `ict_backtest.canonical.latest_plan`. Verificado con ict_backtest BLOQUEADO:
     el observador corre sin tocar el backtest.
   - `grep -r ict_backtest app_observador/` → 0 imports reales.
5. **Datos**: `_data_legacy.py` tenía rango de descarga hardcodeado a 2026-07-07
   → corregido a `datetime.now()`. `update_mt5_data.py` (MERGE) subió EURUSD
   D1/H4/H1 a 2026-08-05. M15 sigue corto (ver pendiente).
6. **Tests**: `pytest tests/test_engine_*.py` → **79 passed, 0 failed**.

### Reordenamiento de documentación (esta sesión)
- AGENTS.md CAVEAT R6 corregido: brechas B y A1 ya CERRADAS en el motor.
- Creada `docs/bitacora/bitacora_trabajo.md` (este archivo).
- MD desactualizados movidos a `docs/_descartado/` (reversible): ver
  `docs/_descartado/INDICE_DESCARTE.md`. No se tocó la tesis.

### Estado actual del motor (permanente)
- COMPLETO: bias (D1/H4/H1), bos/structure, order_block, fvg_poi,
  liquidity_levels (BSL/SSL), dealing_range (EQ/premium-discount),
  htf_narrative, poi_anchor (ancla), plan (top-down 3 capas), data_feed.
- PENDIENTE en motor: exec fino M5/M1; fix sesgo NEUTRAL perpetuo en rangos
  (`engine/bias/narrative.py` `_bias_from_swings`, bug T8).

### Pendiente / bloqueos
- MT5 logueado en **MetaQuotes-Demo** (no cuenta real FundedNext). Hoy funcionó
  para velas de hoy; para histórico real del challenge hay que loguear FundedNext.
- EURUSD_M15.parquet no actualizado a 2026-08-05 (solo D1/H4/H1). Falta correr
  update de M15 para que el plan en vivo vea el día de hoy.
- Sin commit/push (regla Ruben).

### Roadmap recuperado y punto actual (agente humano → ingeniero)
- El repo NO tenía roadmap vivo (docs/plan/ purgado 2026-08-03). 21 roadmaps
  históricos recuperados selectivamente del commit d0a5f20 a
  `docs/planificacion/_roadmap_historico/` (solo hitos/fases/decisiones; SIN
  código de backtest ni libro 13), marcados HISTÓRICOS (no fuente de verdad).
- Diff honesto motor vs roadmap: `docs/planificacion/_roadmap_historico/PUNTO_DEL_ROADMAP_2026-08-05.md`.
- **Punto del roadmap (vista motor):** lectura completa (sesgo, estructura,
  OB/FVG, liquidez, dealing range, narrativa HTF, POI anclado, plan top-down 3
  capas) CERRADA. Ejecución fina PENDIENTE en motor: B2 (exec M5/M1), C2/C3/D1
  (setups), E1 (trade mgmt), y bug T8 (sesgo NEUTRAL en rango). El backtest
  estaba más adelantado en ejecución, pero es desechable; el motor es lo
  permanente y es donde falta subir esas capas.

### Trabajo de la tarde (2026-08-05) — B2 (exec fina) + aislamiento POI del backtest

#### Decisiones del trader humano (Ruben)
- "Borra la duplicación de POI en el backtest; el motor es única fuente; el
  backtest solo lo consume. No puede haber un motor para backtest y otro para
  trader real."
- Confirmó **Opción B**: borrar TODO el subsistema HTF del backtest
  (`HtfPdIndex`, `zone_authority`, `poi_anchor`/`poi_filter`/`poi_anchor_motor`)
  y usar `engine.poi_anchor`. El `zone_authority` (tier/stacking) era ornamento
  del backtest; si se quiere, debe SUBIR al motor, no volver al backtest.

#### Trabajo ejecutado (verificado con ejecución real)
1. **B2 (ejecución fina M5/M1) ESCRITA** en `engine/execution.py`:
   - `fine_execution(ms, t, direction, exec_tf="M5", rr=3.0)`: entry = breakout
     del último swing high (LONG) / low (SHORT) en el TF de ejecución; SL = mecha
     del swing opuesto (estructural, no arbitrary); TP = RR 1:3. Anti look-ahead
     por `time`. Solo usa `engine.bias._swing_points` / `engine.bos` (Ley OK).
   - Bug corregido: fallback `ms.get(exec_tf) or ms.get("M15")` → si `exec_tf`
     presente pero vacío, cae a M15 sin crash.
   - `tests/test_engine_execution_b2.py`: **6 tests passed** (zigzag alcista/bajista,
     anti look-ahead, fallbacks).
   - NOTA: B2 está escrito y testeado pero **NO cableado al backtest** (Ruben:
     "está muy adelantado, deja un agente escribiendo eso"). Pendiente cablear a
     `canonical`/`sequence`.
2. **Aislamiento POI (Opción B) CERRADO**:
   - `engine/poi_anchor.py`: añadido `poi_present()` wrapper (anota bool, sin
     lógica propia del backtest).
   - Recableado del backtest para consumir SOLO `engine.poi_anchor`:
     `ict_backtest/canonical.py`, `sequence.py`, `run_backtest.py`,
     `v2/strategy_mtf.py`, `plan_attach.py` — quitaron `HtfPdIndex`/`zone_authority`/
     `poi_filter`/`poi_anchor_motor` y ahora usan `make_htf_poi_fn` /
     `build_htf_structure_index` / `poi_present` del motor.
   - **BORRADOS** los módulos duplicados del backtest: `poi_anchor.py`,
     `poi_anchor_motor.py`, `poi_filter.py`, `htf_pd_index.py`, `zone_authority.py`.
   - Tests del backtest que testeaban ese subsistema eliminados (desechable; el
     motor lo cubre con `test_engine_poi_anchor.py`): `test_a_poi_anchored`,
     `test_e_poi`, `test_fase_c0/c1_c3/c2/c4`, `test_fase_c_production_wiring`,
     `test_poi_anchor_motor`.
   - Verificación: `pytest` motor **14 passed** (poi_anchor 5 + plan_pd 3 +
     execution_b2 6); import del backtest OK; backtest HTF EURUSD 3M corrió
     exit 0, 3247 eventos, n_orders=1, pipeline íntegro con POI del motor.
3. **Backtest HTF 3M (demostración de tesis, NO edge)**: EURUSD D1→H4→H1→M15,
   clock M15.
   - `live_structure.csv`: 3247 eventos de estructura (FVG/BOS/CHOCH en cada TF,
     anclados por el motor a BOS/CHOCH padre ya cerrado en misma dirección).
   - n_orders=1, filter ok=1, trade SL -1.02R. Veredicto reporte: "implementación
     parcial — NO interpretar como edge". El bajo volumen de setups es del motor
     de secuencia M15 estricto (sweep→displace→BOS→retorno), no del POI.

#### Estado actual del motor (actualizado)
- COMPLETO: bias, bos, order_block, fvg_poi, liquidity_levels, dealing_range,
  htf_narrative, poi_anchor (ancla), plan (top-down 3 capas), data_feed,
  execution (B2, exec fina M5/M1 — módulo escrito, NO cableado a backtest).
- PENDIENTE en motor: cablear B2 al backtest.
- Backtest: SIN lógica propia de POI (consumidor puro del motor). Ley cumplida:
  `engine/` nunca importa `ict_backtest/`.

#### 2026-08-06 — T8 CERRADO (sesgo NEUTRAL perpetuo en rangos)

**Bug (raíz):** `_bias_from_swings` (`engine/bias/narrative.py`) agrupaba los
swings en "tramos" de misma polaridad y votaba los últimos `trend_window`. En
H1 real (EURUSD) los swings alternan LL/HH perpetuamente => empate 2/2 =>
NEUTRAL SIEMPRE. Medido: **100% NEUTRAL en EURUSD H1 real** (motor mudo).

**Fix:** criterio de trader humano HH+HL / LH+LL — compara el último swing
high con el previo y el último swing low con el previo; vota por los últimos
`trend_window` pares de swings confirmados (default subido de 4 a 6 para que
el sesgo refleje la tendencia dominante, no el micro-movimiento spot). En
rango (SH/SL mixtos) sigue NEUTRAL (contexto, no anula el setup — tesis §1).

**Verificación (ejecución real):**
- Sintético: uptrend→BULLISH, downtrend→BEARISH, range→NEUTRAL (3/3 OK).
- EURUSD H1 real (ventanas de 50v muestreadas cada 200v): NEUTRAL bajó de
  100% → **22.4%**; BULLISH 35.6%, BEARISH 42.0% (reparto sano, motor activo).
- `pytest tests/test_engine_*.py` → **112 passed, 0 failed** (los tests de
  bias/narrativa se actualizaron: los generadores viejos solo producían un
  lado de swings y asumían el criterio bugui; ahora usan random-walk
  determinista con drift para HH+HL/LL reales).

#### 2026-08-06 — Actualización de datos a 2026-08 (HistData append)

**Estado previo:** M1/M5 solo hasta 2026-06-26; M15/H1/H4/D1 hasta 2026-08-05
(vía MT5, según sesión previa). El script `download_histdata_m1.py` REESCRIBE
todos los parquet desde `--from-year` => usar 2022 pierde millones de barras y
usar 2026 borra el histórico 2022-2025 de M1/M5.

**Fix de flujo:** creado `scripts/update_histdata_append.py` — append incremental
y quirúrgico: lee M1 existente, descarga SOLO los meses posteriores a su última
fecha desde HistData, concatena+dedup, y resamplea SOLO los TF pedidos (por
defecto M1 M5). No toca M15/H1/H4/D1 (que ya estaban al día vía MT5).

**Ejecutado (EURUSD, --tfs M1 M5):**
- M1: 1.619.941 → 1.652.474 barras (hasta **2026-07-31**).
- M5: 325.433 → 331.972 (hasta **2026-07-31**).
- M15/H1/H4/D1: sin cambio, siguen en **2026-08-05**.

**Límite real:** HistData gratis aún NO tiene 2026-08 (retrazo 1-2 días; hoy
2026-08-06). M1/M5 no pueden llegar a agosto hoy vía HistData. M15 (08-05) se
completa a 08-06 vía MT5 o cuando HistData publique agosto.

**Verificación:** `pytest tests/test_engine_*.py` → 112 passed; backtest importa OK.

#### 2026-08-06 (2) — Cableado de B2 (execución fina M5/M1) al backtest

**Estado previo:** `engine/execution.py` (módulo B2) ya existía y `canonical.evaluate_signals`
lo llamaba, pero el SL se calculaba con swings del exec TF (no la mecha del sweep) y
`fine_execution` NO recibía el sweep → los tests de EFECTO (`test_b2_exec_tf.py`) fallaban
(SL no anclado al sweep del exec TF; `Po3MotorConfig` no recibía `exec_tf`).

**Cambios (verificados con ejecución real):**
1. `engine/execution.py`: `fine_execution` ahora acepta `sweep_ts=None` opcional.
   - Sin `sweep_ts`: entry/SL desde swings del exec TF (contrato de módulo,
     `test_engine_execution_b2.py`).
   - Con `sweep_ts`: **SL anclado a la mecha del sweep del exec TF** (libro 18: SL
     estructural SIEMPRE en el TF más fino). Sin swings (datos planos) el entry =
     toque de zona (close de la vela del entry). Mate elegido: `STRUCT_SL_BUFFER_RANGE=0.3`.
   - No importa `ict_backtest` (Ley OK): usa `_swing_points` del motor y la mecha
     inyectada `sweep_low`/`sweep_high` que el backtest pasa en el frame.
2. `ict_backtest/canonical.py` (línea ~296): `evaluate_signals` ahora pasa
   `sweep_ts = ltf_df.iloc[s["sweep_at"]]["time"]` a `fine_execution`. El SL del
   exec TF reancla entry/SL/TP y se propaga a `Po3MotorConfig(exec_tf=...)`.
3. `tests/test_b2_exec_tf_wiring.py`: fixture `fake_evaluate` corregido para
   respetar `return_phase_seen` (el mock roto rompía 3 tests de wiring — no era
   fallo del cableado).

**Verificación (ejecución real):**
- `tests/test_engine_execution_b2.py` + `test_b2_exec_tf.py` + `test_b2_exec_tf_wiring.py`
  → **14 passed** (módulo + efecto + wiring).
- Batería motor + backtest v2 + B2 → **126 passed, 0 failed**.
- Los 9 errores de COLECCIÓN en `tests/` son PREEXISTENTES (imports rotos de APIs
  que cambiaron: `app_observador.ui.autopilot_widget._PHASES`, `apply_trade_management`,
  `filter_signals_by_model`, `build_signals_from_frames`, `add_bollinger`; y
  `XAUUSD_D1.parquet` faltante). No son de este cambio.
- Efecto real EURUSD (backtest 1 mes) en `results/b2_effect_real.txt` (corriendo en
  background; el runner_monitor no captura stdout de la ventana hija).

**Efecto real (backtest EURUSD 1 mes, window_months=1, session proc_9c027bb3f037):**
- SIN exec_tf: 0 trades, 0 señales. CON exec_tf='M5' (B2): 0 trades, 0 señales.
- Ambos 0 señales → el funnel muere en sweep→displace→BOS (detection), ANTES de
  llegar a la ejecución fina. B2 es NEUTRO aquí: no hay señales que reanclar.
- Coherente con CAVEAT AGENTS.md: motor backtesteado = versión simplificada de la
  estrategia objetivo; falta pulir detección en datos reales. B2 está cableado
  (lo prueba test_call_site_uses_exec_tf_for_po3_config), pero su efecto solo se
  mide cuando el motor detecta setups. No es bug de B2.
- Cuello de botella: `features en 551s` (build_features sobre M15 de 1 mes). Explica
  por qué el backtest previo se cortó a los 60s.

#### 2026-08-06 (3) — Completar 2026-08 vía MT5 (Demo) append quirúrgico

**Contexto:** HistData gratis aún NO publica 2026-08 (retrazo 1-2 días). El usuario
pidió usar MT5 para completar la data faltante. MT5 responde con cuenta
**MetaQuotes-Demo** (login 10011586708), NO FundedNext (la ruta en el proyecto apunta
a FundedNext pero la cuenta que conecta es Demo; se documenta). Datos Demo = en vivo.

**Riesgo evitado:** `update_mt5_data.py` baja DESDE 2020 y al mergear keep="last"
pisaría el histórico de HistData (1.6M barras M1). Se creó `scripts/update_mt5_append.py`
que baja SOLO la punta (agosto 2026) y la appende, conservando 2022-2025.

**Ejecutado (EURUSD, append MT5 Demo):**
- M1: 1.652.474 → 1.657.649 (hasta **2026-08-06 14:14**).
- M5: 331.972 → 333.007 (hasta **2026-08-06 14:10**).
- M15: 114.232 → 114.237 (hasta **2026-08-06 14:00**, antes 08-05).
- H1: 41.014 → 41.019 (hasta **2026-08-06 14:00**, antes 08-05).
- H4: 10.264 → 10.270 (hasta **2026-08-06 12:00**, antes 08-05).
- D1: 1.714 → 1.715 (hasta **2026-08-06 00:00**, antes 08-05).

**Histórico conservado:** M1/M5 arrancan 2022-01-02; H1/H4/D1 arrancan 2020-01-02.
MT5 Demo tiene agosto desde el 03 (limita historia); cubre el agujero julio→agosto.

**Nota calidad:** datos Demo pueden diferir de reales en la frontera julio/agosto
(artefacto menor de continuidad). El backtest usa estos datos; transición jul/ago
puede verse afectada levemente.

**Verificación:** `pytest tests/test_engine_*.py + test_b2_*` → 120 passed, 0 failed.
Todos los TF EURUSD llegan a 2026-08-06.

#### 2026-08-06 (4) — T9: sesgo HTF por ESTRUCTURA VIGENTE (humano, sin conteo fijo)

**Contexto (auditoria de 2 agentes):** el sesgo de un TF se derivaba de un
voto por pares sobre `trend_window=6` swings con `lookback=2` (T8). Eso es
anti-humano: el trader no cuenta velas. Ademas habia DISPARIDAD INTERNA:
`compute_htf_bias` (narrative) decia D1 NEUTRAL, pero `detect_market_structure`
(bos) decia D1 BULLISH. El sesgo diario estaba MUERTO (94% NEUTRAL audit previo)
y `_compose_htf_bias` cedia autoridad a H1. Hoy eso derivo direccion BEARISH
falsa desde H1 contra D1/H4 alcistas.

**Criterio nuevo (TRADER HUMANO):** el sesgo de un TF es la direccion del ULTIMO
BOS/CHOCH cuyo estado es `active` (no invalidado) en ese TF. Sin evento activo
=> NEUTRAL (rango autentico, no fallback de ventana). D1 = autoridad raiz via
`_compose_htf_bias` (ya la respetaba; antes D1 salia NEUTRAL por el bug).

**Cambios:**
- `engine/bias/narrative.py`: `_bias_for_frame` ahora reusa
  `engine.bos.structure.detect_market_structure` (unica fuente de estructura,
  lazy import para no ciclar). Eliminados `_bias_from_swings` y
  `_unique_swing_values` (criterio de conteo fijo). Sin `trend_window`,
  sin `lookback=2`. Recorta cola (`tail=400`) por costo de detect_market_structure.
- `tests/test_engine_bias.py`: helpers `_zigzag_*` (ruidosos) -> `_up_clean`/
  `_down_clean` (monotonos, sesgo univoco); `test_rango_estable` prueba
  estabilidad sin importar `swing_lookback`; `test_pocos_datos` usa laterales;
  `test_ffill_a_h1` incluye columna `open` (detect_market_structure la requiere).

**Efecto real (EURUSD 2026-08-06):**
- ANTES (T8): D1 NEUTRAL -> direccion BEARISH (cedia a H1).
- AHORA (T9): D1 BULLISH -> direccion BULLISH (D1 manda). Consistente con
  `detect_market_structure` (que ya decia D1 BULLISH). Disparidad interna CERRADA.
- H1 sigue BEARISH (pullback en tendencia mayor); gate bloquea por
  `h1_opposes_long` (correcto: H1 no alinea con D1/H4 alcistas).

**Verificacion:** `pytest tests/test_engine_*.py + test_b2_*` -> 120 passed, 0 failed.
request_daily_bias y _demo_htf_today coherentes (D1 BULLISH en ambos).

#### 2026-08-06 (5) — T9.1/T9.2/T9.3: CHOCH persistente + marcas del trader + coherencia del gate

**T9.1 (CHOCH no se pierde en HTF):** el sesgo de un TF es la direccion del
ULTIMO CHOCH activo (memoria de giro que vive hasta que el precio cruza su
nivel); si no hay CHOCH activo, la del ULTIMO BOS activo; sino NEUTRAL.
`engine/bias/narrative.py::_bias_for_frame` recorre el frame y toma el evento
de mayor indice temporal. El CHOCH activo SIEMPRE manda sobre el BOS (si el
BOS lo hubiera invalidado, choch_status seria "invalidated" y no contaria).

**T9.2 (marcas del trader):** `engine/bos/structure.py` expone 4 niveles por
evento (geometria pura, sin indicadores): `bos_proj_level` (pico opuesto que
el precio debe romper para hacer BOS), `bos_inval_level` (cruzar atras = BOS
muerto), `choch_proj_level` (nivel del BOS contrario que confirma el giro),
`choch_inval_level` (nivel que mata al CHOCH). Es lo que el trader marca en
pantalla: "aqui espero el BOS" y "aqui se invalida".

**T9.3 (coherencia del gate):** `engine/plan.py::snapshot_tf` / `ltf_structure_at`
AHORA leen el sesgo por ESTRUCTURA (`_bias_from_frame`: ultimo BOS/CHOCH activo
del frame cerrado hasta t), no la etiqueta de swing `trend` que dejaba RANGING
en tendencia con correcciones. Antes el gate bloqueaba por `d1_ranging` aunque
el sesgo humano (CHOCH activo) dijera BULLISH -> contradiccion. Ahora sesgo =
trend del stack = lo que lee el gate (una sola fuente de verdad). Feeds sin
anotar caen a `_trend_of` (regresion cero).

**Efecto real (EURUSD 2026-08-06, demo):** D1/H4/H1/M15 = BULLISH alineado.
Gate ya NO bloquea por `d1_ranging`; bloquea por `long_in_premium` (D1/H4 en
PREMIUM) -> CORRECTO y humano (no comprar caro). Marcas del trader visibles:
D1 BOS alc pico 1.14710, CHOCH alc rompe 1.14177 muere 1.14609; etc.

**Verificacion:** `pytest tests/test_engine_*.py + test_engine_plan.py + test_b2_*`
-> 123 passed, 0 failed. Nuevo tests/test_engine_plan.py fija T9.3.

#### Pendiente / bloqueos
- Sin commit/push (regla Ruben).
- MT5 = cuenta Demo (no FundedNext).
- B2 efecto real: 0 señales en 1 mes; medible al calibrar deteccion.
- POI en request_daily_bias sigue "SIN ANCLAR" (ese script no activa el anclaje;
  el stack completo si lo hace). Unificar la lectura del script simple opcional.

#### 2026-08-06 (6) — T9.4/T9.5/T9.6/T9.7: cierre de revisión HTF (fidelidad a tesis)

**Objetivo:** leer la tesis (docs/tesis/HALLAZGOS_*.md) y contrastar contra el
motor; cerrar cada regla de oro ICT que faltara. Resultado: motor HTF fiel a
la tesis en TODOS los frentes que los 2 docs piden.

**T9.4 (CHOCH muere por cruce de BOS roto, tesis §estructura):**
`engine/bos/structure.py::_track_structure` ahora recibe `inval_level`
(= `choch_proj_level`, el nivel del BOS contrario que ROMPIÓ). El CHOCH se
invalida cuando el precio cruza ESE nivel (no la mecha de la vela del CHOCH).
Antes el CHOCH vivía de por vida. Verificado H1: CHOCH invalidados 0% -> 52%.
Además el evento original queda `invalidated` (no solo la vela del cruce) para
que `_bias_from_frame` no lo cuente como vivo.

**T9.5 (sesgo HTF solo cuenta BOS real, tesis §3/§7.0):**
`_bias_from_frame` (engine/plan.py) ignora BOS sin `bos_real` (displacement).
La tesis §7.0 dice que un BOS cuenta solo con empujón decidido; el motor YA
calculaba `bos_real` pero el sesgo lo ignoraba. Evidencia H1: 24/73 BOS activos
eran ruido. Impacto stack real: H4 reveló BEARISH (antes BULLISH por BOS de
ruido) -> gate bloquea ambas direcciones por desalineación D1/H4.

**T9.6 (BOS vigente único, superseded):**
`_track_structure`: un BOS nuevo en la MISMA dirección marca al anterior como
`superseded` (el humano mira el vigente, no acumula). Antes el motor solo
descartaba por cruce -> 21.480 BOS `active` en M15 (98% basura histórica). Tras
T9.6: M15 21.480 -> 394, H1 7.901 -> 210, H4 1.959 -> 49, D1 338 -> 4. El
backtest ahora itera ~400 en vez de 21k (probable causa de que el backtest real
se colgara / diera 0 señales: ahogado en eventos).

**T9.7 (CHOCH requiere BOS real detrás, tesis §7.0, extensión T9.5):**
`_bias_from_frame` ignora CHOCH cuyo BOS contrario roto NO es `bos_real`.
Medición: 152 CHOCH espurios en H1, 141 en M15 (~9-10%). Regresión cero si el
frame no trae `bos_real`. Impacto hoy: stack igual (el CHOCH vigente ya era
real), pero el motor queda protegido contra CHOCH espurios que mandarían sesgo.

**HALLAZGO CLAVE (§3 ya estaba hecho):** la tesis §3 pide "swings confirmados
por rotura, no ventana fija". `+_swing_points` (engine/bias/narrative.py:102)
YA lo implementa: el swing es extremo local (`low[i]<low[i-1] and low[i]<low[i-2]`)
y el docstring confirma filosofía de rotura. El `swing_lookback=5` de
StructureConfig es INERTE para swings (el loop usa i-1/i-2 fijos). O sea la
"madre de todas" (raíz del ruido de BOS/CHOCH espurios) YA estaba cerrada; lo
que faltaba era el filtro de CALIDAD (T9.5/6/7), que es lo que se cerró hoy.

**Estado del motor HTF (al cierre de T9):** fiel a la tesis en todos los frentes
de los 2 docs: sesgo por estructura vigente (T9.1/3), CHOCH persistente-pero-no-
eterno (T9.4), CHOCH manda (T9.1), solo BOS/CHOCH REALES (T9.5/7), BOS vigente
único (T9.6), marcas del trader (T9.2), PD premium/discount, OTE, sweep,
liquidez BSL/SSL, POI anclado (en motor, desactivado por defecto). 123 passed.

**Verificación:** `pytest tests/test_engine_*.py + test_engine_plan.py + test_b2_*`
-> 123 passed, 0 failed. tests/test_engine_bos.py::test_bos_invalidated_on_level_cross
actualizado al contrato superseded (T9.6): el BOS reemplazado queda superseded,
el vigente se invalida por cruce (tesis).

#### 2026-08-06 — HOJA DE RUTA (post T9, vista motor)

1. **Relanzar backtest EURUSD con motor ya limpio (T9.4/5/6/7).** Sospecha: el
   backtest real daba 0 señales / se colgaba porque iteraba 21k BOS `active`
   (T9.6 los bajó a ~400). Re-medir funnel (¿sigue muriendo en detección?).
   Usar window_months=1 (backtests >1 mes mueren por SIGTERM).
2. **Activar POI anclado en el gate (brecha B ya en motor).** `engine/poi_anchor.py`
   está escrito y testeado pero DESACTIVADO por defecto (AUDITORÍA_POI_REPORT).
   Cablear `htf_poi_fn` al `top_down_allows_trade` para que el OB deba estar
   anclado al BOS del padre (tesis: POI no al azar).
3. **Evaluar LTF / scalping / intradía (PO3, pipeline M15).** El motor ya tiene
   `signals/po3.py`, `signals/pipeline.py`, exec fina B2 (M5/M1). Falta decidir
   si el stack operativo usa eso para entradas de intradía (no solo HTF).
4. **Calibrar detección en datos reales** (continuación de backtest 0-señales):
   umbrales de BOS quality, ventana de confirmación, tolerancia de CHOCH.
5. **Datos:** re-correr `update_histdata_append.py` cuando HistData publique
   2026-08 (fuente primaria M1/M5; hoy vienen de MT5 Demo).

**Roadmap NUNCA toca el backtest como fuente de decisión** (Ley): el backtest
solo demuestra el motor. Toda nueva lógica de estrategia va al MOTOR.

#### Pendiente / bloqueos
- Sin commit/push (regla Ruben) — pendiente aplicar T9.4–T9.7 + bitácora.
- MT5 = cuenta Demo (no FundedNext).
- B2 efecto real: 0 señales en 1 mes; medible al calibrar detección (ver hoja de ruta 1-4).
- POI en request_daily_bias sigue "SIN ANCLAR" (ese script no activa el anclaje).

#### 2026-08-06 (7) — AUDITORÍA DE SECUENCIA / FUNNEL (validación del detector de setup HTF)

**Pedido del trader:** no es backtest de P&L. Es demostrar que el motor, vela a
vela, RECONOCE cuando se arma el patrón ICT canonico (sweep→displace→BOS→
retorno a POI anclada) y dice "setup completo de HTF". Medir EN QUÉ FASE del
patrón se pierde (funnel), no simular entradas.

**Qué es (y qué NO es):** AUDITORÍA DE SECUENCIA / FUNNEL = validación del
detector. Consumidor PURO del motor (`engine.sequence.run_sequence_traced` vía
`evaluate_signals`). NO reimplementa detección (Ley). NO calcula P&L (eso es el
backtest de entradas, capa posterior). El término "backtest" NO aplica aquí.

**Script:** `scripts/audit_sequence_funnel.py` (nuevo). Carga EURUSD, corre el
detector del motor con HTF real + POI anclado (`enable_pd_index=True`), reporta
`phase_seen` + setups completos por mes. Recorta a D1/H4/H1/M15 (SIN M1/M5:
el build de objects sobre 1.6M velas M1 colgaba el proceso a 1500s timeout;
quitar M1/M5 lo baja a ~210s).

**Resultado real (EURUSD, 1 mes, 2026-07-31→08-06, motor ya limpio T9):**
```
FUNNEL (nacen -> completan):
  SWEEP   : 23
  DISPLACE: 22  (95.7% de SWEEP)
  BOS     : 19  (82.6% de SWEEP)
  ENTRY   : 19  (82.6% de SWEEP)
Setups completos (ENTRY): 10  (1 en jul-31 + 9 en ago)
Muestra: 2026-07-31 07:15, 2026-08-03 07:15/08:15/09:15, 2026-08-04 14:45...
```
En `results/audit_funnel_1m.txt`.

**Veredicto:** el detector ENCIENDE. El funnel no muere en ningún eslabón
(caída suave y real 23→22→19→19, mercado normal). Se arman ~10 setups
completos de HTF por mes (~2-3/semana) — coherente con ICT: "no todos los
días, pero cada cierto tiempo sí". Confirma la hipótesis de que T9.6 (BOS
vigente único, de 21k→~400) desatascaba el backtest: el detector ya no se
ahoga en eventos. Esto es la PRUEBA de que la capa HTF del motor es sólida
como FILTRO y como RECONOCEDOR de patrón; el backtest de ENTRADAS (P&L) es la
siguiente capa, aún no construida.

#### 2026-08-06 (8) — SDD LTF + Fase 1 (exec fino M5/M1) EJECUTADA

**Contexto:** el HTF esta al 100% (sesion previa). El usuario pidio SDD de la
capa LTF y arrancar el trabajo. Se escribio docs/tesis/SDD_LTF_ENTRY_LAYER.md
(con Fases 1-5: exec fino M5/M1, Trade Management, Silver Bullet+PO3, OTE,
unificar KZ) y se ejecuto la Fase 1.

**Fase 1 — bug aislado y fix (exec fino M5/M1, B2):**
- fine_execution (engine/execution.py) con exec_tf=M5 daba 6 ok / 4 fallos
  sobre 10 senales reales EURUSD (con POI anclado). Los 4 fallos eran TODOS
  sl_invalid_long: el SL por mecha de sweep quedaba >= entry por COMPRESION
  de M5 (la mecha del sweep queda muy cerca del entry en el TF fino).
- El backtest real que daba 0 senales era por FALTA de enable_pd_index=True
  en la llamada (motor sin POI -> 0 setups), NO por el M5.
- Fix (commit 03c8539): si el SL por mecha de sweep queda invalido en el
  exec TF fino, fine_execution hace FALLBACK al ultimo swing opuesto del exec
  TF (estructura real, libro 18: SL SIEMPRE en estructura, nunca arbitrary).
  Ley respetada (engine/ no importa ict_backtest/).
- Test nuevo test_b2_fallback_sweep_sl_invalid_uses_swing: bateria B2 =
  15 passed. Sin romper tests existentes.

**Auditoria de secuencia (re-confirmacion):** la seccion (7) de arriba SON los
numeros vigentes (misma corrida, datos 2026-08-06). Hoy se re-intento correr
audit_sequence_funnel.py y NO termino en 400s (timeout): el detector con POI
es LENTO en esta laptop (cuello de evaluate_signals+POI sobre M15, mismo que
colgaba el backtest). Los numeros de la seccion (7) siguen siendo validos y
actuales; el script es correcto, solo pesado.

**Backtest end-to-end de 1 mes con exec_tf=M5:** INVIABLE en esta laptop
(timeout 1500s). El cuello es fine_execution reprocesando M5 masivo (333k
velas) por cada senal. Es un problema de ARQUITECTURA del backtest (no del
fix): el backtest original tambien moria por SIGTERM a los ~550s. Para ver
senales en vivo sin esperar 25 min: el HUB con runner_monitor en ventana
chica, u optimizar la carga de M5 (Fase 1.5 pendiente).

**Estado de la capa LTF:**
- EXEC FINO M5/M1 (Fase 1): CERRADO en motor + testeado (15 passed, commit 03c8539).
- PENDIENTE: Fase 2 (Trade Management BE+parciales), Fase 3 (Silver Bullet+PO3),
  Fase 4 (OTE), Fase 5 (unificar KZ), y optimizar backtest para ventana chica.

**Verificacion:** pytest tests/test_engine_execution_b2.py + test_b2_exec_tf.py
+ test_b2_exec_tf_wiring.py -> 15 passed. Commit 03c8539 (sin push, regla Ruben).

## Registro de sesiones anteriores (resumido)
- 2026-08-03: purga intencional de roadmaps (docs/plan/). Fuente de verdad =
  AGENTS.md + docs/tesis/ + engine/.

## 2026-08-06 (9) — ORDEN del VIGILANTE de riesgo (2% perdida + $60 ganancia flotante)

**Pedido del trader:** confirmar si existe un vigilante que gestione 2% de
perdida flotante y $60 de ganancia flotante, y ORDENARLO.

**Hallazgo:** el vigilante SI existe pero estaba DESORDENADO:
- scripts/_legacy/vigilante_riesgo.py (carpeta legacy/inactiva, no en
  scripts/ donde el observador lo busca).
- app_observador/core/process_control.py define VIGILANTE_SCRIPT =
  vigilante_riesgo.py y lo arranca desde ROOT/scripts/ => apuntaba a la
  nada (toggle del observador roto).
- El script importa _single_instance que NO existia => crasheaba al arrancar.
- Solo gestionaba 2%/4% de PERDIDA; le faltaba el trigger de +$60 GANANCIA
  que el trader describio.

**Orden aplicado (verificado con ejecucion real):**
1. Movido scripts/_legacy/vigilante_riesgo.py -> scripts/vigilante_riesgo.py
   (donde process_control.py lo espera).
2. Creado scripts/_single_instance.py (helper de instancia unica que el
   script requeria y faltaba).
3. Anadido GOAL_PROFIT = 60.0 y rama de GANANCIA FLOTANTE en el loop: si
   equity - balance0 >= $60 -> cierra todo (banquear). Ahora gestiona
   AMBOS: 2% perdida (SOFT) / 4% (HARD/DLL) y +$60 ganancia flotante.
4. Corregido docstring con rutas Windows sin escape invalido (SyntaxWarning).
5. Verificacion: ast.parse OK, import vigilante_riesgo OK (sin MT5),
   import _single_instance OK.

**Nota:** el $60 de ganancia flotante en el VIGILANTE (cierra todo al +$60)
es distinto al $60 de META DE APAGADO del bot en app_observador/ui/
autopilot_widget.py (el bot se apaga solo al +$60). Ambos coexisten:
vigilante = proteccion de CUENTA; autopilot = apagado del bot. El motor ya
tiene Trade Management E1 (BE+parciales) en ict_backtest/trade_mgmt.py
(escrito por sesion previa, no cableado al backtest).

**Verificacion:** syntax OK, imports OK. Sin MT5 (no se conecta en seco).

## 2026-08-06 (10) — CABLEADO de E1 (Trade Management BE+parciales) al backtest

**Pedido:** "si cablealo" -> cablear el Trade Management E1 al backtest.

**Hallazgo previo:** el motor YA tenia E1 en `ict_backtest/trade_mgmt.py`
(BE + parciales + trailing) escrito por sesion previa, pero el backtest
(`bar_by_bar_engine.compute_backtest_metrics`) hacia HOLD SL/TP PURO (sin
gestion). El backtest ignoraba E1.

**Cambios (verificados con ejecucion real):**
1. `ict_backtest/bar_by_bar_engine.py`: reemplazado el loop hold SL/TP puro
   por llamada a `apply_trade_management(entry, sl, tp, dirn, tm_df,
   partial_pct=0.5, tp1_r=1.0, trail_step_r=1.0, be_buf=0.0)` sobre el slice
   M5 post-entry. El backtest ahora consume E1 (Ley respetada: backtest
   importa backtest, nunca motor).
2. `ict_backtest/trade_mgmt.py` (E1): BUG de precision corregido. E1 solo
   miraba `close` para detectar touches -> ciego a intra-bar y fallaba por
   deriva de flotantes en touches exactos (1.1010 >= 1.1010000000000002 =
   False). Ahora detecta el touch por `high`/`low` (ejecuta al nivel
   tocado) y usa epsilon 1e-10. Esto hace que el parcial/BE/TP se disparen
   como en trading real (el precio TOCA el nivel, no solo cierra ahi).
3. El backtest usa `pnl_r` ya ponderado por E1 (parcial + remanente), no lo
   recalcula. Costs ON (R6): comm restado en R (comm/risk).
4. `hold_bars` corregido: busca el cruce del nivel de salida segun direccion
   (TP sube, SL/BE cae).

**Verificacion (smoke temporal, borrado):**
- Serie M5 sintetica: long entry 1.1000 sl 1.0990 tp 1.1030, sube a 1.1010
  (tp1), cae a 1.0990. Con hold puro -> SL -1R. Con E1 -> parcial +1R a la
  mitad + remanente en BE => pnl_r = 0.5 (razon be). DEMUESTRA cableado.
- Bateria: 152 passed (test_engine_* + test_b2_* + test_e1_*). E1 no roto.

**Nota:** E1 es del backtest (desechable). La Fase 2 real de la tesis pide
Trade Management en el MOTOR (engine/), no solo en el backtest. Esto queda
pendiente: el motor aun hace hold SL/TP; el backtest ahora gestiona. Cuando
el motor tenga su trade_mgmt, el backtest lo consumira y E1 se borrara.

## 2026-08-06 (11) — PLAN DE MANANA: render tipo TradingView del motor (D1)

**Contexto:** el trader mostro una imagen de EURUSD D1 en TradingView (SMC:
BOS/CHOCH/MSS/FVG/OB/liquidez) y pregunto si el motor da algo parecido.
Verificado hoy (corrida ad-hoc, sin commit): el motor en D1 marca BOS
alcista activo 2026-08-03 nivel 1.14710, CHOCH=0 (sin giro). El observador
es hub de texto, NO grafico. El motor TIENE los datos (bos/structure,
fvg_poi, order_block) pero nadie los dibuja en velas.

**Objetivo:** construir un render visual (tipo TradingView) que consuma el
motor y muestre lo que el motor "dice" hoy sobre EURUSD D1, para que el
trader lo juzgue por OJO contra su imagen.

**Pasos (DUMI, sin codear hasta OK del trader):**
1. Formato: decidir PNG estatico (matplotlib, abres el archivo) vs cablear
   al hub web (localhost:8765, app_observador). Recomendado: PNG estatico
   primero (mas rapido de validar por OJO), luego opcional al hub.
2. Pipeline del render:
   - Cargar EURUSD_D1.parquet (data/raw, velas cerradas).
   - `engine/bos/structure.detect_market_structure` -> lineas BOS/CHOCH
     (niveles activos + ultimos eventos).
   - `engine/fvg_poi` + `engine/order_block` -> zonas FVG y OB (POI anclado).
   - matplotlib: velas + lineas horizontales localizadas (vida del evento,
     estilo trader humano: NO ancho completo del canvas — Ruben lo rechaza
     como "infinitas").
3. Validacion por OJO (Ruben): las lineas caen donde el motor dice? Coincide
   con su imagen de TradingView en la zona 1.138-1.160?
4. Si coincide y el trader quiere: cablear al hub web para ver en vivo.

**Restricciones:** Ley respetada (el render es consumidor del motor, nunca
al reves). Sin indicadores. Sin look-ahead. Niveles solo sobre velas cerradas.

**Fuera de alcance mañana:** no escribir logica de deteccion nueva (ya esta
en el motor). Solo VISUALIZAR lo que el motor ya calcula.

## Registro de sesiones anteriores (resumido)
- 2026-08-03: purga intencional de roadmaps (docs/plan/). Fuente de verdad =
  AGENTS.md + docs/tesis/ + engine/.
- 2026-07-16..17: R6 cerrado en código; auditorías de fidelidad a tesis y
  cobertura de backtest. Ver docs/auditorias/ (vigentes) y docs/_descartado/
  (los que cruzaban roadmaps ya purgados).

## 2026-08-07 — Sesión: auditoría de secuencia/funnel + filtro de autoridad POI HTF

### Contexto de arranque (pendiente de anoche, recuperado de bitácora)
- Sesión anterior (2026-08-06) cerró con POI rescatado al motor: `engine/htf_pd_index.py`
  + `engine/zone_authority.py` (rescate de Brecha B/POI anclado, módulos que habían sido
  borrados por acoplamiento a `ict_backtest.market_object`; reescritos SIN importar backtest).
- Tarea de anoche: "auditoría de viabilidad del rescate" + arrancar auditoría de secuencia/funnel.
- Se corrió `audit_sequence_funnel.py 3` (3 meses EURUSD): FUNNEL SWEEP 82 → DISPLACE 81 →
  BOS 68 → ENTRY 68 = 25 setups completos (2026-07=16, 2026-08=9). Conversión por eslabón
  estable (~83% SWEEP→ENTRY). El cuello NO es el detector: casi todo sweep que desplaza y
  rompe completa el retorno; el 17% muere en SWEEP→DISPLACE/BOS.

### Trabajo de hoy (verificado con ejecución real)
1. **Pregunta del trader**: "¿el motor reconoce reversión/retroceso en LTF como un humano?"
   Respuesta (con evidencia en engine/): SÍ, con geometría pura (sin indicadores):
   - RETROCESO OTE: `engine/dealing_range.py` marca OTE 0.62–0.79 del rango y exige
     discount (alcista)/premium (bajista). Cableado en `htf_narrative.py:122` y `plan.py:349`.
   - REVERSIÓN ESTRUCTURAL = CHOCH: `engine/bos/structure.py` + `sequence.py:189`. En
     contratendencia se exige como paso 2 de BOS→CHOCH→BOS. `plan.py:57` (`_bos_real_behind`,
     T9.7) filtra CHOCH por BOS real detrás (anti-ruido).
   - SWINGS HH/HL/LH/LL confirmados: `engine/bias/narrative.py:141` (`_label_swings`),
     versión humana (extremo cuenta solo si rompe swing previo en dirección opuesta).
   - BRECHA vs ojo humano: el CHOCH del motor NO aplica el filtro EXP-012 de Ruben
     (empuje >=2 HH/LL post-tendencia, nivel=pivote roto, reclaim invalida). El OTE se mide
     sobre el rango HTF, no sobre el mini-swing LTF interno.
2. **Filtro de autoridad POI sobre el funnel** (nuevo, consume el motor):
   - `scripts/audit_funnel_authority_filter.py`: corre `evaluate_signals` (WM vía argv[1])
     y por cada ENTRY lee `poi["authority"]` de `build_htf_narrative` (MISMA fuente del
     observador — NO se reimplementa la autoridad, Ley OK).
   - Resultado 1 mes (EURUSD, válido): 10 setups → Alta 2 (0.85, T2, 3 capas) / Media 6
     (0.65–0.75) / Baja 2 (0.0, sin ancla) / sin_autoridad 0. **Alta+Media = 80%**.
   - Conclusión: el rescate POI aporta información accionable — 80% de los setups tienen
     respaldo HTF real; 20% (2/10) son ruido sin ancla (lo que tesis 21 §4 quiere filtrar).
     Un filtro SUAVE (no gate duro, Fase E) `confidence_weight >= 0.65` pasaría 8/10.
   - NOTA: primeras 3 corridas del filtro usaron `HtfPdIndex.zones_at`+`detect_fvg/ob` a mano
     (bug: 19/25 "sin-zona-ltf", 0% Alta). Corregido a `build_htf_narrative`; el resultado
     válido es el de 1 mes arriba. Los `.out` viejos bugueados NO se usan.
3. **Experimentos en el repo (pregunta del trader)**: SÍ existe laboratorio —
   `geometry_lab/run_experiment.py` + `docs/lab/LABORATORIO_ICT_SMC.md` (falsificación
   empírica del motor vela a vela, importa engine/, engine/ NO lo importa). También
   experimentos E1–E5 en `docs/METRICS_CANON.md` y experimentos A/A''/F referenciados en
   openspec/ y scripts/.

### Archivos / resultados generados hoy
- `scripts/audit_funnel_authority_filter.py` (renombrado desde _tmp_, limpio).
- `results/funnel_authority_filter.json` (válido, 1 mes: Alta 2/Media 6/Baja 2, 80% Alta+Media).
- `results/audit_funnel_3m.out` (funnel 3 meses: 25 setups).
- Bitácora actualizada.

### Pendiente / próximos pasos (sin OK explícito, no ejecutado)
- (A) Correr filtro WM=3 corregido (~37 min) para confirmar 80% a escala 3 meses.
- (C) OTE sobre mini-swing LTF interno (granularidad fina) vs rango HTF actual.
- (D) Abrir `geometry_lab/run_experiment.py` para medir el motor vela a vela.

## 2026-08-08 — Cierre de BRECHA EXP-012 en el motor (CHOCH real con empuje)

**Contexto:** tarea (B) del 08-07. EXP-012 (skill smc-ict-hub-exp012) define CHOCH REAL =
cambio de carácter tras tendencia con momentum: exige empuje >=2 HH/LL post-tendencia,
BOS de mercado real detrás, nivel = ÚLTIMO HL/LH roto (no el nivel del BOS roto), reclaim
invalida. El motor SMC-SYSTEMS ya tenía T9.4 (reclaim) y T9.7 (after_bos real) pero
NO el filtro de momentum → su CHOCH era más permisivo (ruido).

**Método (rol CEO + asamblea de agentes):** se convocó asamblea de 3 agentes (Arquitecto,
Trader-Humano, Riesgo/OPS) que votó 1 APROBAR / 2 MODIFICAR. Ruben aclaró filosofía:
los agentes Trader-Humano NO mandan, son pragmáticos (reflejo de su ojo); el CEO decide.
Se aplicaron las enmiendas TÉCNICAS válidas y se descartaron las imposiciones de rol:
- Aplicado: nivel HL/LH correcto (no reusar BOS), dtypes compactos, test ON/OFF con
  no-regresión byte-idéntica, flag con caducidad documentada.
- Decidido por CEO (pragmático, no por voto de rol): BONUS de autoridad (no GATE duro) +
  `exp012=True` por defecto en el observador para ejercitar la ruta a diario.

**Trabajo ejecutado (verificado con ejecución real):**
1. `engine/bos/structure.py`: `StructureConfig.exp012_choch: bool = False` (OFF por
   defecto, regresión cero). Nuevo helper `_exp012_choch_marks(d)` recorre el frame ya
   anotado y por cada `choch_dir != 0` evalúa (a) momentum HH/LL>=2, (b) after_bos real
   vía `_last_bos_dir`, (c) nivel = ÚLTIMO HL/LH roto (`choch_pivot_level`, NO
   `choch_proj_level`), (d) reclaim = `choch_status == invalidated`. Expone columnas
   `choch_exp012` (int8), `choch_pivot_level` (float64), `choch_exp012_after_bos` (int8).
   NO muta `choch_dir`/`choch_status` (bonus, no gate).
2. `engine/plan.py`: `ltf_structure_at(..., exp012=False)` pasa el flag a
   `detect_market_structure` y expone `choch_exp012_count`/`choch_exp012_last_level`.
3. `engine/bias/narrative.py`: `compute_htf_bias` / `compute_htf_bias_series` ganan
   `exp012=False` y lo propagan a `_bias_for_frame` (sin vetar el sesgo canónico).
4. `engine/htf_narrative.py`: `build_htf_narrative(..., exp012=True)` → default ON;
   expone `choch_exp012={'count','last_level'}` en la salida. El observador
   (`app_observador/core/engine.py::_canonical_plan`) ya lo recibe sin cambios.
5. `tests/test_engine_bos_exp012.py`: 5 tests (helper con/sin momentum, reclaim,
   no-regresión OFF no añade columnas, integración M15 real con drop).

**Resultados medidos (verify ad-hoc, EURUSD M15 114,237 velas):**
- Tiempo OFF=18.3s vs ON=18.7s → delta +381ms (marginal, O(n) vectorizable).
- CHOCH canónico = 12,404 → EXP-012 = 763 → **drop 11,641 (93.8% de ruido eliminado)**.
- `choch_pivot_level` difiere de `choch_proj_level` (confirma nivel HL/LH correcto).
- 0 filas exp012 inconsistentes. Integración observador: `choch_exp012={'count':10,
  'last_level':1.15105}` con default ON; `None` con OFF.

**Tests:** `pytest tests/test_engine_*.py` → **132 passed** (subió de 127 a 132; 5 nuevos).
Regresión cero confirmada (flag OFF deja el frame idéntico).

**Caducidad del flag:** `exp012_choch` se documenta como experimental 2026-08-08.
Promover a comportamiento estable (encender en backtests) o borrar en revisión futura.

**CORRECCIÓN MISMA SESIÓN (Ruben: "equivocado, quiero GATE DURO"):** el diseño
original era BONUS (solo marcaba, no vetaba). Ruben corrigió: debe ser GATE DURO.
Cambio aplicado y verificado:
- `engine/bos/structure.py`: con `exp012_choch=True`, tras el helper se SOBREESCRIBE
  `choch_dir=0` y `choch_status="none"` donde `choch_exp012==0`. El CHOCH sin empuje
  >=2 HH/LL DEJA DE EXISTIR en el frame → sesgo, secuencia y observador lo ignoran
  (consumidores intactos, censura en la fuente). `choch_exp012`/`choch_pivot_level`
  quedan como auditoría.
- `engine/htf_narrative.py`: `_last_bos_event(frame, exp012)` aplica el gate también al
  BOS/CHOCH que alimenta el POI del observador.
- Tests: `test_exp012_gate_hard_zeroes_noise` + `test_exp012_real_m15_drop` ahora
  exigen `choch_dir!=0 == choch_exp012==1` (gate duro, no subconjunto).
- Verificación ad-hoc (EURUSD M15 3,000 velas): 319 CHOCH canonico -> 14 con gate
  (95.6% ruido eliminado). Sesgo estable en ventana con tendencia; en RANGO el sesgo
  caeria a NEUTRAL (riesgo conocido, documentado: el sesgo NEUTRAL perpetuo en rangos
  empeora con gate duro — ver AGENTS.md brecha narrative.py).
- `pytest tests/test_engine_*.py` -> 133 passed (6 nuevos). Regresión cero (flag OFF
  no muta el frame).

**Fuera de alcance (no hecho hoy):** pintar `choch_exp012` en la UI del observador
(el dato ya viaja en el dict; mostrarlo en pantalla es paso de UI aparte). (A)/(C)/(D) siguen
pendientes de días previos.

**CAMINO B — CONSEJO DE AGENTES (2026-08-08, misma sesión):** tras medir la BASE
(`scripts/measure_motor_veltick.py` → `results/motor_veltick_EURUSD_M15.json`, EURUSD M15
3 meses), el consejo votó el destino del gate. Resultados de la base: CHOCH drop 94.2%,
NEUTRAL 0%/0%, ALIGNED 1.5%/42.2%, flips 45%. Votos: Arquitecto→B, Trader-Humano→B,
Riesgo/OPS→C. MAYORÍA = B.

CAMINO B implementado: **GATE DURO solo en ESTRUCTURA LTF/ENTRADA; SESGO HTF CANÓNICO.**
El gate vive SOLO en `engine.bos.structure.detect_market_structure` (flag `exp012_choch`);
el sesgo (`engine/bias/narrative.py` `_bias_for_frame`/`compute_htf_bias`/`compute_htf_bias_series`
y `htf_narrative._resolve_bias`) YA NO acepta `exp012` → usa CHOCH canónico SIEMPRE.
Esto resuelve la objeción de Riesgo/OPS (gate en un solo lugar, sin flag bifurcado) y
recupera la alineación sesgo↔estructura (ver base nueva).
- `engine/bias/narrative.py`: quitado `exp012` de las 3 funciones de sesgo; detect sin gate.
- `engine/htf_narrative.py`: `_resolve_bias` sin `exp012`; `build_htf_narrative` mantiene el
  flag SOLO para pintar `choch_exp012` (auditoría visual del observador), no para el sesgo.
- Bug doc corregido: `StructureConfig.exp012_choch` decía "NO muta" y mutaba (Riesgo/OPS lo halló).
- Tests: nuevo `test_caminoB_sesgo_inmune_a_gate`; pytest enfocado -> 7 passed.
- BASE NUEVA (1 mes, camino B): NEUTRAL=0%, ALIGNED=40.0% (recuperó el 42% que el gate
  duro destruía), CHOCH/ventana 30.56→2.09 (drop 93.2% en EJECUCIÓN LTF), flips=0.
  Conclusión: sesgo coherente (40% alineado) + ejecución LTF limpia (94% menos ruido).
- Pendiente: medir ALIGNED para umbral ≥1 HH/LL (camino C) si se quiere comparar; por ahora
  B es el camino vigente por mayoría del consejo.

**(A) CERRADO — filtro autoridad WM=3 (2026-08-08):** confirmado a escala 3 meses.
Script `scripts/audit_funnel_authority_filter.py 3` (consume el motor vía
`build_htf_narrative`, NO reimplementa). Resultado REAL (EURUSD M15, 3m, 6533
velas, 3316.8s):
- Funnel: SWEEP 82 -> DISPLACE 81 -> BOS 68 -> ENTRY 68. Setups ENTRY: 25.
- Autoridad HTF: Alta 10, Media 15, Baja 0, sin_authority 0.
- TOTAL 25 | Alta = 40.0% | **Alta+Media = 100.0%** (0 Baja, 0 sin autoridad).
- Conclusión: el filtro de autoridad POI es sólido a escala — supera el 80% de
  1 mes (Alta 2/Media 6/Baja 2 = 80%) y a 3 meses llega a 100% Alta+Media.
  JSON en `results/funnel_authority_filter.json`.
- NOTA tooling: `runner_monitor --window` FALLA en este bash MSYS ("no job
  control"); para jobs largos usar `background=true` + `notify_on_complete`
  directo (no runner_monitor --window). Documentado para futuros jobs.

**(C) BASE MEDIDA — OTE mini-swing M5 vs rango HTF (2026-08-08):** decidido
M5-dentro-de-M15. Script `scripts/measure_ote_c.py` reusa las 25 entries de (A)
y calcula OTE (retroceso 0.62-0.79) sobre (1) rango HTF M15 (lookback=10) y
(2) "mini-swing" M5 (rolling 60 velas previas). Resultado REAL (EURUSD, 25 entries):
- Ancho zona: HTF=0.00025 | M5=0.00045. Ratio 0.57x — el OTE M5 resultó MAS
  ANCHO, no mas ajustado (mi "mini-swing" M5 era rango rodante, no pivote real).
- Entry en HTF=16% | en M5=16% | en ambos=0%.
- HALLAZGO HONESTO: el motor ENTRA EN BOS, no en retroceso OTE. El OTE es zona
  de confirmacion, no de entrada; por eso la entry rara vez cae en la zona OTE.
  La idea (C) "OTE sobre mini-swing" no mejora tal cual: el rango M15 ya es
  estrecho y la entry es el BOS. Para (C) real se necesita mini-swing por
  PIVOTES (HL/LH) sobre el tramo swing->entry, no rango rodante. Pendiente
  refinar si se quiere (C) como mejora de precision de entrada.
- JSON: `results/ote_c_EURUSD.json`.

**Sin commit/push (regla Ruben: requiere OK expreso).**

## Auditoría de conformidad engine/ vs SDD — 2026-08-14

Se registró la auditoría completa en `docs/auditoria_conformidad_engine_sdd_2026-08-14.md`.
Correcciones técnicas aplicadas: verificador de fuentes UTF-8 seguro; consumidores de
`run_sequence_traced` alineados a la tupla de cuatro valores; `avg_candle_range` sin
`bfill()` futuro y shim del backtest hacia `engine._util`; `engine.market_structure`
convertido en fachada hacia `engine.bos.structure`; aliases de killzone y normalización
del call-site de `run_backtest`. Evidencia: fuentes activas 23/0 rotas/0 cross-project,
baterías engine y replay registradas en el informe, compileall limpio. Quedan escaladas
únicamente decisiones de semántica/autoridad (OTE, convención OB, perímetro legacy,
contrato labels y documentos de protocolo ausentes). Sin commit/push.

## 2026-08-14 (tarde) — Cierre de conformidad autónomo (Hermes + Consejo activo)

Director delega objetivo completo: "llevar SDD + engine a conformidad cerrada y
verificable; orquestar todo; escalar solo decisiones de autoridad". Aprobación total
de documentos ya decididos. Protocolo: bitácora + plan con checks + push por unidad +
pop-up al terminar para revisión con ChatGPT.

### F0 Reality Map (hecho)
- HEAD local = `b3fa2c7`. Mis commits FIX (`1651bdf` cableado MarketReplay, `a3708b4`
  addendum SDD_MARKET_REPLAY + SUPERSEDED SDD_M2_LINEAGE) SÍ en rama y origin.
- Working tree sucio (23 archivos): correcciones Codex + refactor señal adelantada
  (borró `bar_by_bar_engine.py`, `_smoke.py`, redujo `ict_backtest/engine.py` a fachada)
  + scripts propios sin commitear. Se aíslan fuera del commit de cierre.

### F1 Contract Reconciliation (hecho)
- OTE (`engine/ote.py:67-71`): LONG en descuento, SHORT en premium. SIN inversión.
  gap es AMBIGUOUS CONTRACT (SDD no dice si OTE es gate o metadata) → resuelto por
  aprobación: OTE = metadata, no gate duro.
- OB (`engine/order_block.py`): ya confirma por vela siguiente (shift(-1)).
- POI fail-open: EXPECTED BY DESIGN (SDD lo permite).
- G2/G3: fuera del motor, no contradice SDD. O(n²): en uso canónico es O(n).

### F2 Shadow OB (hecho)
- 2000 velas M15 → 27 OB, status event-driven (none/active/invalidated). Convención
  actual ya canónica. Añadir origin_index/confirmed_index = trazabilidad, no cambia señal.

### F3a Quarantine tests/_broken (hecho)
- Creado `tests/_broken/QUARANTINED.md`. Fuera del gate oficial.

### F3b/c BLOQUEADO por autoridad (HALT)
- Contradicción real: decisión aprobada #2 ("confirmación cerrada" = vela siguiente,
  como `engine/order_block.py`) CHOCA con `detectors/ob.py:20-26` que argumenta que
  vela siguiente = look-ahead y por eso usa vela ANTERIOR (shift(1)).
- NO se toca ni `engine/order_block.py` ni `detectors/ob.py` hasta fallo del Director:
  ¿confirmación = vela siguiente (entonces detectors/ob.py debe cambiar) o = vela
  anterior (entonces engine/order_block.py tiene look-ahead y se corrige)?

### Pendiente
- F4 perímetro oficial de pruebas (documental).
- F5 replay escalado 100→2000 velas con runner_monitor.
- F6 paquete de auditoría independiente → AUDITED.
- F7 ACCEPTED (Director).

## 2026-08-14 (noche) — F4 OK, F5 INCONCLUSIVE, avance F6

### F4 Perímetro oficial de pruebas (HECHO)
- Creado `docs/planificacion/PERIMETRO_PRUEBAS_CONFORMIDAD.md`: gate oficial (truth
  sources, compileall, separacion engine/ict_backtest, suites del motor, replay
  rapido, equivalencia escalada) + tratamiento fuera de perimetro (QUARANTINE,
  BLOCKED_DATA, INCONCLUSIVE). Criterio PASS estricto.

### F5 Replay escalado (INCONCLUSIVE_OPERATIONAL — no PASS, no FAIL)
- Validador `_validate_fix_quick.py` corregido para usar el FIX (htf="H4",
  bos_gap=10). N=100: exit 0 (PASS) en corrida aislada, pero NO deterministico:
  re-corrida N=100 y N=400 dieron timeout (exit 124, 120-200s).
- Causa: MarketReplay sigue O(n^2) en ventanas >100 velas (diagnostico original de
  sequence.py: copia por llamada). El FIX de cableado (contexto HTF + LTF) es
  correcto para N pequeno pero el cuello de botella de rendimiento persiste.
- Veredicto F5: N=100 PASS aislado; N>=400 INCONCLUSIVE_OPERATIONAL (timeout, no
  evidencia de fallo ni de exito). NO se declara PASS del replay escalado.
- Accion pendiente (tecnica, fuera de autoridad): aplicar parche copy_objs
  (SequenceConfig.copy_objs ya existe en engine) para llevar MarketReplay a O(n).
  Requiere test de equivalencia previo. Se delega a MISION rendimiento.

### F6 Paquete de auditoria (EN CURSO)
- Evidencia solida INDEPENDIENTE del replay escalado:
  * FASE A: 18 setups en backtest canonico (run_sequence_traced directo), 100% §4.
  * Bateria replay rapida: 12 passed (test_market_replay_audit_battery.py).
  * Linaje: 17 passed, 1 skipped (test_m2_lineage + test_phase6_lineage).
  * Truth sources: 23/23 activas, 0 rotas, 0 cross-project.
  * compileall engine+ict_backtest: exit 0.
  * 0 imports ict_backtest desde engine/.
- Estas pruebas usan el motor directo (no MarketReplay escalado), por lo que el
  timeout de F5 NO las afecta. El motor esta TESTED+SEMANTICALLY_VERIFIED en el
  perimetro activo.

### F3b/c sigue BLOQUEADO por autoridad (confirmacion OB vela siguiente vs anterior).

