# Evidencia — Reconciliación de Verdad y Autoridad (baseline SDD-00)

**Repositorio:** `C:\Users\v_jac\Desktop\SMC-SYSTEMS`
**Rama:** `feature/backtest-ict` · **HEAD:** `9842394`
**Fecha de recolección:** 2026-08-07
**Método:** claim-vs-code. Toda afirmación lleva cita `archivo:línea`.
**Modo:** solo lectura. No se modificó, movió ni versionó ningún archivo del repositorio.

## Leyenda de estados

| Estado | Significado |
|--------|-------------|
| SUPPORTED | El código o el archivo confirma la afirmación tal como está escrita. |
| CONTRADICTED | El código o el árbol de archivos dice lo contrario. |
| STALE | Fue cierto en algún momento; el referente cambió de ruta, de nombre o desapareció. |
| UNVERIFIED | No se encontró evidencia suficiente ni a favor ni en contra. |
| MISSING | El referente citado no existe en ninguna parte del repositorio. |

---

## Cadena de autoridad

### Hallazgo central

Los tres archivos que se auto-cargan en el contexto de todo agente
(`AGENTS.md`, `README.md`, `opencode.json`) apuntan mayoritariamente a rutas que
**ya no existen**. La reorganización documental del 2026-08-05 (`docs/plan/`
purgado, roadmaps movidos a `docs/planificacion/_roadmap_historico/`, documentos
del bot heredado movidos a `docs/_descartado/`) **no se propagó** a los archivos
de configuración ni a los índices de la raíz.

### Nivel 1 — Normativo hoy (citable como "la tesis")

| Documento | Ruta real | Evidencia de vigencia |
|-----------|-----------|----------------------|
| Ley arquitectónica motor-vs-backtest | `AGENTS.md:3-39` | Auto-cargado en todo agente; contiene la ley fundamental |
| Contrato formal de la estrategia | `docs/ict/SPEC_TESIS_FORMAL.md` | `docs/ict/SPEC_TESIS_FORMAL.md:8` — `Estado: CONTRATO FUENTE (FIRMADA 2026-07-20). Precede al código (R1).` |
| Decisión de backtest único | `docs/DECISION_BACKTEST_UNICO.md` | `docs/DECISION_BACKTEST_UNICO.md:5` — `**Estado:** VIGENTE. Fuente de verdad para la arquitectura de backtest.` |
| Números de performance | `docs/METRICS_CANON.md` | `docs/METRICS_CANON.md:3` — `**Única fuente de números de performance para la documentación.**` (⚠ ver caveat abajo) |
| Capa LTF de ejecución | `docs/tesis/SDD_LTF_ENTRY_LAYER.md` | `docs/tesis/SDD_LTF_ENTRY_LAYER.md:5` — `**Estado:** Fase 1 en ejecución; Fases 2-5 pendientes de OK por fase.` |
| Bitácora viviente | `docs/bitacora/bitacora_trabajo.md` | `docs/bitacora/bitacora_trabajo.md:3-5` — `Fuente de verdad viviente junto con AGENTS.md y la tesis (docs/tesis/).` |
| Hallazgos de estructura y sesgo | `docs/tesis/HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md`, `docs/tesis/HALLAZGOS_SESGO_BACKTEST.md` | Sin marcador de obsolescencia; el primero está modificado sin commitear |
| Biblioteca ICT (libros) | `docs/ict/00_INDICE.md` + libros `01`–`21` | `docs/ict/00_INDICE.md:7` — `**Fuente de verdad:** código del repo + auditorías + METRICS_CANON` |
| El motor | `engine/` (20 módulos `.py`) | `AGENTS.md:12` — `El motor (engine/) es la ÚNICA fuente de decisión.` |

**Caveat sobre `docs/METRICS_CANON.md`:** se declara única fuente de números
pero su fecha de actualización es `docs/METRICS_CANON.md:6` — `**Actualizado:** 2026-07-17`,
es decir **anterior** a la construcción del motor `engine/` (posterior al
2026-07-21 según `docs/planificacion/_roadmap_historico/PUNTO_DEL_ROADMAP_2026-08-05.md:9-12`).
Todos sus PF/WR miden `ict_backtest/`, no el motor actual. Además cita scripts
que ya no están en su ruta (ver tabla de claims).

### Nivel 2 — Histórico explícito (no citable como verdad presente)

Los 21 documentos de `docs/planificacion/_roadmap_historico/` llevan marcador
propio en las líneas 1 y 10 de cada archivo. Ejemplos verificados:

- `docs/planificacion/_roadmap_historico/CRONOGRAMA_Y_ROADMAP.md:1` — `> ⚠️ **DOCUMENTO HISTÓRICO (recuperado 2026-08-05 del commit d0a5f20).**`
- `docs/planificacion/_roadmap_historico/HOJA_DE_RUTA_SMC-SYSTEMS.md:17` — `> ⚠️ **DOCUMENTO OBSOLETO — NO USAR COMO FUENTE DE VERDAD**`
- `docs/planificacion/_roadmap_historico/PLAN_IMPLEMENTACION_ETAPAS.md:15` — `> **⚠️ SUPERSEDED** — Contrato de ingeniería original (2026-07-17).`
- `docs/planificacion/_roadmap_historico/DECISION_LOG.md:1`, `DECISION_TZ.md:1`, `ETAPA_0_BASELINE.md:1`, `ETAPA_1_VALIDACION.md:1`, `ETAPA_2_DEPENDENCY.md:1`, `ETAPA_3_IMPLEMENTATION.md:1`, `ETAPA_4_BUGS.md:1`, `ETAPA_4_FASE_B1_PLAN.md:1`, `ETAPA_DIAGNOSIS_ENGINE_FASE_E.md:1`, `ETAPA_DIAGNOSIS_ENGINE_MTF.md:1`, `ETAPA_DIAGNOSIS_ENGINE_PLAN.md:1`, `IMPLEMENTATION_PLAN.md:1`, `PRINCIPIOS_ARQUITECTONICOS.md:1`, `PROJECT_PROTOCOL.md:1`, `PROPUESTA_BRECHA_A1_CABLEADO_TOPDOWN.md:1`, `R7_UNIFICACION_MOTOR.md:1`, `ROADMAP_BIBLIOTECA_Y_APLICACION.md:1`, `ROADMAP_TESIS_DRIVEN_2026-07-17.md:1` — todos con el mismo marcador HISTÓRICO.

**Excepción de valor:** `docs/planificacion/_roadmap_historico/PUNTO_DEL_ROADMAP_2026-08-05.md`
**no** lleva el marcador de historicidad y se declara mapa vivo:
`docs/planificacion/_roadmap_historico/PUNTO_DEL_ROADMAP_2026-08-05.md:58-60` —
`Los roadmaps originales están en docs/planificacion/_roadmap_historico/ marcados / como HISTÓRICOS (no fuente de verdad). Este archivo es el mapa vivo del punto`.
Está guardado **dentro** de la carpeta histórica, lo que induce a descartarlo por
ubicación. Es un defecto de clasificación, no de contenido.

Índice de la carpeta: `docs/planificacion/INDICE_PLANES.md:26-29`.

### Nivel 3 — Descartado

`docs/_descartado/` (con subcarpetas `arquitectura/`, `auditorias/`, `proposals/`),
indexado en `docs/_descartado/INDICE_DESCARTE.md:20-23`. Contiene, entre otros,
las dos copias supervivientes de `COMPLETION_REPORT.md`.

### Nivel 4 — Sin marcador, autoridad ambigua

`docs/auditorias/` (14 documentos) y `docs/avances/` (7 documentos) **no llevan
ningún marcador de vigencia u obsolescencia** en su cabecera. Varios describen
estados del backtest de julio 2026 que ya fueron superados por el motor. Un
agente que los abra los tomará por vigentes. Ejemplo:
`docs/avances/BACKTEST_V2_MTF_REPORTE_2026-07-17.md` describe un motor que
`docs/DECISION_BACKTEST_UNICO.md:19-24` declara **PROHIBIDO** reintroducir.

### Verificación de existencia y ubicación real (solicitada explícitamente)

| Documento buscado | Ruta que afirma la doc | Ruta REAL | Estado |
|-------------------|------------------------|-----------|--------|
| `SPEC_TESIS_FORMAL.md` | `docs/tesis/` (`AGENTS.md:124`) | **`docs/ict/SPEC_TESIS_FORMAL.md`** | STALE (existe, otra ruta) |
| `TRUTH_SOURCES.md` | `docs/tesis/` (`AGENTS.md:125`) | **no existe** — nunca en el árbol actual; fue añadido en el commit `2b384c7` como `docs/tesis/TRUTH_SOURCES.md` y hoy no está trackeado ni en disco | MISSING |
| `docs/CRONOGRAMA_Y_ROADMAP.md` | `docs/` (`README.md:24`, `README.md:332`) | **`docs/planificacion/_roadmap_historico/CRONOGRAMA_Y_ROADMAP.md`**, marcado HISTÓRICO en su línea 1 | STALE + degradado |
| `COMPLETION_REPORT.md` | raíz (`AGENTS.md:42`, `README.md:239`, `README.md:333`, `opencode.json:25`) | **borrado de la raíz** (`git status`: `D COMPLETION_REPORT.md`); sobreviven `docs/_descartado/COMPLETION_REPORT.md` y `docs/_descartado/auditorias/COMPLETION_REPORT.md` | CONTRADICTED |
| `docs/DECISION_BACKTEST_UNICO.md` | `docs/` (`AGENTS.md:38`) | `docs/DECISION_BACKTEST_UNICO.md` | SUPPORTED |
| `docs/METRICS_CANON.md` | `docs/` (`AGENTS.md:97`) | `docs/METRICS_CANON.md` | SUPPORTED |
| `docs/tesis/SDD_LTF_ENTRY_LAYER.md` | — | `docs/tesis/SDD_LTF_ENTRY_LAYER.md` | SUPPORTED |
| `docs/planificacion/_roadmap_historico/PUNTO_DEL_ROADMAP_2026-08-05.md` | — | igual | SUPPORTED |
| `docs/plan/` (carpeta) | `AGENTS.md:82`, `opencode.json:13-21` | **no existe** (`Test-Path docs\plan` → `False`) | MISSING (purga intencional, `AGENTS.md:120-122`) |

**Contenido real de `docs/tesis/`** (solo 3 archivos): `HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md`,
`HALLAZGOS_SESGO_BACKTEST.md`, `SDD_LTF_ENTRY_LAYER.md`. Ni `SPEC_TESIS_FORMAL.md`
ni `TRUTH_SOURCES.md` están ahí, pese a que `AGENTS.md:122` declara `docs/tesis/`
como fuente de verdad vigente.

### Cadena de autoridad propuesta (ranking para citar "la tesis" hoy)

1. `AGENTS.md:3-39` — Ley arquitectónica motor-vs-backtest (constitución).
2. `docs/ict/SPEC_TESIS_FORMAL.md` — contrato formal firmado de la estrategia.
3. `docs/DECISION_BACKTEST_UNICO.md` — arquitectura del backtest, vigente y fechada 2026-08-05.
4. `engine/` — el código del motor (`AGENTS.md:12`: única fuente de decisión).
5. `docs/tesis/SDD_LTF_ENTRY_LAYER.md` — capa LTF, la fase en curso.
6. `docs/bitacora/bitacora_trabajo.md` — cronología de decisiones (la más reciente).
7. `docs/planificacion/_roadmap_historico/PUNTO_DEL_ROADMAP_2026-08-05.md` — diff honesto motor vs roadmap.
8. `docs/ict/` libros `01`–`21` — reglas ICT por concepto.
9. `docs/METRICS_CANON.md` — **solo** para números del backtest hasta 2026-07-17.

Histórico exclusivo: todo `docs/planificacion/_roadmap_historico/` (salvo el
punto 7) y todo `docs/_descartado/`.

---

## Tabla de claims

### A. Claims de `AGENTS.md` (auto-cargado en todo agente)

| # | Claim | Origen | Evidencia | Estado |
|---|-------|--------|-----------|--------|
| A1 | `engine/` nunca importa `ict_backtest/` | `AGENTS.md:25-26` | Ningún módulo de `engine/*.py` importa `ict_backtest`; `engine/sequence.py:52` importa `engine.poi_anchor`, `engine/htf_narrative.py:24` idem | SUPPORTED |
| A2 | Backtest canónico = `ict_backtest/run_backtest.run_sequence_backtest` | `AGENTS.md:29` | `ict_backtest/run_backtest.py:193` — `def run_sequence_backtest(symbol: str, htf: str, ltf: str, max_hold: int,` | SUPPORTED |
| A3 | Backtest canónico = `ict_backtest/v2/orchestrator.run_sequence_parity` | `AGENTS.md:30` | `ict_backtest/v2/orchestrator.py:89` — `def run_sequence_parity(` | SUPPORTED |
| A4 | El backtest llama a `engine/sequence.run_sequence` | `AGENTS.md:31` | `engine/sequence.py:641` — `def run_sequence(ltf_df_or_objs: Any, est_htf_fn, cfg: SequenceConfig,` | SUPPORTED |
| A5 | `run_mtf_intraday` / `generate_mtf_signals` fueron eliminados | `AGENTS.md:37-38` | Búsqueda repo-wide sobre `*.py` (tracked + untracked): **cero** coincidencias. Solo aparecen en prosa de `docs/` | SUPPORTED |
| A6 | Ver `docs/DECISION_BACKTEST_UNICO.md` | `AGENTS.md:38` | El archivo existe y está VIGENTE (`docs/DECISION_BACKTEST_UNICO.md:5`) | SUPPORTED |
| A7 | "Lee siempre README.md y COMPLETION_REPORT.md" | `AGENTS.md:42` | `COMPLETION_REPORT.md` borrado de la raíz (`git status`: `D COMPLETION_REPORT.md`) | CONTRADICTED |
| A8 | "Actualiza este opencode.json…" (dentro de AGENTS.md) | `AGENTS.md:43` | Redacción heredada: el archivo se llama `AGENTS.md`, no `opencode.json`. Confunde qué archivo editar | STALE |
| A9 | Existe `scripts/runner_monitor.py` | `AGENTS.md:53`, `AGENTS.md:61` | `Test-Path scripts\runner_monitor.py` → `True` | SUPPORTED |
| A10 | Detalle del runner en `docs/plan/RUNNER_MONITOR.md` | `AGENTS.md:82` | `docs/plan/` no existe; `RUNNER_MONITOR.md` no existe en **ninguna** ruta del repo | MISSING |
| A11 | Ablation R6 vía `scripts/r6_ablation.py` | `AGENTS.md:86` | Ruta real: `scripts/_legacy/r6_ablation.py` (movido a legacy) | STALE |
| A12 | Números R6.4 en `docs/METRICS_CANON.md` §0 | `AGENTS.md:97` | `docs/METRICS_CANON.md` §0 contiene la tabla; los valores coinciden | SUPPORTED |
| A13 | "3 capas reales CERRADAS" vía `engine/plan.py` `build_context_stack` + `top_down_allows_trade` | `AGENTS.md:104-105` | `engine/plan.py:313` — `def build_context_stack(`; `engine/plan.py:364` — `def top_down_allows_trade(`. El default de TFs es `("D1", "H4", "H1", "M15")` (`engine/plan.py:317`) | SUPPORTED |
| A14 | `engine/poi_anchor.py` ancla POI a BOS/CHOCH del TF padre cerrado | `AGENTS.md:106` | El archivo existe pero está **UNTRACKED** (`git status`: `?? engine/poi_anchor.py`). Consumido por `engine/sequence.py:52`, `engine/htf_narrative.py:24`, `ict_backtest/canonical.py:42`, `ict_backtest/run_backtest.py:33` | SUPPORTED (con riesgo, ver §Riesgo) |
| A15 | `engine/htf_narrative.py` marca `poi["anchored"]` | `AGENTS.md:107` | `engine/htf_narrative.py:152` — `poi["anchored"] = bool(htf_poi_fn(len(frame) - 1, tnum))`; ramas `False` en `:154` y `:156` | SUPPORTED |
| A16 | El backtest lo consume en `run_backtest.py:479` con `enable_pd_index=True` | `AGENTS.md:107-108` | Línea real: `ict_backtest/run_backtest.py:505` — `enable_pd_index=True,  # Fase C: autoridad de zonas HTF como METADATA (sin gate, R1 se preserva)`. La línea 479 es texto de ayuda de un `argparse` (`ict_backtest/run_backtest.py:476-479`, flag `--invalidate-on-opposite-swing`) | STALE (línea equivocada por 26) |
| A17 | `enable_pd_index=True` → `ict_backtest.poi_filter` | `AGENTS.md:108` | `ict_backtest/poi_filter.py` está **BORRADO** (`git status`: `D ict_backtest/poi_filter.py`). La lógica POI vive hoy en `engine/poi_anchor.py`, importada por `ict_backtest/canonical.py:42` — `from engine.poi_anchor import build_htf_structure_index, make_htf_poi_fn, poi_present` y anotada en `ict_backtest/canonical.py:191` — `# --- Fase C (C1): POI anclado = UNICA fuente engine.poi_anchor (Ley). ---` | CONTRADICTED |
| A18 | `dealing_range.py` y `liquidity_levels.py` COMPLETOS en el motor | `AGENTS.md:110` | `engine/dealing_range.py` y `engine/liquidity_levels.py` existen | SUPPORTED |
| A19 | Falta en el motor: exec fino M5/M1 | `AGENTS.md:115` | Cerrado después: `docs/tesis/SDD_LTF_ENTRY_LAYER.md:5` (Fase 1 ejecutada) y commit `03c8539` — `Fase 1 LTF (exec fino M5/M1)...`. `engine/plan.py:330` recorre `LTF_TFS`; `engine/micro.py` y `engine/execution.py` existen | STALE |
| A20 | Falta fix del sesgo NEUTRAL perpetuo en `engine/bias/narrative.py` `_bias_from_swings` | `AGENTS.md:116` | El símbolo `_bias_from_swings` **ya no existe** en `engine/bias/narrative.py` (sus `def` son `_compose_htf_bias:52`, `_swing_points:102`, `_label_swings:141`, `_bias_for_frame:158`, `compute_htf_bias:210`, `compute_htf_bias_series:234`). Fue eliminado según `docs/bitacora/bitacora_trabajo.md:281` — `lazy import para no ciclar). Eliminados \`_bias_from_swings\` y`, y el bug fue corregido (`docs/bitacora/bitacora_trabajo.md:275-276`) | CONTRADICTED |
| A21 | Fuentes de verdad: `docs/tesis/SPEC_TESIS_FORMAL.md` | `AGENTS.md:124` | Ruta real `docs/ict/SPEC_TESIS_FORMAL.md` | STALE |
| A22 | Fuentes de verdad: `docs/tesis/TRUTH_SOURCES.md` | `AGENTS.md:125` | No existe en disco ni en `git ls-files`. Última traza: añadido en commit `2b384c7` (`chore(repo): from-zero reset aligned to SPEC_TESIS_FORMAL`) | MISSING |
| A23 | Fuente de verdad vigente = `AGENTS.md` + `docs/tesis/` + `engine/` | `AGENTS.md:120-122` | `docs/tesis/` contiene solo 3 archivos y **ninguno** es la tesis formal ni las fuentes de verdad citadas dos líneas más abajo. Contradicción interna del propio AGENTS.md | CONTRADICTED |
| A24 | Regla commit/push: no commitear sin OK de Rubén | `AGENTS.md:120` | Regla de proceso, no verificable en código. Reforzada por `docs/METRICS_CANON.md` §8.2b — `Parches aplicados (autorizados por Ruben, SIN commit — regla de hierro)` | UNVERIFIED (regla de proceso, se asume vigente) |
| A25 | Bloqueo real = DATOS (R5/A6) | `AGENTS.md:118` | Ninguna corrida posterior lo confirma ni lo niega en el árbol actual | UNVERIFIED |

### B. Claims de `README.md`

| # | Claim | Origen | Evidencia | Estado |
|---|-------|--------|-----------|--------|
| B1 | `docs/CRONOGRAMA_Y_ROADMAP.md` es la ÚNICA fuente de verdad | `README.md:24`, `README.md:332` | Ruta inexistente; el archivo real está en `docs/planificacion/_roadmap_historico/CRONOGRAMA_Y_ROADMAP.md` y su línea 1 lo marca HISTÓRICO. Además `AGENTS.md:120-122` designa otra fuente de verdad | CONTRADICTED |
| B2 | `python -m harness` ejecuta el framework de pruebas | `README.md:310` | `harness/` contiene **un solo archivo**: `harness/README.md`. No hay `__init__.py` ni `__main__.py`. El comando no puede resolverse | CONTRADICTED |
| B3 | Harness: 11 adapters, 14 scenarios | `README.md:45`, `harness/README.md` (tabla de adapters) | Ningún adapter, fixture ni scenario existe en disco | CONTRADICTED |
| B4 | `harness/` = "Harness-first testing framework" en el árbol del proyecto | `README.md:264` | Directorio vacío salvo su README | CONTRADICTED |
| B5 | El venv `smc_probe` tiene stub de MT5 | `README.md:91` | `Test-Path .\smc_probe` → `False`; `Test-Path C:\Users\v_jac\smc_probe` → `True`. Vive **fuera** del repositorio; el README no lo indica | STALE |
| B6 | Checklist completo en `COMPLETION_REPORT.md` (raíz) | `README.md:239`, `README.md:333` | Borrado de la raíz; copias en `docs/_descartado/` | CONTRADICTED |
| B7 | `docs/EDGE_DIAGNOSIS_REPORT.md` | `README.md:162`, `README.md:334` | Ruta real: `docs/avances/EDGE_DIAGNOSIS_REPORT.md` | STALE |
| B8 | `docs/ESTADO_ACTUAL.md` | `README.md:335` | Ruta real: `docs/avances/ESTADO_ACTUAL.md` | STALE |
| B9 | `docs/RUTINA_EURUSD.md` | `README.md:336` | Ruta real: `docs/rutinas/RUTINA_EURUSD.md` | STALE |
| B10 | `docs/AUDITORIA_USO_2026-07-09.md` | `README.md:337` | Ruta real: `docs/_descartado/auditorias/AUDITORIA_USO_2026-07-09.md` (descartado) | STALE + degradado |
| B11 | `docs/AGENT_ARCHITECTURE.md` | `README.md:338` | Ruta real: `docs/_descartado/arquitectura/AGENT_ARCHITECTURE.md` | STALE + degradado |
| B12 | `docs/DEPLOYMENT_GUIDE.md` | `README.md:340` | Ruta real: `docs/_descartado/arquitectura/DEPLOYMENT_GUIDE.md` | STALE + degradado |
| B13 | `docs/ICT_RULEBOOK.md` | `README.md:341` | Ruta real: `docs/reglas/ICT_RULEBOOK.md` | STALE |
| B14 | `docs/WYCKOFF_RULEBOOK.md` | `README.md:343` | Ruta real: `docs/reglas/WYCKOFF_RULEBOOK.md` | STALE |
| B15 | `docs/HOJA_DE_RUTA_SMC-SYSTEMS.md` quedó obsoleta y redirige | `README.md:25` | Ruta real: `docs/planificacion/_roadmap_historico/HOJA_DE_RUTA_SMC-SYSTEMS.md`; su `:39` redirige a `docs/CRONOGRAMA_Y_ROADMAP.md`, que tampoco existe (redirección rota en cadena) | STALE |
| B16 | `pyinstaller smc_trading.spec` en la raíz | `README.md:299` (bloque de packaging) | Ruta real: `bin/smc_trading.spec` | STALE |
| B17 | `docs/specs/app_observador.md` | `README.md:185`, `README.md:339` | Existe | SUPPORTED |
| B18 | `scripts/edge_diagnosis/run.py` | `README.md:288` | Existe | SUPPORTED |
| B19 | `scripts/loop_analisis.py`, `scripts/rutina_eurusd.py`, `scripts/vigilante_riesgo.py`, `run_app.py`, `app_observador/main.py`, `start_hermes_session.ps1` | `README.md:284`, `README.md:283` y tabla de scripts | Todos existen | SUPPORTED |
| B20 | Arranque automático diario vía Carpeta de Inicio | `README.md:103-118` | Contradicho por `docs/bitacora/bitacora_trabajo.md:11-13` — `Auto-arranque con Windows **ELIMINADO**: el sistema corre solo bajo demanda`. Confirmado por los `.lnk` en `scripts/DisabledStartup/` (untracked) | CONTRADICTED |
| B21 | `ml/models/quality_filter.pkl` | `README.md` (tabla ML) | Existe | SUPPORTED |

### C. Claims de `docs/METRICS_CANON.md`

| # | Claim | Origen | Evidencia | Estado |
|---|-------|--------|-----------|--------|
| C1 | Script de ablation `scripts/r6_ablation.py` | `docs/METRICS_CANON.md` §0 | Ruta real: `scripts/_legacy/r6_ablation.py` | STALE |
| C2 | Script `scripts/r4_clean_funding_gate.py` | `docs/METRICS_CANON.md` §8.3 | Ruta real: `scripts/_legacy/r4_clean_funding_gate.py` | STALE |
| C3 | Referencia a `docs/plan/PLAN_BACKTEST_PROFESIONAL.md` | `docs/METRICS_CANON.md:9` | `docs/plan/` no existe; el archivo no aparece en ninguna ruta | MISSING |
| C4 | Referencia a `docs/plan/CRONOGRAMA_Y_ROADMAP.md` | `docs/METRICS_CANON.md` §1 | Ruta inexistente (ver B1) | STALE |
| C5 | Los PF/WR publicados describen el sistema actual | `docs/METRICS_CANON.md:6` | Fecha de actualización `2026-07-17`, anterior al motor `engine/` (`docs/planificacion/_roadmap_historico/PUNTO_DEL_ROADMAP_2026-08-05.md:9-12`) | STALE |

### D. Claims sobre otros índices

| # | Claim | Origen | Evidencia | Estado |
|---|-------|--------|-----------|--------|
| D1 | Estándar de escritura en `../plan/ADR-021_filosofia_documentacion_ict.md` | `docs/ict/00_INDICE.md:10` | `docs/plan/` purgado; `ADR-021*` no existe en ninguna ruta | MISSING |
| D2 | Aplicación al sistema en `../plan/ROADMAP_BIBLIOTECA_Y_APLICACION.md` | `docs/ict/00_INDICE.md:11` | Ruta real: `docs/planificacion/_roadmap_historico/ROADMAP_BIBLIOTECA_Y_APLICACION.md`, marcado HISTÓRICO | STALE |
| D3 | `SPEC_TESIS_FORMAL.md` vinculado a la matriz de `ROADMAP_TESIS_DRIVEN_2026-07-17.md` §9 | `docs/ict/SPEC_TESIS_FORMAL.md:9-10` | El roadmap existe pero en `docs/planificacion/_roadmap_historico/ROADMAP_TESIS_DRIVEN_2026-07-17.md:1`, marcado HISTÓRICO. Un contrato VIGENTE depende de una matriz de trazabilidad HISTÓRICA | STALE |
| D4 | El estándar documental es ADR-021 / DEC-009e | `docs/ict/SPEC_TESIS_FORMAL.md:7` | Ninguno de los dos documentos existe en el repo | MISSING |

---

## Referencias rotas en AGENTS.md / opencode.json / README.md

### `opencode.json` — instrucciones auto-cargadas

`opencode.json:12-27` declara 14 archivos de instrucciones. **10 de 14 no resuelven.**

| Índice JSON | Clave / valor | Existe | Estado |
|-------------|---------------|:------:|--------|
| `instructions[0]` | `opencode.json:13` `docs/plan/PROJECT_PROTOCOL.md` | ✗ | STALE — existe en `docs/planificacion/_roadmap_historico/PROJECT_PROTOCOL.md`, marcado HISTÓRICO |
| `instructions[1]` | `opencode.json:14` `docs/plan/VISION.md` | ✗ | MISSING — no existe en ninguna ruta |
| `instructions[2]` | `opencode.json:15` `docs/plan/PRD.md` | ✗ | MISSING |
| `instructions[3]` | `opencode.json:16` `docs/plan/SRS.md` | ✗ | MISSING |
| `instructions[4]` | `opencode.json:17` `docs/plan/SAD.md` | ✗ | MISSING |
| `instructions[5]` | `opencode.json:18` `docs/plan/RFC-001_actualizacion_biblioteca_ict.md` | ✗ | MISSING |
| `instructions[6]` | `opencode.json:19` `docs/plan/ADR-021_filosofia_documentacion_ict.md` | ✗ | MISSING |
| `instructions[7]` | `opencode.json:20` `docs/plan/ROADMAP_BIBLIOTECA_Y_APLICACION.md` | ✗ | STALE — existe en `_roadmap_historico/`, marcado HISTÓRICO |
| `instructions[8]` | `opencode.json:21` `docs/plan/RUNNER_MONITOR.md` | ✗ | MISSING |
| `instructions[9]` | `opencode.json:22` `docs/METRICS_CANON.md` | ✓ | SUPPORTED (contenido STALE, ver §C) |
| `instructions[10]` | `opencode.json:23` `AGENTS.md` | ✓ | SUPPORTED |
| `instructions[11]` | `opencode.json:24` `README.md` | ✓ | SUPPORTED (contenido con 16 claims rotos, ver §B) |
| `instructions[12]` | `opencode.json:25` `COMPLETION_REPORT.md` | ✗ | CONTRADICTED — borrado (`git status`: `D COMPLETION_REPORT.md`) |
| `instructions[13]` | `opencode.json:26` `harness/README.md` | ✓ | SUPPORTED como archivo; su contenido describe un framework inexistente (ver B2–B4) |

Además, `opencode.json:28-30` (`skills.paths = [".opencode/skills"]`) apunta a
`.opencode/skills`, que **no existe** (`Test-Path .opencode/skills` → `False`).
Estado: MISSING (no bloqueante, pero es configuración muerta).

**Consecuencia:** de las 14 instrucciones inyectadas, solo 3 aportan contexto
correcto (`AGENTS.md`, y parcialmente `METRICS_CANON.md` y `README.md`). Las 7
MISSING nunca existieron o desaparecieron sin dejar sustituto: **no se puede
"reparar la ruta", hay que decidir si se reescriben o se eliminan**.

### `AGENTS.md` — referencias rotas

| Línea | Referencia | Estado |
|-------|------------|--------|
| `AGENTS.md:42` | `COMPLETION_REPORT.md` | CONTRADICTED (borrado) |
| `AGENTS.md:82` | `docs/plan/RUNNER_MONITOR.md` | MISSING |
| `AGENTS.md:86` | `scripts/r6_ablation.py` | STALE → `scripts/_legacy/r6_ablation.py` |
| `AGENTS.md:107-108` | `run_backtest.py:479` | STALE → línea real `505` |
| `AGENTS.md:108` | `ict_backtest.poi_filter` | CONTRADICTED (módulo borrado) |
| `AGENTS.md:116` | `engine/bias/narrative.py` `_bias_from_swings` | CONTRADICTED (símbolo eliminado) |
| `AGENTS.md:124` | `docs/tesis/SPEC_TESIS_FORMAL.md` | STALE → `docs/ict/SPEC_TESIS_FORMAL.md` |
| `AGENTS.md:125` | `docs/tesis/TRUTH_SOURCES.md` | MISSING |

### `README.md` — referencias rotas

10 de 12 enlaces de la tabla de documentación (`README.md:332-343`) apuntan a
rutas inexistentes. Detalle en la tabla §B (B1, B6–B16). Los dos que resuelven
son `docs/specs/app_observador.md` (B17) y el propio `docs/METRICS_CANON.md`
cuando se cita por ruta completa.

### Importaciones de código rotas (efecto colateral de los borrados)

Estas rutas de import apuntan a módulos borrados en el árbol de trabajo. Son
`ImportError` garantizados si se ejecuta ese camino.

| Import | Módulo destino | Estado |
|--------|----------------|--------|
| `ict_backtest/plan_attach.py:100` — `from ict_backtest.poi_anchor import anchor_objects` | `ict_backtest/poi_anchor.py` (`D`) | CONTRADICTED — **código de producción**, no test |
| `scripts/cierre_brecha_b_demo.py:22` — `from ict_backtest.htf_pd_index import HtfPdZone` | `ict_backtest/htf_pd_index.py` (`D`) | CONTRADICTED |
| `scripts/verify_brecha_ce_cableado.py:21` — `from ict_backtest.htf_pd_index import HtfPdZone` | `ict_backtest/htf_pd_index.py` (`D`) | CONTRADICTED |
| `scripts/diagnose_bias_trace.py:21` — `_bias_from_swings` | símbolo eliminado de `engine/bias/narrative.py` | CONTRADICTED |
| `tests/test_poi_anchor.py:40,50,60,70` — `from ict_backtest.poi_anchor import anchor_objects` | `ict_backtest/poi_anchor.py` (`D`) | CONTRADICTED |
| `tests/test_plan_cableado_real.py:58` — `from ict_backtest.poi_anchor import anchor_objects` | `ict_backtest/poi_anchor.py` (`D`) | CONTRADICTED |
| `tests/test_fase_d_paso2_trade_context.py:94` — `from ict_backtest.zone_authority import ZoneAuthority` | `ict_backtest/zone_authority.py` (`D`) | CONTRADICTED |
| `tests/test_r10c_adapter.py:219` — `from ict_backtest.zone_authority import ZoneAuthority` | `ict_backtest/zone_authority.py` (`D`) | CONTRADICTED |

Nota metodológica: no se ejecutó `pytest` ni ningún import (restricción de solo
lectura). La conclusión se apoya en la ausencia del archivo destino en disco,
confirmada por `git status` y por el listado de `ict_backtest/`.

---

## Decisiones protegidas

Decisiones tomadas deliberadamente después de una auditoría. Revertirlas —
incluso por "limpieza" o por normalizar defaults — deshace trabajo previo y
reintroduce un regresor conocido.

### DP-1 — `require_pd=False` en el gate top-down (PRIORIDAD)

**Cita exacta, `engine/sequence.py:469-480`:**

```
469:        # BRECHA A1 (Opción B, filtro suave): la dirección objetivo debe
470:        # alinearse con la cascada top-down D1->H4->H1 del MultiTFContext
471:        # completo. Solo se aplica cuando el llamador pasó est_htf_ctx_fn
472:        # (modo multitemporal). Si es None (legacy sin contexto) el
473:        # comportamiento histórico queda INTACTO. El POI anclado NO es veto
474:        # (require_pd=False): según auditoría destruye edge; se usa como
475:        # bonus/anotación, no como gate duro.
476:        if est_htf_ctx_fn is not None and _ctx is not None:
477:            from engine.plan import top_down_allows_trade
478:            _ok, _reason = top_down_allows_trade(
479:                _ctx, target, counter_trend=cfg.counter_trend, require_pd=False,
480:            )
```

**Trampa crítica:** el default de la función es el contrario.
`engine/plan.py:371` — `    require_pd: bool = True,`. Si alguien elimina el
kwarg explícito de `engine/sequence.py:479` por "simplificar la llamada", el gate
duro se **reactiva silenciosamente** y se reintroduce el regresor. No hay test
que lo impida detectado en este barrido.

**Marcador gemelo, `engine/sequence.py:500-501`:**

```
500:            # POI anclado = motor (engine.poi_anchor). Anota poi_present (bool)
501:            # para metadata; NO es gate duro (el veto destruye edge).
```

**Marcador en el backtest, `ict_backtest/canonical.py:233`:**

```
233:        # backtest. as_gate=False: NO veta (el veto destruye edge), solo anota.
```

**Documento que respalda la razón — SÍ existe.** Estado del respaldo: SUPPORTED
(la afirmación "destruye edge" está documentada con números), con una salvedad
importante sobre el documento primario.

| Fuente | Cita | Peso |
|--------|------|------|
| `docs/ict/SPEC_TESIS_FORMAL.md:285-287` | `AMBIG: CRÍTICA empírica (tests/AUDITORIA_POI_REPORT): POI como filtro DURO destruye / edge (A'' PF 0.900 vs A' PF 1.511). Por eso es BONUS, no gate. Esto es regla de / tesis validada por evidencia, no ambigüedad.` | **Máximo** — contrato firmado y vigente |
| `docs/ict/20_TESIS_ICT.md:91` | `Usar POI HTF como filtro duro destruye el edge: **A'' PF 0.900** (perdedor) vs **A' PF 1.511** (rentable).` | Alto |
| `docs/ict/21_POI.md:92` | `La auditoría demostró que usar POI HTF como filtro duro destruye el edge (A'' PF 0.900 vs A' PF 1.511).` | Alto |
| `docs/planificacion/_roadmap_historico/CRONOGRAMA_Y_ROADMAP.md:94` | `A'' (POI HTF como FILTRO DURO): 31 trades \| PF 0.900 \| -1.7R  ← PERDEDOR` | Medio (documento HISTÓRICO, pero es la corrida original "Fase F") |
| `docs/planificacion/_roadmap_historico/PROPUESTA_BRECHA_A1_CABLEADO_TOPDOWN.md:105` | `como el POI duro (A'' PF 0.900), un filtro direccional duro PUEDE matar señales si el` | Medio |
| `docs/planificacion/_roadmap_historico/DECISION_LOG.md:490`, `:527` | `evita el pozo de A'' (gate duro HTF = PF 0.900)` | Medio |

**Salvedad — UNVERIFIED parcial:** el contrato apunta al artefacto primario
`tests/AUDITORIA_POI_REPORT` (`docs/ict/SPEC_TESIS_FORMAL.md:285`). Ese artefacto
**no fue localizado** en el árbol. El número `PF 0.900 / 31 trades / -1.7R` solo
sobrevive en documentos secundarios, y el más detallado
(`docs/planificacion/_roadmap_historico/CRONOGRAMA_Y_ROADMAP.md:94`) está marcado
HISTÓRICO en su línea 1. Además la corrida es del backtest de julio 2026, no del
motor `engine/` actual. **La decisión debe respetarse** (está en el contrato
firmado), pero **el dato crudo que la sostiene no es reproducible hoy**.

### DP-2 — Contrato de regresión cero por defecto

Varios flags están apagados por defecto de forma deliberada para preservar
comparabilidad histórica. Encenderlos "porque suena mejor" invalida las series.

| Marcador | Cita |
|----------|------|
| `engine/plan.py:381` | `comportamiento es identico al previo -> regresion cero.` (sobre `require_ltf=False`) |
| `engine/sequence.py:498-499` | `Sin / guarda (htf_poi_fn=None) el comportamiento es el historico.` |
| `engine/sequence.py:506-507` | `Hook historico: poi_ok decide si se memoriza la zona LTF. Con / htf_poi_fn=None es no-op (comportamiento historico intacto).` |
| `ict_backtest/run_backtest.py:477-479` | `OFF = regresion cero / (identico al historico).` (flag `--invalidate-on-opposite-swing`) |
| `ict_backtest/run_backtest.py:505` | `enable_pd_index=True,  # Fase C: autoridad de zonas HTF como METADATA (sin gate, R1 se preserva)` |

### DP-3 — Regla de hierro de commit/push

`AGENTS.md:120` — `**Regla commit/push (Ruben):** NO hacer commit ni push sin OK expreso.`

Precedente aplicado: `docs/METRICS_CANON.md` §8.2b registra parches funcionales
verificados que **no se commitearon** por esta regla. La regla explica —
parcialmente — por qué el árbol de trabajo lleva tantos cambios sin versionar
(ver §Riesgo). Estado: UNVERIFIED en código (es proceso humano), pero
consistentemente respetada en el historial documental.

### DP-4 — Purga intencional de `docs/plan/`

`AGENTS.md:120-122` — `Los roadmaps / (docs/plan/) fueron PURGADOS intencionalmente (2026-08-03)`.
No es un accidente ni un archivo perdido: **no se debe "restaurar" `docs/plan/`**.
Corolario para el SDD: las 9 entradas `docs/plan/*` de `opencode.json:13-21`
deben **eliminarse o reemplazarse**, nunca resucitarse.

### DP-5 — Prohibición de reintroducir el "backtest B"

`docs/DECISION_BACKTEST_UNICO.md:19-24`:

```
19: ## PROHIBIDO — no recuperar el backtest B
21: Queda prohibido reintroducir `ict_backtest/v2/strategy_mtf.py`
22: (`generate_mtf_signals`, `mtf_signals_to_plan`, `explanation_mtf`) ni
23: `ict_backtest/v2/orchestrator.run_mtf_intraday`, ni los scripts
24: `scripts/run_bt_v2_mtf.py` / `scripts/run_htf_mtf_window.py`.
```

Verificado: ninguno de esos símbolos existe en `*.py` (claim A5, SUPPORTED). La
prohibición está **cumplida hoy** y debe seguir así.

### DP-6 — Auto-arranque con Windows eliminado por decisión del trader

`docs/bitacora/bitacora_trabajo.md:11-13` — `Auto-arranque con Windows **ELIMINADO**: el sistema corre solo bajo demanda / (pedir "dame el bias de hoy" / "analiza la gráfica"). Hermes.lnk movido a / scripts/DisabledStartup/.`

`README.md:103-118` sigue documentando el arranque automático como producción.
Un agente que "arregle el README para que coincida con el código" podría
reactivarlo. **Es la documentación la que está mal, no el código.**

---

## Riesgo del árbol de trabajo

### Estado observado

Comandos ejecutados (solo lectura): `git status --porcelain`, `git log --oneline -10`,
`git diff --stat`.

**`git log --oneline -10` (rama `feature/backtest-ict`):**

```
9842394 Bitacora (11): plan de manana - render tipo TradingView del motor (D1)
565b501 Fase 2 (E1) cableado al backtest: Trade Mgmt BE+parciales + fix precision E1
cee5544 Orden del vigilante de riesgo: 2% perdida + $60 ganancia flotante
b9b7515 Bitacora + SDD LTF (Fase 1 ejecutada): exec fino M5/M1 cerrado, auditoria funnel vigente
03c8539 Fase 1 LTF (exec fino M5/M1): fallback SL a swing opuesto cuando mecha sweep invalida en TF fino
a3c29e5 Orden repo 2026-08-06: huérfanos de sesiones previas a carpetas _legacy/_archive/_broken (gitignored)
1db16d3 Auditoria de secuencia/funnel HTF: validacion del detector de setup (no P&L)
7fc4f0c T9.7: CHOCH requiere BOS real detras (tesis S7.0) + cierre revision HTF + hoja de ruta
7571593 T9.6: BOS vigente unico por direccion (superseded al reemplazar)
eff0955 T9.4/T9.5: CHOCH muere por cruce de BOS roto + sesgo HTF solo cuenta BOS real
```

**`git diff --stat`:** 11 archivos, 72 inserciones, **728 eliminaciones**.

### Borrados sin commitear (`D` en `git status`)

| Archivo | Líneas borradas | Impacto |
|---------|----------------:|---------|
| `ict_backtest/htf_pd_index.py` | 212 | Rompe `scripts/cierre_brecha_b_demo.py:22` y `scripts/verify_brecha_ce_cableado.py:21` |
| `ict_backtest/zone_authority.py` | 103 | Rompe `tests/test_fase_d_paso2_trade_context.py:94` y `tests/test_r10c_adapter.py:219` |
| `ict_backtest/poi_filter.py` | 74 | Invalida `AGENTS.md:108` (claim A17) |
| `ict_backtest/poi_anchor.py` | 88 | Rompe **`ict_backtest/plan_attach.py:100`** (código de producción), `tests/test_poi_anchor.py`, `tests/test_plan_cableado_real.py:58` |
| `ict_backtest/poi_anchor_motor.py` | 45 | Referenciado en prosa por `ict_backtest/po3_motor.py:3` |
| `COMPLETION_REPORT.md` | 188 | Invalida `AGENTS.md:42`, `README.md:239`, `README.md:333`, `opencode.json:25` |

### Altas sin trackear (`??` en `git status`)

| Archivo | Impacto |
|---------|---------|
| **`engine/poi_anchor.py`** | **Crítico.** Es el sustituto de los 3 módulos POI borrados. Lo importan `engine/sequence.py:52`, `engine/htf_narrative.py:24`, `ict_backtest/canonical.py:42`, `ict_backtest/run_backtest.py:33`. Un `git clean -fd` lo destruye y deja el motor sin arrancar. Un `git stash` sin `-u` lo deja fuera del stash |
| `tests/test_engine_poi_anchor.py` | Única cobertura del módulo anterior; también untracked |
| `tests/test_engine_plan_pd.py` | Cobertura de premium/discount en `engine/plan.py`; untracked |
| `scripts/request_daily_bias.py` | Entrada operativa del flujo "dame el bias de hoy" |
| `_audit_docstrings.py` | Script suelto en la raíz |
| `openspec/` | Este mismo directorio de trabajo SDD |
| `scripts/DisabledStartup/*.lnk` | Evidencia física de DP-6 |
| `data/histdata_tmp_probe/` | Datos temporales |

### Modificaciones sin commitear (`M`)

`_data_legacy.py` (+7/-…), `app_observador/core/engine.py` (+46), 
`docs/tesis/HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md` (+30), `.atl/skill-registry.md`,
`.atl/.skill-registry.cache.json`.

### Por qué esto rompe cualquier SDD que asuma baseline estable

1. **No hay commit que represente el estado actual.** `HEAD` (`9842394`) **todavía
   contiene** `ict_backtest/poi_filter.py`, `poi_anchor.py`, `zone_authority.py`,
   `htf_pd_index.py` y `COMPLETION_REPORT.md`, y **no contiene**
   `engine/poi_anchor.py`. Ni `HEAD` ni el árbol de trabajo describen un sistema
   coherente por sí solos: el sistema funcional solo existe en el **working tree**.
2. **El componente más crítico no está versionado.** `engine/poi_anchor.py` es
   untracked. Cualquier operación destructiva rutinaria (`git clean -fd`,
   `git checkout .`, `git stash` sin `-u`, cambio de rama con conflicto) lo elimina
   sin posibilidad de recuperarlo desde el historial.
3. **La migración `ict_backtest/*` → `engine/poi_anchor.py` está a medias.**
   `ict_backtest/plan_attach.py:100` sigue importando el módulo borrado. Es código
   de producción, no un test.
4. **Un SDD que cite `file:line` caduca en cuanto se commitee o se revierta algo.**
   Todas las citas de este documento son válidas contra el working tree del
   2026-08-07 sobre `9842394`. Si el árbol cambia, hay que re-verificar.
5. **`git bisect` y `git blame` son inútiles** para la mitad de la superficie
   afectada: los borrados y las altas no tienen commit.

### Mitigación mínima recomendada (requiere OK de Rubén, `AGENTS.md:120`)

Antes de empezar cualquier trabajo del SDD, congelar el estado. La opción no
destructiva y que no viola la regla de commit es un **stash con untracked**:

```
git stash push -u -m "baseline-sdd-00 2026-08-07"
git stash apply
```

Esto crea un objeto recuperable en el repositorio sin generar un commit en la
rama. Alternativa si Rubén autoriza: un commit WIP en una rama de respaldo.

---

## Preguntas abiertas para el autor del spec

1. **`TRUTH_SOURCES.md` (MISSING).** `AGENTS.md:125` lo declara fuente de verdad
   y no existe desde el reset `2b384c7`. ¿Se reescribe, se recupera del commit
   `2b384c7`, o se elimina la referencia y su rol lo absorbe la nueva cadena de
   autoridad?

2. **Contradicción interna de `AGENTS.md`.** La línea 122 dice que la fuente de
   verdad es `docs/tesis/`, pero las líneas 124-125 citan dos archivos que no
   están en `docs/tesis/`. ¿Se mueve `SPEC_TESIS_FORMAL.md` de `docs/ict/` a
   `docs/tesis/`, o se corrigen las rutas en `AGENTS.md` dejando el archivo donde
   está? Mover el archivo rompería las referencias de `docs/ict/00_INDICE.md`.

3. **`opencode.json` — 7 instrucciones MISSING sin sustituto.** `VISION.md`,
   `PRD.md`, `SRS.md`, `SAD.md`, `RFC-001`, `ADR-021`, `RUNNER_MONITOR.md` no
   existen en ninguna ruta. ¿Se eliminan del array (DP-4 sugiere que sí) o hay
   intención de reescribirlos?

4. **`README.md` — ¿reparar o reemplazar?** Describe un producto distinto al
   actual (bot con desktop PySide6, harness, arranque automático). 16 claims
   verificados están rotos. ¿El SDD lo reescribe desde cero o solo corrige rutas?
   Atención a DP-6: alinear el README al código sin leer la bitácora reactivaría
   el auto-arranque eliminado por decisión del trader.

5. **`harness/` — carpeta fantasma.** Solo queda `harness/README.md`, cargado como
   instrucción en `opencode.json:26`. ¿Se borra la carpeta y la entrada, o el
   harness volverá?

6. **Artefacto primario de la auditoría POI.** `docs/ict/SPEC_TESIS_FORMAL.md:285`
   cita `tests/AUDITORIA_POI_REPORT`, que no se localizó. ¿Existe fuera del repo?
   Sin él, `PF 0.900 vs 1.511` es un número heredado sin reproducibilidad, aunque
   la decisión derivada sea contractualmente vinculante.

7. **Protección de `require_pd=False`.** ¿El SDD debe añadir un test de regresión
   que falle si `engine/sequence.py` deja de pasar `require_pd=False` explícito?
   Hoy el default de `engine/plan.py:371` es `True` y nada impide el revert
   accidental.

8. **`ict_backtest/plan_attach.py:100`.** Import roto a un módulo borrado en
   código de producción. ¿Se repunta a `engine.poi_anchor`, o `plan_attach.py`
   entero se retira por la Ley (el backtest no debe tener lógica de decisión)?

9. **`docs/auditorias/` y `docs/avances/` sin marcadores.** 21 documentos sin
   señal de vigencia, varios describiendo un motor superado. ¿El SDD les añade
   cabecera de estado, o se mueven a `_historico/`?

10. **Autoridad de `docs/METRICS_CANON.md`.** Se declara única fuente de números
    pero mide el backtest de julio 2026, no el motor actual. ¿Se le añade un
    caveat de alcance, o se congela como histórico hasta que haya corrida nueva
    del motor?

11. **`PUNTO_DEL_ROADMAP_2026-08-05.md` mal ubicado.** Es el mapa vivo
    (`:58-60`) pero vive dentro de `_roadmap_historico/`. ¿Se promueve a
    `docs/planificacion/`?

12. **Congelamiento del baseline.** ¿Rubén autoriza el `git stash push -u` (o un
    commit WIP en rama de respaldo) antes de que el SDD empiece? Sin eso,
    `engine/poi_anchor.py` sigue a un comando de distancia de desaparecer.
