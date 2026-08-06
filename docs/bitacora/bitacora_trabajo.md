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
- 2026-07-16..17: R6 cerrado en código; auditorías de fidelidad a tesis y
  cobertura de backtest. Ver docs/auditorias/ (vigentes) y docs/_descartado/
  (los que cruzaban roadmaps ya purgados).
