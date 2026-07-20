# Roadmap — Biblioteca 10/10 y aplicación al sistema

**Fecha:** 2026-07-19  \
**Propósito:** convertir la documentación ICT/Wyckoff en **contrato ejecutable** y cerrar el gap libro → código → backtest → observador.  \
**No sustituye** `CRONOGRAMA_Y_ROADMAP.md` (hitos A6/A12/R7). Este doc es el plan de **calidad documental + cableado PO3/modelos**.  \
**Actualización 2026-07-19:** R7 unificación COMPLETADA (motores legacy BOS/CHOCH/TREND eliminados; canónico `ict_backtest/market_structure.py` es única fuente de verdad). Diseño de temporalidades/FSM y roadmap por capacidades (Plan/Setup/Ejecución/Optimización) en `docs/plan/ARQUITECTURA_TEMPORALIDADES.md` + `docs/plan/ROADMAP_CAPACIDADES.md` como vista superpuesta sobre los hitos R. **Actualización 2026-07-20:** A1 Nivel 2 CERRADA (Opción B, FSM como compuerta de ejecución en `run_backtest`, `run_sequence` intacto). **MIGRACIÓN ATR→RANGO Fase 1 CERRADA (2026-07-20):** única fuente de volatilidad del motor = `avg_candle_range` (rango high-low puro, sin ATR/Wilder); ver hito Fase 1 de `CRONOGRAMA_Y_ROADMAP.md`.

> **NOTA DE CONTRATO (2026-07-17):** la biblioteca ICT de este doc se convertirá en
> el **contrato formal de la tesis** en `docs/ict/SPEC_TESIS_FORMAL.md` (Fase 0 del
> roadmap maestro `ROADMAP_TESIS_DRIVEN_2026-07-17.md`). Esa SPEC es el CONTRATO
> FUENTE: ninguna regla se implementa sin estar primero en la SPEC, y la matriz de
> trazabilidad (§9 del roadmap maestro) se mantiene sincronizada con ella. Este doc
> queda al día al commitear el roadmap maestro.

---

## 1. Principios

1. **Un número, un sitio** → `docs/METRICS_CANON.md`.
2. **Un contrato, un detector/checklist** → cada libro §0 debe poder codificarse.
3. **Vivo = backtest** → una sola función de evaluación (sin copias divergentes).
4. **Medir antes de optimizar** → ablación y WF antes de Optuna agresivo.
5. **Trader manda** → no bot de órdenes hasta A12 + autorización.

---

## 2. Estado de la biblioteca (post reescritura 10/10)

| Área | Acción documental | Estado docs |
|------|-------------------|-------------|
| ICT 01–11 | Estándar ADR-021 + contrato §0 + métricas por enlace | ✅ Reescritos |
| `METRICS_CANON.md` | Fuente única de PF/WR | ✅ Creado |
| `_PLANTILLA_LIBRO.md` | Plantilla obligatoria | ✅ Creada |
| Wyckoff | Mapeo código + § aplicación | ✅ Elevado |
| Índices | Actualizados | ✅ |

---

## 3. Roadmap de aplicación al **código** (orden estricto)

### R0 — Congelar contratos (0.5 día) · docs only
- [x] Contratos §0 en libros (PO3 A/M/D, FVG, OB, Sweep, Turtle, Silver Bullet, Killzones).
- [x] Revisar con operador (Ruben/Eva): ¿aceptamos el "PO3 completo" tal cual? **DECIDIDO 2026-07-13: SÍ, PO3 completo (A+M+D obligatorias) aprobado tal cual por libro 08. Base para R1 `po3_state`.**

**Criterio de done:** checklist firmado o “approved” en este archivo.

---

### R1 — Capa de estado de modelos (2–4 días) · código

| Tarea | Detalle | Archivos |
|-------|---------|----------|
| R1.1 | `po3_state` con A/M/D + `complete` + `direction` | `signals/po3.py` ✅ |
| R1.2 | `evaluate(model="po3")` **separado** de Turtle Soup | `ict_backtest/rules.py` ✅ |
| R1.3 | Misma función importada por UI | `app_observador/ui/resumen_widget.py` ✅ |
| R1.4 | Tests sintéticos: solo A, solo M, A+M+D, sin look-ahead | `tests/test_po3.py` ✅ |

**Criterio de done:** pytest verde; UI muestra "PO3 completo / incompleto".  \n**Estado 2026-07-13:** R1 COMPLETO — 8/8 tests `tests/test_po3.py` pasan; UI muestra bloque "ESTADO PO3 (A/M/D)".

---

### R2 — Alinear killzones y zona horaria (1 día)

| Tarea | Detalle | Archivos |
|-------|---------|----------|
| R2.1 | Documentar y unificar TZ: UTC canónico + display operador configurable (env SMC_TZ, default Ecuador) | `docs/plan/DECISION_TZ.md`, `app_observador/core/timezone.py` ✅ |
| R2.2 | Vivo y backtest llaman al mismo `killzone_activa_ahora()` (UTC) | `resumen_widget.py` ✅ / `ict_backtest/rules.py` (ya UTC) |
| R2.3 | UI muestra reloj en zona operador + bandas UTC y operador | `mt5_status.py`, `resumen_widget.py` ✅ |
| R2.4 | Tests de bandas London/NY y override por env | `tests/test_timezone.py` ✅ |

**Criterio de done:** pytest verde; UI y backtest coinciden en "en killzone"; reloj mostrado en zona operador.  \n**Estado 2026-07-13:** R2 COMPLETO — 6/6 `tests/test_timezone.py` pasan; KZ-1 cerrado; helper único UTC + display Ecuador (o SMC_TZ). KZ-2 (unificar `detectors/killzones.py` del mapa) queda fuera de R2.

---

---

### R3 — Cerrar huecos de arquitectura documentados (3–5 días)

| Hueco (libro) | Acción |
|---------------|--------|
| Liquidez pinta ≠ sweep filtra (`05`) | Unificar o documentar adapter único `liquidity_context` consumido por pipeline | ✅ R3: `detectors/liquidity_context.py` (`canonical_sweep`); `detect_bos` + `signals/pipeline.py` delegan |
| OTE ~1% no-op (`10`) | Ajustar bandas o desactivar peso hasta WF OOS del test propuesto | 🔶 R4 (decisión + walk-forward; no es código) |
| Open del día en PO3 (`08`) | Feature `session_open` + filtro manipulación vs open | ✅ PO3-2 (R3): `compute_session_open` + filtro duro en `signals/po3.py` |
| CHOCH→BOS gate off (`02`) | Re-medir en XAUUSD + costos; no forzar en EURUSD naive | ✅ gate cableado (default OFF); re-medición en XAUUSD = R4 |

**Criterio de done:** cada hueco = issue cerrado o "wontfix" con razón en METRICS/ libro.  \n**Estado 2026-07-13:** R3 completo en arquitectura — PO3-2 y Liquidez (05) cerrados con código + tests; OTE (10) y CHOCH-gate (02) resueltos como trabajo de R4 (medición/decisiones, no arquitectura).

---

### R3.5 — Cerrar huecos del canon ICT en la TESIS (URGENTE · 2026-07-13)

**Fuente:** `20_TESIS_ICT.md` § investigación de gaps (2026-07-13). La tesis unifica PO3/estructura/liquidez/temporalidad/SL, pero se escapa de 3 capas del canon ICT que separan un setup "ok" de uno "institucional". El backtest v29 ya probó que el SL estructural da edge (PF>1); el siguiente cuello es la CALIDAD de la entrada, no el stop.

| Hueco (canon ICT) | Por qué es urgente | Estado repo | Tarea |
|-------------------|-------------------|-------------|-------|
| **SMT Divergence** (filtrar manipulación real vs continuación) | Sin SMT el robot entra en sweeps que pueden ser continuación, no caza de stops. Es el filtro de entrada más fuerte de ICT. | ❌ Sin detector; ningún libro lo cubre a fondo | Libro `21_SMT_DIVERGENCIA.md` + detector `detectors/smt.py` (par correlacionado EURUSD/DXY, mismo TF) |
| **Breaker Block / MMXM** (zona de entry alternativa al FVG) | El robot solo entra en FVG; ICT usa breaker como falla de OB que se vuelve resistencia. MMXM es el "mapa" del ciclo. | ❌ `ob.py` existe pero no breaker/MMXM | Libro `22_BREAKER_MMXM.md` + extender `detectors/ob.py` con breaker state |
| **OTE (Optimal Trade Entry)** | Entry por retrace a 62–79% Fib del swing, no solo "retorno a FVG". `detectors/fib.py` YA existe pero no integrado en la tesis ni en entry. | ⚠️ `fib.py` existe; libro 10 dice OTE ~no-op; tesis no lo integra | Libro `23_OTE_FIB.md` + cablear OTE como zona de entry en `build_signals_from_frames` |

**Acción documental inmediata (esta sesión):**
- [x] Libros 14/15/16/17/20 creados y en `00_INDICE.md` (SL estructural, intradía, temporalidad, scalping, tesis).
- [x] **Libro 18 `EJECUCION_OPTIMA_TF_SL_ENTRY.md`** — REGLA DURA 3 capas HTF/ITF/exec, SL/entry SIEMPRE en exec TF, RR 1:3, 3 killzones, M5 estándar / M1 avanzado. Creado 2026-07-14 (commit `46b074e`).
- [x] Libros 15/16/17/20 corregidos a la regla 18 (ITF agregado, RR 1:3, M3, killzones London/NY PM).
- [ ] Crear libros 21 (SMT), 22 (Breaker/MMXM), 23 (OTE) y enlazarlos a la tesis 20.
- [x] **Libro `21_POI.md` CREADO (2026-07-15):** POI = PD Array en zona correcta + sesgo + respaldo; tiers; stacking MTF; **bonus, no filtro duro**. Investigado en fuentes ICT reales (InnerCircleTrader, ictkillzone, fxopen). Tesis §5b + índice actualizados.
- [ ] Crear libros 22 (Breaker/MMXM), 23 (OTE).
- [ ] Actualizar tesis 20 § con los 3 huecos como "pendiente de integración".

**Acción de código (bloquea R4 honesto):**
- [ ] `detectors/smt.py`: divergencia EURUSD vs DXY (o par correlacionado) en mismo TF.
- [ ] `detectors/ob.py`: breaker block state tras falla de OB.
- [ ] `build_signals_from_frames`: entry requiere SMT confirmando el sweep + OTE/Breaker como zona (no solo FVG).
- [ ] **Fase E (POI) corregida (2026-07-15):** POI del libro 21 = PD Array ITF en zona correcta + sesgo + respaldo + ancla narrativa HTF. Aplicar como **BONUS de quality_score**, NO como filtro duro (A'' filtro duro = PF 0.900, rechazado). Pendiente cablear en `sequence.py`/`engine.py`.
- [x] **Fase E (Diagnosis Engine — motores de análisis) ✅ CERRADA 2026-07-18:** StatisticsEngine/CorrelationEngine/HypothesisEngine solo-lectura sobre TradeContext v2; orquestrador `diagnosis_report.py`. 23 tests TDD. Corrida real EURUSD 6m (36 trades): sin edge concluyente (n<30 por cohorte), única señal tenue M5 coef +0.27. Ver `docs/plan/ETAPA_DIAGNOSIS_ENGINE_FASE_E.md` + `CRONOGRAMA_Y_ROADMAP.md` fila E. (No confundir con la Fase E POI de este bloque: son fases distintas; esta es post-backtest, aquella es filtro de calidad de entrada.)
- [x] **A1 Nivel 2 (loop driver FSM → compuerta de EJECUCIÓN) ✅ CERRADA Opción B (2026-07-20, TDD RED→GREEN→Demo→Verify):** `run_sequence` INTACTO; `run_sequence_backtest` gana kwarg `plan_gate=False` (default → comportamiento histórico 100% intacto). La FSM (`PlanFSM` + emisores Fases 1–4) gobierna la **EJECUCIÓN de trades**, NO la generación de señales. Umbral inicial `STRUCTURE_OK`. `plan_step`/`run_plan_fsm` en `ict_backtest/plan_driver.py` (reusan `_objs_before` + `emit_*`); `_field` en `ict_backtest/plan_emitters.py` acepta dict O `ICTSignal` (gap de compatibilidad detectado por auditoría de call site real). `_objs_before` movido a `ict_backtest/plan_fsm.py` (rompe import circular `plan_attach ↔ plan_driver`). Tests `tests/test_plan_gate_a1.py` (4, incl. call site real en `run_backtest`) + demo `scripts/plan_gate_demo.py`. **AC cumplidos:** mismo nº de señales generadas / solo cambia nº de trades ejecutados / cada veto registrado con su estado (`m["vetoes"]`). 25/25 suite `plan_*`. Subir a `ENTRY_READY` = Fase 2 de A1 (kwarg umbral). Ver `docs/plan/AUDITORIA_TESIS_FASE5.md` §9 + `CRONOGRAMA_Y_ROADMAP.md` fila A1 Nivel 2.
- [x] **Fase 1 — Lectura multitemporal (causa raíz de la brecha A1) ✅ CERRADA (2026-07-20, TDD RED→GREEN + call site real + verify empírico):** Resuelve la infraestructura de lectura, NO la estrategia. Causa raíz real: el motor usaba interfaz de 1-HTF (`canonical.est_htf_fn` leía `ms.get(htf)`), NO falta de datos (los 6 TF YA estaban en disco: `data/raw/*_{D1,H4,H1,M15,M5,M1}.parquet`). Nuevo `ict_backtest/multitf_context.py`: `MultiTFContext` + `build_multitf_context` (reusa `v2/context_mtf.build_context_stack`, closed-only anti look-ahead) + `extract_htf_layer`. `canonical.evaluate_signals` carga TF_CHAIN completa (`D1,H4,H1,M15,M5,M1`) y pasa `est_htf_ctx_fn` a `run_sequence`; `run_sequence` acepta `est_htf_ctx_fn`+`htf` y reduce vía `extract_htf_layer(context, htf)` (Opción A: decide con el MISMO HTF de hoy → 100% idéntico al baseline de 1 nivel). `run_sequence` NO cambia su lógica interna. Evidencia demostrada: (1) 6 TF llegan ✓; (2) sin look-ahead (`build_context_stack` vía `closed_row_at_time`) ✓; (3) `run_sequence` recibe `MultiTFContext` (test call site real) ✓; (4) idéntico al baseline (tests sintéticos + `scripts/fase1_verify.py` sobre EURUSD real, entry_at iguales) ✓; (5) tests verdes ✓; (6) doc ✓. Los otros 5 TF viajan disponibles en el contexto pero NO influyen todavía (Fase 2 decidirá cómo aprovecharlos, con evidencia). Ver `docs/plan/AUDITORIA_TESIS_FASE5.md` §10 + `CRONOGRAMA_Y_ROADMAP.md` fila Fase 1.
- [x] **Brecha A1 real (cascada D1→H4→H1 en motor) ✅ CERRADA (2026-07-20, TDD + call site real):** `run_sequence` ahora llama `top_down_allows_trade` (v2/context_mtf.py:136) y veta si la dirección choca con la cascada D1/H4/H1. El motor deja de decidir solo en H4. Tests `tests/test_a1_topdown_filter.py` (6). Ver DEC-009i (Ruben elige C: PlanFSM → cerebro de dirección, modifica DEC-009f).
- [x] **Fase B2 (exec TF M5/M1) ✅ CERRADA (2026-07-20, TDD + call site real):** `evaluate_signals` gana `exec_tf` (default M15, regresión cero); entry/SL/TP se reanclan al TF fino cuando se pide. M15 sigue como LTF y default. Tests `tests/test_b2_exec_tf.py` (4). MDS_B2_EXEC_M5_M1.
- [x] **Brecha A (POI anclado bonus) ✅ CERRADA (2026-07-20, TDD + call site real):** hook `htf_poi_fn` (hasta hoy None) ahora recibe `make_htf_poi_fn` desde canonical cuando `enable_pd_index=True`; anota `poi_present` (nunca veta, rol bonus Fase E). Nuevo `ict_backtest/poi_filter.py`; `ICTSignal.poi_present` en engine.py. Tests `tests/test_a_poi_anchored.py` (12).
- [x] **RR por setup → TP real ✅ CERRADA + APLICADA (2026-07-20, TDD RED→GREEN + call site real del pipeline):** `canonical._rr_for_raw_signal(s, ltf_df, direction, ltf)` resuelve el setup de la señal CRUDa vía los detectores reales (`is_silver_bullet`/`is_turtle_soup`/`is_ote_entry`) y aplica `rr_target` al TP (`tp = entry ± rr_target*risk`), reemplazando el `3.0*risk` fijo. SB 1:2 / Turtle 1:1.5 / OTE 1:3 / default 1:3. Regresión cero (sin setup → RR 3.0 histórico). Tests `tests/test_rr_applied_to_tp.py` (4). Ver `CRONOGRAMA_Y_ROADMAP.md` fila RR por setup + DEC-009l.
- [x] **E1 Trade Management → simulador ✅ CERRADA + APLICADA (2026-07-20, TDD RED→GREEN + call site real):** `ict_backtest/trade_mgmt.py` con `to_breakeven`/`partial_exit`/`trailing_stop` (funciones puras) + `apply_trade_management(entry, sl, tp, direction, df, ...)` = call-site real que el backtest usará para gestionar el trade post-entry (parcial en tp1 + BE + trailing + cierre en TP/SL/BE, PnL ponderado). NO backtest de PF (bloqueado hasta Fase G); solo unidad con serie sintética. Tests `tests/test_e1_trade_mgmt.py` (19) + `tests/test_e1_applied_trade_mgmt.py` (3). Ver `CRONOGRAMA_Y_ROADMAP.md` fila E1 + DEC-009l.
- [ ] Re-correr R4 v30 CON SMT+OTE+Breaker antes de declarar edge.

**Prioridad:** URGENTE. Sin SMT, la medición de R4 (v30) sobre-estima el edge (entra en manipulaciones falsas). El SL estructural (v29) ya resolvió el stop; estos 3 resuelven la entrada.

**Criterio de done:** libros 21/22/23 en índice + detectores smt/breaker cableados + tesis 20 actualizada + R4 v30 incluye los 3 filtros.

---

---

### R4 — Medición aislada (2–3 días)

| Experimento | Qué |
|-------------|-----|
| E1 | Baseline intradia mezcla (actual) |
| E2 | Solo PO3 `complete=True` a-favor | ✅ E2 corrido: PF 0.286 (8 trades, muestra minima) — sin edge |
| E3 | Solo Turtle Soup `counter_trend=True` | ✅ E3 corrido: PF 0.689 (466 trades) — pierde sistematicamente |
| E4 | Solo Silver Bullet (kz + sweep + FVG) | ⏳ pendiente (sugerido antes de descartar ICT intradia M15) |
| E5 | Con `--cost` en todos | ✅ E5 corrido: empeora (PO3 0.194, Turtle 0.511) |

**Estado 2026-07-13:** E2/E3/E5 completados y reportados en METRICS_CANON §8.1.  \
**Veredicto:** NINGUN modelo aislado supera el gate (PF ≥1.10). PO3 aislado = muestra  \
mínima (8 trades), no concluyente; Turtle aislado = PF 0.689 concluyente sin edge.  \
**Decision:** NO Optuna sobre estos modelos; documentado "sin edge en EURUSD M15".  \
Falta E4 (Silver Bullet) para cerrar el analisis del stack ICT intradia en M15.

**ACTUALIZACIÓN 2026-07-14 (post-auditoría look-ahead):**
- **Look-ahead CRÍTICO corregido** (`6d4b158`/`07afc0e`): el join H4→M5 leía velas sin cerrar. Medido: 97.4% de velas M15/M5 contaminadas por HTF futuro. Los PF de v2.7 (Turtle 1.14) eran FALSO positivo.
- **Re-medición v2.7 tras limpiar look-ahead:** E4 Silver Bullet PF 0.896/0.639 → **RECHAZADO**; PO3+displacement 2/0 trades → INCONCLUSO; **Turtle Soup PENDIENTE v2.8** (único que rozó el gate).
- **SL Estructural v29** (`e2a9c11`): SL anclado a mecha del sweep. EURUSD PF 1.128 / GBPUSD PF 2.101 PERO sostenido en `hold_limit` (7/11 y 11/13 cerraron por hold, no TP). Rentable pero el éxito vive del hold.

**Turtle Soup v2.8 ALINEADO A TESIS 18 (2026-07-14):** `run_backtest.py` camino sequence usa SL mecha sweep + RR 1:3 + killzone. EURUSD M15 H4→M15 = **0 señales** (1787→170→92→0). El retorno al cuadro no ocurre tras el BOS con SL estructural. Veredicto: **no concluyente** (0 trades, no PF<1.10). GBPUSD pendiente.

**Gate:** no Optuna hasta que E2 o el modelo elegido tenga PF OOS medio ≥1.10 **y** ningún fold <1 **o** se documente "frágil aceptado para paper".

---

### R4-tesis — Tesis de ejecución óptima (libro 18) · docs ✅ · código 🟡 (2026-07-14)

**Fuente:** `docs/ict/18_EJECUCION_OPTIMA_TF_SL_ENTRY.md` (regla dura, commit `46b074e`).

| Tarea código | Detalle | Archivos | Estado |
|--------------|---------|----------|--------|
| SL estructural (mecha sweep) en sequence | `run_backtest.run_sequence_backtest` usa `calc_structural_sl` (no BOS±ATR) | `ict_backtest/run_backtest.py` | ✅ R4-clean |
| RR 1:3 en sequence | TP = liquidez opuesta o entry±3R | `ict_backtest/run_backtest.py` | ✅ R4-clean |
| Killzone en sequence | filtro London/NY AM/NY PM | `ict_backtest/run_backtest.py` | ✅ R4-clean |
| `exec_tf` explícito | `build_signals_from_frames` recibe `exec_tf`/`itf` separados de `ltf` | `ict_backtest/engine.py:44` | ❌ R4-tesis/v30 |
| M3 en `TF_FREQ` | agregar M3 (intermedio M5→M1) | `ict_backtest/engine.py:250` | ❌ R4-tesis/v30 |
| Killzones London/NY PM en checklist | cablear las 3 KZ en camino checklist/scalping | `ict_backtest/rules.py` | ❌ R4-tesis/v30 |

**Criterio de done:** el motor produce SL/entry en el exec TF correcto (M5 scalping / M15 intradía) y la tesis 18 deja de depender de la coincidencia `exec_tf==ltf`. Camino sequence/Turtle Soup YA alineado; falta checklist/scalping (v30).

---

### R7 — Unificar motor de decisión (single source of truth) · 🔒 Fase 1+2 CONGELADAS + AMPLIADAS post-auditoría

**Reabierto como proyecto INDEPENDIENTE de R9** (R9 cerrado 2026-07-15: su
contrato era la representación MarketObject, NO eliminar engine.py). Ver
**`docs/plan/R7_UNIFICACION_MOTOR.md`** (contrato oficial + auditoría R7).

**Contrato oficial (2026-07-15, ampliado tras auditoría crítica):**
- Motor canónico = **sequence.py** (sobre MarketObject[]).
- engine.py degradado a helpers puros (`simulate_trade`, `calc_structural_sl`,
  `_tp_liquidity`); ubicación física diferida a implementación.
- `build_signals_from_frames` eliminado; consumidores documentados (1.4 del doc).
- **Default del runner en sequence** (no opt-in).
- **ict_agent delega en sequence** (H1); **legacy/backtest y ml/dataset_builder
  DOCUMENTADOS fuera de alcance** con decisión explícita (H2/H3).
- **DoD fortalecido**: no se declara "una sola fuente" mientras exista motor ICT
  paralelo o consumidor no redirigido; check_separation incluye ict_agent/
  legacy/ml (H10).
- **Anti-lookahead HTF** preservado como requisito arquitectónico (H8).

**Fase 3 (TDD) — COMPLETADA (2026-07-15):**
- **T3.1:** el runner por defecto (`run_backtest.run`) delega en `run_sequence_backtest` (motor canónico); ya no usa `build_signals_from_frames`. API pública intacta.
- **T3.2A:** consumidores secundarios (`scripts/_smoke.py`, `scripts/plot_trade_structsl.py`, `__init__.py`, `ict_backtest/_smoke.py`) redirigidos al motor canónico → 0 consumidores vivos (ver `tests/test_r7_t32a_consumers.py`).
- **T3.2B:** `build_signals_from_frames` BORRADA de `engine.py` (isla eliminada); test consumidor `test_r4_po3_isolated.py` eliminado. Eliminación mecánica de código muerto, SIN tocar lógica ICT ni `bos_gap`. `simulate_trade`/`calc_structural_sl`/`_tp_liquidity`/`ICTSignal` preservados como helpers puros.
- **Cobertura TDD:** `test_r7_runner_default.py` (T3.1), `test_r7_t32a_consumers.py` (T3.2A), `test_r7_t32b_elimination.py` (T3.2B), `test_r7_divergence_investigation.py`, `test_r7_bosgap_rootcause.py`, `test_r7_ms_mutation.py`.
- **Batería:** 378 passed / 3 failed (los 3 failures son áreas fuera de alcance R7: POI en `sequence.py:182`, `ml/dataset_builder`, `ml_trainer` sklearn). Cero regresiones.
- **Deuda documentada → R10:** divergencia `bos_gap` (sequence.py=40 vs run_backtest.py=10) es número mágico antipatrón (PRINCIPIOS_ARQUITECTONICOS.md). No se unifica en R7; se derivará de estado estructural en R10.

**Estado:** R7 Fase 3 cerrada como refactor mecánico. Fases 4-6 (portar rules/po3/killzone a sequence, eliminar build_signals legacy, redirigir runner/agent/ml) DEFERIDAS; legacy/backtest y ml/dataset_builder siguen DOCUMENTADOS fuera de alcance.

### R9 — Migración del motor a MarketObject (refactor de tipo de dato) · ✅ COMPLETADO (2026-07-15)

**Principio:** R9 es una REFACTORIZACIÓN PURA. NO cambia ninguna regla ICT (POI, quality_score, narrativa, sweep, BOS, MSS, entry, risk). Solo cambia el tipo de dato interno: de columnas sueltas de pandas a `MarketObject[]` + `MarketNarrative` como representación canónica, manteniendo la interfaz legacy vía `translation.py`.

**Hecho (Paso 1 + 2 + 3, 2026-07-15):**
- `ict_backtest/object_adapter.py`: `objects_view(frames)` pasa `{tf: df}` por `build_objects` → `df_to_objects` (sella capa `origin_tf` + rol + `bar_index`/`bar_time`) → `objects_to_legacy_df` (FIEL: carga columnas del detector en `meta` y las devuelve tal cual) → reensambla por `bar_index` sobre el df original.
- `MarketObject` ahora lleva `bar_index`/`bar_time` (ancla a su vela de origen) + `ObjectType.CANDLE` (vista de vela para sequence).
- `tests/test_r9_object_adapter.py` (TDD): verifica sobre XAUUSD real recortado que `run_sequence(frames)` == `run_sequence(objects_view(frames))`: **16==16 señales, mismos trades, mismo PF/WR/expectancy**. Y `test_sequence_consumes_marketobject_equivalent`: `run_sequence(df)` == `run_sequence(MarketObject[])` → mismas señales/time/direction/entry/sweep_at/bos_at/entry_at. Baseline de equivalencia establecido y VERDE (15 tests).
- **Paso 3 (sequence.py migrado a MarketObject):** todas las funciones internas leen `MarketObject.meta` en lugar de `row_ltf[col]`. `run_sequence` acepta DataFrame O `list[MarketObject]`; convierte al inicio vía `_candle_objects` (NO toca translation.py). HTF context (`est_htf`) sigue como dict (no es columna LTF). `run_sequence_backtest` end-to-end verificado sin error.

**Matriz de migración (sequence.py — DataFrame → MarketObject):** ver tabla en versión previa (sin cambios: `_has_sweep`, `_has_displacement`, `_has_choch`, `_has_bos`, `_latest_fvg_zone`, `_latest_ob_zone`, `_touches_zone`, `run_sequence`, `_candle_objects`).

**Dependencias legacy restantes (fuera de alcance R9 Paso 3):**
1. `run_backtest.py` sigue pasando `ltf_df` (DataFrame) a `run_sequence`; sequence lo convierte internamente. Las columnas legacy siguen disponibles para `run_backtest` (lee `ltf_df.iloc[sweep_at]` para SL/sweep) y para `engine.simulate_trade`.
2. `engine.py` (`simulate_trade`, `ICTSignal`, `calc_structural_sl`, `_tp_liquidity`) consume DataFrame (`ltf_df.iloc[...]`). NO migrado en R9 (otro módulo; columnas legacy intactas).
3. `est_htf_fn(i)` devuelve dict del HTF (contexto de capa superior, no columna LTF). No es DataFrame.
4. `translation.py` / `objects_to_legacy_df()` / `object_adapter.py` → INTACTOS (capa de compatibilidad).

**Criterio de done (R9 COMPLETADO):** el motor de decisión `sequence.py` piensa 100% en `MarketObject[]` (no en columnas sueltas); la equivalencia de señales/trades/PF/WR/expectancy está probada y en verde; la capa de compatibilidad (translation/adapter) queda intacta. Ninguna métrica de baseline cambia por el refactor. **R9 NO incluía eliminar `engine.py` ni cablear `MarketNarrative`/POI bonus:** esos quedan fuera de alcance (deuda R7 y trabajo de narrativa posterior, respectivamente).**

**Aclaración de alcance (resuelve aparente tensión con la ontología):**
- `MarketNarrative` (MARKET_OBJECT_MODEL.md) es la VISIÓN DE LARGO PLAZO de la arquitectura objetivo; NO forma parte del alcance de R9 ni de R7. Su ausencia en `sequence.py` hoy no invalida el contrato: R9/R7 operan sobre `MarketObject` sin exigir la capa narrativa.
- `quality_score` y `POI bonus` son CAPACIDADES FUTURAS contempladas en la ontología. Empíricamente, el filtro duro POI HTF empeoró los resultados (Fase F: A'' PF 0.900 vs A' PF 1.511) y fue EXCLUIDO del alcance de R9 por decisión expresa. No son requisito para cerrar R9.
| Función | Antes (DataFrame) | Ahora (MarketObject) | Campo leído en obj.meta |
|---|---|---|---|
| `_has_sweep` | `row_ltf["liquidity_sweep_*"]` | `obj.meta["liquidity_sweep_*"]` | liquidity_sweep_down/up |
| `_has_displacement` | `row_ltf["displacement_*"]` | `obj.meta["displacement_*"]` | displacement_bullish/bearish |
| `_has_choch` | `row_ltf["choch_dir"]` | `obj.meta["choch_dir"]` | choch_dir |
| `_has_bos` | `row_ltf["bos_dir"]`/`choch_dir` | `obj.meta["bos_dir"]`/`choch_dir` | bos_dir, choch_dir |
| `_latest_fvg_zone` | `row_ltf["fvg_*"]`/`high`/`low` | `obj.meta[...]` | fvg_bullish/bearish, high, low |
| `_latest_ob_zone` | `row_ltf["ob_direction"]`/`open`/`close` | `obj.meta[...]` | ob_direction, open, close |
| `_touches_zone` | `row_ltf["low"]`/`high` | `obj.meta["low"]`/`high` | low, high |
| `run_sequence` | `ltf_df.iloc[i][col]` | itera `objs` (MarketObject[]) | time, close, bos_level, atr |
| `_candle_objects` (nueva) | — | DataFrame → `list[MarketObject(CANDLE)]` | TODOS los campos ICT por vela |

### R5 — Datos A6 (bloqueante A12) (1–N días, MT5)

- [ ] Descargar ≥3–4 años M15 XAUUSD (+ EURUSD)
- [ ] Rebuild contextos harness si aplica (`_ctx/*.pkl`)

---

### R6 — Backtest profesional: reloj, fill, costos (2–4 días) · docs ✅ · código ⏳

**Libro:** `docs/ict/13_BACKTEST_PROFESIONAL/`  
**Plan detallado:** `docs/plan/PLAN_BACKTEST_PROFESIONAL.md`  
**Motivación:** auditoría 2026-07-13 — el LTF es reloj correcto, pero HTF se lee incompleto; fill al close; costos no default.

| Tarea | Detalle | Estado |
|-------|---------|--------|
| R6.0 | Congelar contrato libro 13 + review operador (`next_open` default) | 📄 docs ✅ · review ⏳ |
| R6.1 | HTF **closed-only** (`row_at_time` + merge_asof) + test multi-TF | ⏳ G1 |
| R6.2 | `fill_mode=next_open` default producción | ⏳ G2 |
| R6.3 | Cost pack ON por default en runners (`--no-cost` = theory) | ⏳ G3 |
| R6.4 | Re-medir Capa 2/3 (ablation reloj) → **METRICS_CANON** | 🟢 corrido (R6.4 multi-símbolo en METRICS_CANON §0) |
| R6-v2 | Motor multi-TF `ict_backtest/v2` (D1→H4→H1→M15) corrido 2026-07-17: 7 majors, costos ON, OOS 0.3. 0-4 trades/símbolo, ningún gate pasa, coverage v2_partial 86.1% (C06 POI missing). Reporte: `docs/avances/BACKTEST_V2_MTF_REPORTE_2026-07-17.md` | 🟢 corrido |
| R6.5 | DSR/PBO / veredicto auto en optimize ICT (opcional) | ⏳ G6–G7 |
| R6.6 | Gaps sesión, portafolio prop, régimen (post R5) | ⏳ no bloquea sello v1 |

**Criterio de done (sello v1 profesional):** G1+G2+G3 + tests + METRICS actualizado.  
**Gate:** no Optuna agresivo ni declarar edge de producción hasta R6.4.
- [ ] Actualizar `METRICS_CANON` tras re-run

Scripts: `download_multiyear.py`, `download_xauusd_m15.bat`.  
MT5: `C:\Program Files\FundedNext MT5 Terminal\terminal64.exe`.

---

### R6 — Walk-forward + Optuna acotado (A12 / Capa 3)

- [ ] Re-run A12 celda `no_session` × XAUUSD tras A6
- [ ] Optuna **pocos** params (≤6) solo sobre modelo ganador de R4
- [ ] WF multi-fold, dirección pasado→futuro, costos ON

**Gate duro (cronograma):** DSR>0, N≥200/fold si posible, PF≥1.10 OOS.

---

### R7 — Observador óptimo (sin bot)

- [ ] Panel: fases A/M/D visuales en mapa o checklist
- [ ] Diario: ficha “réplica del ciclo” del día
- [ ] Shadow mode: log “hubiera entrado PO3” sin orden
- [ ] **No** reactivar loop 24/7 en máquinas que lo desactiven (`start_local.ps1`)

---

### R8 — Paper / live (solo si R6 pasa + autorización)

- Paper trading runner
- Vigilante 2%/4%
- Cumplimiento FundedNext (`tools/fundednext_compliance.py`)
- Deployment A8 al final

---

## 4. Timeline sugerido (calendario)

| Semana | Foco |
|--------|------|
| S0 | R0 revisión contratos + merge docs |
| S1 | R1 PO3 estado + tests + UI |
| S1–S2 | R2 killzones unificadas |
| S2 | R3 huecos (open día, liquidez, OTE decisión) |
| S3 | R4 medición aislada + costos |
| S3–S4 | R5 A6 datos MT5 |
| S4+ | R6 WF/A12 |
| Luego | R7 shadow · R8 solo con OK humano |

---

## 5. Matriz libro → tarea de código

| Libro | Contrato clave | Tarea código primaria |
|-------|----------------|----------------------|
| 01 Killzones | Ventana horaria unificada | Helper único UTC/broker |
| 02 MSS/CHoCH | Secuencia BOS→CHOCH→BOS | Gate opcional; re-test XAUUSD |
| 03 FVG | 3 velas + unfilled | Ya OK; aislar contribución |
| 04 OB | Valid + followthrough post-cierre | Vigilar `shift(-1)` en entrada |
| 05 Liquidez | Sweep = filtro | Unificar fuente de verdad |
| 06 Turtle Soup | Contra + sweep + MSS | `model="turtle"` separado |
| 07 Silver Bullet | KZ + sweep + FVG | `model="silver_bullet"` |
| 08 PO3 | A+M+D complete | **R1 prioridad #1** |
| 09 Optuna | WF + no overfit | Solo tras R4 |
| 10 Sweep+OTE | Pesos con evidencia | Fix OTE o peso 0 |
| 11 Manual vs Auto | Automation-ready | Shadow log, no ejecutor aún |

---

## 6. Definition of Done — “sistema óptimo en el tema PO3”

1. Libro 08 contrato A/M/D implementado en código.  
2. UI y backtest llaman la misma función.  
3. Métricas aisladas PO3 en `METRICS_CANON` con costos.  
4. WF multi-fold sin fold muerto **o** etiqueta explícita “frágil / solo paper”.  
5. Shadow en diario ≥ N días sin desincronía UI↔log.  
6. A6 datos suficientes para no repetir fallo A12 por N bajo.

---

## 7. Anti-objetivos

- No reescribir `signals/pipeline.py` “por estética” (regla edge diagnosis).  
- No optimizar 20 parámetros a la vez.  
- No declarar PF sin costos.  
- No bot de órdenes en esta fase.

---

*Documento vivo. Actualizar checkboxes al cerrar cada R#.*
