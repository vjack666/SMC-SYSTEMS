# AUDITORÍA DE ARQUITECTURA — PlanFSM como cerebro de decisión

**Fecha:** 2026-07-20
**Autor:** Hermes (auditoría, NO propuesta — solo evidencia de código + roadmap)
**Alcance:** responder si `PlanFSM` ya puede ser el único cerebro de decisión
usando la cascada D1→H4→H1→M15→M5→M1, o si `run_sequence` sigue obligado a
decidir. Basado en código actual y roadmap. Sin recomendaciones.

---

## 0. PIEZAS REVISADAS (evidencia de código)

- `ict_backtest/plan_fsm.py` — `PlanFSM` (reductor puro), `PlanEvent`,
  `PlanVerdict`, `_CONTEXT_LAYERS=("D1","H4")`, `_TRANSITIONS`.
- `ict_backtest/plan_emitters.py` — `emit_d1/h4/h1/m15/m5/m1` (funciones puras).
- `ict_backtest/plan_driver.py` — `plan_step`, `run_plan_fsm`, `score_plan`,
  `AlignmentReport`, `build_confirm_from_tf`.
- `ict_backtest/sequence.py` — `run_sequence` (líneas 319-403, `htf_poi_fn`,
  loop SWEEP→DISPLACE→BOS→ENTRY a `run_backtest.py:282-380` (plan_gate Opción B).
- `ict_backtest/v2/context_mtf.py` — `top_down_allows_trade` (gate D1→H4→H1→PD).
- `ict_backtest/data_feed.py` — `build_objects` (MarketObjects por TF).
- Docs: `ARQUITECTURA_TEMPORALIDADES.md`, `AUDITORIA_TESIS_FASE5.md`,
  `ETAPA_4_FASE_C_PLAN.md`, `CRONOGRAMA_Y_ROADMAP.md`.

---

## 1. ¿QUÉ INFORMACIÓN APORTA HOY CADA TF AL PlanFSM?

Por los emisores (`plan_emitters.py`):

| TF  | Emisor | Veredicto que emite | Qué lee del TF |
|-----|--------|---------------------|----------------|
| D1  | `emit_d1` (l.38) | `CONTEXT_OK` / `CONTEXT_INVALID` | ¿hay OBJETOS? (cualquiera, sin filtrar tipo) |
| H4  | `emit_h4` (l.45) | `CONTEXT_OK` / `CONTEXT_INVALID` | ¿hay BOS/CHOCH ACTIVE/CREATED? |
| H1  | `emit_h1` (l.59) | `ZONE_ARMED` / `ZONE_INVALID` | ¿hay objeto `role=POI` tipo OB/FVG ACTIVE? |
| M15 | `emit_m15` (l.79) | `STRUCTURE_OK` / `SETUP_LIVE` / None | salida de `run_sequence` (entry_at/bos_at o phase_log) |
| M5  | `emit_m5` (l.112) | `ENTRY_READY` / None | `m5_confirm.confirmed` + misma dirección |
| M1  | `emit_m1` (l.131) | `IN_TRADE` / None | `m1_trigger.confirmed` + misma dirección |

En `plan_step` (plan_driver.py:184-212) cada TF se consulta con
`_objs_before(objs_by_tf, tf, t)` (closed-only por `bar_time`).

---

## 2. ¿QUÉ INFO DE CADA TF ESTÁ DISPONIBLE PERO NO SE USA EN EL PlanFSM?

- **D1**: `dealing_range_pd` (premium/discount EQ) YA existe en `context_mtf.py`
  y se inyecta en `build_context_stack`, pero `emit_d1` NO lo lee. El PlanFSM
  ignora premium/discount de D1.
- **H4/H1**: `pd_side` (premium/discount) y `poi_count` (POI anclado vía
  `htf_pd_index`, Fase C) están en el `MultiTFContext` (context_mtf.py:122-132)
  pero `emit_h4`/`emit_h1` NO los consultan. `emit_h1` busca `role=POI` en los
  MarketObjects de H1, no el POI anclado HTF de la Fase C.
- **POI anclado (Fase C / `htf_pd_index`)**: cableado en producción (obs +
  backtests CLI/v2) para `zone_authority`, pero el PlanFSM no lo consume como
  veredicto. `score_plan` lo bonifica (`m15_anchored`, +0.5) pero no como gate.
- **PO3 / AMD** (A/M/D): `compute_po3_complete` se calcula en `canonical.py`
  por señal, pero el PlanFSM no lo evalúa (solo `score_plan` lo bonifica,
  +0.5, Brecha E).
- **Sweep / displacement / BOS internos**: el PlanFSM solo ve el veredicto M15
  final (`emit_m15` sobre la salida de run_sequence). No ve las fases
  intermedias sueltas.
- **M5/M1 estructura fina**: `build_confirm_from_tf` solo mira `bos_dir`/
  `choch_dir` del último objeto cerrado. No usa mecha de sweep, ni BPR, ni
  ranging real.

---

## 3. ¿QUÉ DECIDE HOY EL PlanFSM Y QUÉ SIGUE EN run_sequence?

**PlanFSM (vía `plan_gate` en run_backtest.py:284-319, Opción B):**
- Decide SOLO la EJECUCIÓN: si una señal YA generada por run_sequence se opera.
- Umbral `STRUCTURE_OK` (run_backtest.py:289). Veta si el estado FSM < STRUCTURE_OK.
- NO genera señales, NO define dirección, NO define SL/entry, NO define el setup.
- Por diseño (AUDITORIA_TESIS_FASE5.md:166-172): "run_sequence INTACTO; la FSM
  gobierna la EJECUCIÓN de trades, NO la generación de señales."

**run_sequence (sequence.py:368-510, loop SWEEP→DISPLACE→BOS→ENTRY):**
- Decide: barra a barra, la secuencia sweep→displace→BOS→retorno.
- Decide dirección `target` desde `est_htf["trend"]` (solo H4, sequence.py:380).
- Decide el SL estructural (calc_structural_sl sobre mecha M15, buffer rango M15).
- Decide el RR 1:3 forzado y el filtro de killzone (canonical.py:177).
- Decide el POI vía `htf_poi_fn` (sequence.py:403) → HOY `None` ⇒ siempre True.
- Decide el filtro de volatilidad `STRUCT_SL_MAX_RANGE` (6×rango M15).

Conclusión: **la dirección, el setup, el SL y el filtrado de volatilidad viven
100% en run_sequence/canonical. El PlanFSM solo filtra al final (ejecución).**

---

## 4. ¿LÓGICA DUPLICADA ENTRE PlanFSM Y run_sequence?

SÍ, en el eje dirección/contexto:

- **Dirección desde H4**: `run_sequence` la saca de `est_htf["trend"]` (H4) en
  sequence.py:380. El PlanFSM la deduce en cadena D1→H4→H1 (emit_d1/emit_h4/
  emit_h1). Ambos evalúan el sesgo H4; el PlanFSM además exige D1+H1, run_sequence
  ignora D1/H1.
- **POI**: `run_sequence` tiene el hook `htf_poi_fn` (sequence.py:403, hoy None).
  `emit_h1` evalúa POI en H1. Dos caminos de POI distintos, uno muerto.
- **Confirmación M5/M1**: `run_sequence` NO usa M5/M1 para decidir (solo M15).
  `emit_m5`/`emit_m1` los usan pero solo como bonus/timing en el PlanFSM.
- **NO duplicado**: el setup sweep→displace→BOS→entry es exclusivo de
  run_sequence; el PlanFSM solo consume su veredicto final (emit_m15).

La duplicación es de **responsabilidad solapada en dirección/contexto**, no de
código idéntico. Son dos cerebros leyendo H4.

---

## 5. ¿QUÉ RESPONSABILIDAD DEBERÍA SER EXCLUSIVA DE CADA UNO?

Por el contrato de `plan_fsm.py` (l.11-18) y `ETAPA_4_FASE_C_PLAN.md:93`
("Un solo cerebro. C es capa de CONTEXTO, no de decisión"):

- **PlanFSM (cerebro de CONTEXTO/alineación MultiTF):** dirección derivada
  D1→H4→H1; POI anclado; premium/discount; alineación de capas. Su veredicto es
  el estado del plan (CONTEXT_OK→...→IN_TRADE).
- **run_sequence (motor de SETUP/ejecución LTF):** la secuencia sweep→displace→
  BOS→retorno; el SL estructural anclado a mecha; el RR; el filtro de killzone;
  la volatilidad del LTF. NO debería decidir dirección macro (hoy lo hace).

Hoy run_sequence decide dirección (exclusiva del PlanFSM según contrato) y el
PlanFSM solo filtra ejecución. Están INVERTIDOS respecto al contrato ideal: el
PlanFSM debería ser el que autoriza la dirección y run_sequence operar dentro.

---

## 6. ¿EL PlanFSM YA PUEDE GOBERNAR LA CASCADA COMPLETA SIN MODIFICAR SU ARQUITECTURA?

**NO, sin modificaciones.** Evidencia:

- `PlanFSM.transition` (plan_fsm.py:95-115) solo entiende los veredictos
  `CONTEXT_OK/ZONE_ARMED/SETUP_LIVE/STRUCTURE_OK/ENTRY_READY/IN_TRADE/*_INVALID`.
  No tiene noción de "dirección" ni de "premium/discount" ni de "POI anclado".
  Solo acumula `_context_layers` y transiciona por veredicto.
- `emit_d1` (plan_emitters.py:38-42) devuelve `CONTEXT_OK` si hay CUALQUIER
  objeto D1, sin importar `trend` ni dirección. O sea: D1 hoy NO aporta sesgo
  direccional al PlanFSM (solo "hay contexto"). Para gobernar dirección,
  `emit_d1` debiera leer `trend` y emitir dirección, no solo presencia.
- `emit_h4` (l.45-56) sí chequea BOS/CHOCH (sesgo), pero ignora `trend` del
  market_structure y el `pd_side`.
- El PlanFSM no produce una "decisión de dirección" consumible por run_sequence:
  `plan_step` devuelve `PlanState` (un estado de madurez del plan), no una
  dirección ni un SL.
- `top_down_allows_trade` (context_mtf.py:136) SÍ hace gate direccional
  D1→H4→H1→PD, pero el PlanFSM NO lo usa; está solo en el motor v2 legacy
  (no versionado, auditoría R6 marcó no reproducible).

**Veredicto:** el PlanFSM tiene la FORMA (FSM + emisores por TF) pero no el
CONTENIDO direccional. Hoy gobierna "madurez del plan" (CONTEXT_OK→IN_TRADE),
no "dirección + autorización de setup". Para ser el único cerebro necesita que
sus emisores emitan dirección (no solo presencia) y que su estado se traduzca a
una decisión que run_sequence consuma.

---

## 7. SI HOY REEMPLAZÁRAMOS H4→M15 POR PlanFSM GOBERNANDO, ¿QUÉ FUNCIONA Y QUÉ SE ROMPE?

Escenario: activar `plan_gate=True` y subir umbral a ENTRY_READY/IN_TRADE (ya
soportado por `run_plan_fsm`) para que el PlanFSM autorice la señal.

**Funciona correctamente:**
- El PlanFSM ya filtra por madurez de cascada (D1+H4 → H1 POI → M15 setup →
  M5/M1 confirm). Las señales que no lleguen a STRUCTURE_OK se vetan.
- Anti-look-ahead respetado (`_objs_before` por `bar_time`).
- `run_sequence` sigue generando (AC1 cumplido); el conteo de señales no cambia.
- El veto es explicable (estado FSM por señal).

**Dejaría de funcionar / se rompe:**
- **Dirección macro**: el PlanFSM no emite dirección; run_sequence sigue
  sacándola de H4 (sequence.py:380). O sea: el PlanFSM gobierna "si opera" pero
  NO "hacia dónde". La dirección sigue siendo H4-only. No cerraría la Brecha A1
  (3 capas reales) en la dirección.
- **POI anclado (Brecha B)**: `emit_h1` usa `role=POI` de MarketObjects H1, no
  el POI anclado HTF de Fase C (`htf_pd_index`). Si los MarketObjects H1 no
  llevan `role=POI`, H1 emite `ZONE_INVALID` y el plan nunca pasa de CONTEXT_OK
  → TODAS las señales vetadas. Riesgo alto de matar señales por falta de POI en
  H1 (coherente con el veredicto Fase E: POI como filtro duro da PF 0.900).
- **Premium/discount (Brecha C)**: el PlanFSM lo ignora (emit_d1/h4 no leen
  pd_side). No se aplicaría.
- **SL/volatilidad**: siguen en run_sequence (M15). El PlanFSM no los toca
  (correcto, pero entonces no es "único cerebro", solo "cerebro de autorización").

Conclusión: activar `plan_gate` hoy convierte al PlanFSM en **compuerta de
madurez**, no en **cerebro de dirección**. Cierra parcialmente la Brecha A1
(exige D1+H4+H1+M15 presentes) pero NO la dirección multi-capa ni el POI
anclado ni premium/discount.

---

## 8. BRECHAS QUE IMPIDEN QUE PlanFSM SEA EL ÚNICO CEREBRO

Enumeradas, con evidencia de código:

1. **B1 — PlanFSM no emite dirección.** `emit_d1` solo prueba presencia de
   objetos (l.38-42); no lee `trend` ni dirección. `plan_step` devuelve
   `PlanState`, no dirección. run_sequence sigue dueño de la dirección
   (sequence.py:380). → El PlanFSM no puede suplantar la decisión H4→M15.

2. **B2 — POI anclado desconectado del PlanFSM.** Fase C (`htf_pd_index`) está
   cableada a `zone_authority` (bonus) pero `emit_h1` busca `role=POI` en
   MarketObjects H1 (plan_emitters.py:63-71). Si no hay `role=POI`, H1 =
   ZONE_INVALID → veto total. El POI anclado HTF no llega al PlanFSM como
   veredicto. → Brecha B no cerrada en el PlanFSM.

3. **B3 — Premium/discount ignorado.** `pd_side` de D1/H4 está en el
   `MultiTFContext` (context_mtf.py:122-126) pero ningún emisor lo lee. →
   Brecha C no cerrada en el PlanFSM.

4. **B4 — PO3/AMD no evaluado por el PlanFSM.** `compute_po3_complete` se calcula
   en canonical.py pero el PlanFSM solo lo bonifica en `score_plan` (+0.5). →
   Brecha E no cerrada como gate.

5. **B5 — `top_down_allows_trade` (gate direccional real) no está conectado al
   PlanFSM.** Existe en v2/context_mtf.py:136 pero solo se usa en el motor v2
   legacy (no versionado). Hay DOS implementaciones de gate direccional (una en
   PlanFSM por madurez, otra en top_down_allows_trade por dirección) y ninguna
   es la fuente única del PlanFSM.

6. **B6 — Duplicación de cerebro en dirección H4.** run_sequence lee H4 trend
   (sequence.py:380); el PlanFSM también (emit_h4). Dos lecturas de H4, ninguna
   unificada como "decisión de dirección" del sistema.

7. **B7 — Contrato de "un solo cerebro" no cumplido en la práctica.** El doc
   `ETAPA_4_FASE_C_PLAN.md:93` dice "Un solo cerebro. C es capa de CONTEXTO, no
   de decisión". Hoy hay DOS: run_sequence (dirección+setup+SL) y PlanFSM
   (madurez). Para que el PlanFSM sea el único, run_sequence debe delegarle la
   dirección y el POI, quedando como motor de setup/SL puro.

---

## RESUMEN DE EVIDENCIA (sin propuesta)

- El PlanFSM tiene la FORMA arquitectónica (FSM + emisores por TF + anti
  look-ahead) pero NO el CONTENIDO: no emite dirección, no consume POI anclado,
  no consume premium/discount, no evalúa PO3 como gate.
- Hoy gobierna solo la MADUREZ del plan (ejecución/autorización), no la
  DIRECCIÓN ni el SETUP. La dirección, el setup, el SL y la volatilidad siguen
  100% en run_sequence/canonical.
- Activar `plan_gate` (umbral ENTRY_READY) funcionaría como compuerta de
  madurez, pero NO cerraría las Brechas A1 (dirección multi-capa), B (POI
  anclado), C (premium/discount) ni E (PO3) en el PlanFSM, porque sus emisores
  no leen esos datos.
- Para ser el ÚNICO cerebro, el PlanFSM necesita: (a) emisores que emitan
  DIRECCIÓN (no solo presencia), (b) consumir POI anclado Fase C, (c) consumir
  pd_side, (d) evaluar PO3, y (e) que run_sequence delegue la dirección y el POI
  (quitando su lectura de H4 trend y su hook htf_poi_fn muerto). Eso requiere
  MODIFICAR la arquitectura de los emisores y el contrato run_sequence↔PlanFSM.
- Existe `top_down_allows_trade` (gate direccional real) pero fuera del PlanFSM
  y en motor legacy no versionado.

Estado: PlanFSM NO puede ser hoy el único cerebro sin ampliar sus capacidades
(Brechas B1-B7). La evidencia está en los archivos citados.
