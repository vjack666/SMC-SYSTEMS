# Auditoría de conformidad `engine/` frente al SDD vigente

**Fecha:** 2026-08-14 12:14 (-05:00)
**Agente:** Hermes / rol Ingeniero + Cumplimiento Operativo + Auditoría independiente interna
**Estado:** `ESCALATED` para decisiones semánticas/autoridad; correcciones técnicas aplicadas y verificadas dentro del perímetro.

## 1. Alcance y autoridad

Se auditó `engine/`, sus consumidores directos, trazabilidad y pruebas relevantes contra esta precedencia:

1. `AGENTS.md`.
2. `docs/ict/SPEC_TESIS_FORMAL.md`.
3. `docs/DECISION_BACKTEST_UNICO.md`.
4. `engine/`.
5. `docs/specs/SDD_GOVERNANCE.md`.
6. `docs/specs/INDICE_MDS.md` y `docs/specs/MDS_*.md`.
7. `docs/tesis/SDD_*.md`.

No se contó con una herramienta de subagentes delegados callable en esta sesión. Para no fabricar delegaciones, se ejecutaron cuatro pistas independientes: fuentes/gobernanza, dependencias, semántica anti-look-ahead y regresión técnica.

## 2. Registro de operaciones

| Hora aprox. | Operación | Resultado |
|---|---|---|
| 11:24 | `runner_monitor` sobre batería inicial del motor | Proceso terminó con código 1; 8 fallos de consumidores de `run_sequence_traced` esperando 3 valores. |
| 11:25 | `python scripts/check_truth_sources.py` | Fallo de consola cp1252 al imprimir Unicode. |
| 11:26 | Corrección UTF-8 segura en `scripts/check_truth_sources.py`; rerun | 23 fuentes activas, 0 rotas, 0 referencias cross-project; exit 0. |
| 11:29–11:32 | Baterías engine agrupadas | 170 pruebas pasaron; 8 fallos iniciales quedaron aislados en linaje. |
| 11:32 | `tests/test_m2_lineage.py` + `tests/test_phase6_lineage.py` | Tras alinear la tupla vigente de 4 valores: 27 pasaron, 1 skip en la batería combinada con continuidad. |
| 11:34 | Auditoría estática de imports, indicadores y look-ahead | 0 imports `ict_backtest` desde `engine/`; tokens de indicadores encontrados solo en comentarios/alias históricos, no como cálculo técnico. |
| 11:35 | Corrección de `avg_candle_range` | Eliminado `bfill()` futuro; shim del backtest delega al motor; prueba causal nueva. |
| 11:36 | Baterías B2/utilidad | 15 pasaron; `py_compile`/`compileall` limpio en el perímetro modificado. |
| 11:37 | Suite completa `tests/` | No colecciona: 12 errores legacy/broken por imports eliminados y datasets ausentes. |
| 11:39–11:55 | Suite activa amplia | Interrumpida al alcanzar la equivalencia real de replay, que no concluyó tras ~16 min; no se declara pass/fail. |
| 12:00 | Corrección de frontera estructural | `engine/market_structure.py` convertido en shim hacia `engine.bos.structure`; alias `structure_label` conservado solo para compatibilidad. |
| 12:02 | Compatibilidad de consumidores | `app_observador.core.timezone.killzone_en` delega al motor; `run_backtest` acepta dobles que devuelven solo señales. |
| 12:04 | Replay audit battery | 12 pasaron; la prueba de cableado/equivalencia real larga queda pendiente. |
| 12:14 | Verificación final de fuentes y compilación | Fuentes OK; compilación OK; sin commit/push. |

## 3. Hallazgos y acciones

### H1 — Contrato de retorno de linaje desactualizado: corregido

El código vigente devuelve `run_sequence_traced -> (signals, phase_seen, expedientes, state)`, requerido por persistencia/reanudación. Dos suites esperaban la tupla histórica de tres. Se actualizaron consumidores de prueba y las referencias de `RESEARCH_CONTRACT.md`; `run_sequence` público conserva su tupla de dos.

### H2 — `avg_candle_range` tenía fuga en el calentamiento: corregido

`engine/_util.py` hacía `rolling(...).ffill().bfill()`. El `bfill()` podía copiar al inicio un rango calculado con velas futuras. Ahora la media usa únicamente filas observadas hasta `i`, con `min_periods=1`; `ict_backtest/_util.py` es shim hacia `engine._util`. La prueba `tests/test_engine_util.py` demuestra que la primera vela no recibe el rango de una vela futura.

### H3 — Dos ontologías BOS/CHOCH: corregido estructuralmente

El SDD vigente declara `engine.bos.structure` como fuente única, pero varios consumidores importaban el antiguo `engine.market_structure.py`. Ese archivo ahora solo adapta `MarketStructure.frame` a la API DataFrame histórica y añade `structure_label` no decisional. Se actualizó `MDS_BOS_CHOCH.md` para dejar la frontera explícita.

### H4 — Call-sites de ejecución fina: corregido

`run_backtest` asumía que cualquier doble de `generate_sequence_signals` devolvería una tupla, aunque el contrato por defecto permite una lista. Ahora normaliza ambos formatos sin alterar el wrapper canónico. También se restauró el alias observable de killzone del dashboard hacia `engine.killzone`.

### H5 — `engine/order_block.py` y detector reutilizable: pendiente de autoridad

Se detectó una divergencia real: `engine/order_block.py` representa el OB en la vela origen usando confirmación de la siguiente vela, mientras `detectors.ob` usa otra convención causal. Un intento de sustitución automática produjo OBs adicionales y rompió expectativas semánticas del componente. Se revirtió ese intento; no se impuso una regla nueva. Requiere decidir formalmente si el timestamp del OB es origen o confirmación y si ambas convenciones deben unificarse.

### H6 — OTE en ejecución: pendiente de autoridad

`engine/ote.py` y `engine/dealing_range.py` calculan/anotan OTE, pero `fine_execution` entra por swing breakout. `SDD_LTF_ENTRY_LAYER.md` clasifica OTE como Fase 4 opcional; `MDS_D1_OTE.md` ahora documenta el gap. Cablearlo como filtro duro o blando cambiaría la estrategia y no se puede decidir por evidencia técnica solamente.

### H7 — Pruebas heredadas y contrato de equivalencia: pendiente operativo

La colección total incluye `tests/_broken/` y pruebas legacy que exigen módulos eliminados o datos ausentes; no se resucitaron. La equivalencia real de replay excede el tiempo operativo observado y fue detenida de forma controlada. La batería rápida de replay sí pasó 12 pruebas y la batería anterior del fix funcional pasó 14 pruebas.

### H8 — Test de aislamiento de etiquetas: pendiente de contrato

`tests/test_labels_isolation.py` todavía trata `bos_status` como decisión invariante al truncar, aunque el SDD define invalidación/superseded como estado event-driven que puede cambiar con barras posteriores. También detecta la anotación descriptiva ERL→IRL como uso de futuro fuera de `labels.py`. Requiere decidir si el contrato limita futuro solo a decisiones o también a metadatos descriptivos; no se maquilló el test.

### H9 — Documentación de contexto ausente

El protocolo menciona `.hermes.md` y `engineering.md`, pero no existen en el árbol actual. `AGENTS.md` + `SDD_GOVERNANCE.md` contienen reglas suficientes para esta ejecución. Queda escalado decidir si se crean esos documentos o se eliminan sus referencias del protocolo.

## 4. Evidencia de verificación

- `scripts/check_truth_sources.py`: exit 0; `BROKEN ACTIVE REFERENCES=0`, `ACTIVE CROSS-PROJECT REFS=0`.
- Baterías engine agrupadas tras correcciones: `61 + 36 + 37 + 37 = 171 passed`.
- Linaje/continuidad: `27 passed, 1 skipped`.
- B2/utilidad: `15 passed`.
- Replay audit battery: `12 passed`.
- POI/B2/plan-gate tras compatibilidad: las pruebas del grupo pasaron salvo el test legacy de lifecycle ya actualizado en el árbol; no se declara la colección completa como verde.
- `python -m compileall -q engine ict_backtest app_observador/core ...`: exit 0.
- Auditoría de imports: 0 imports activos de `ict_backtest` desde `engine/`.
- Suite completa: 12 errores de colección legacy/broken; no es una prueba válida de conformidad del motor hasta definir el perímetro oficial.

## 5. Estado de conformidad

`engine/` queda en estado técnico **IMPLEMENTED → TESTED → parcialmente SEMANTICALLY_VERIFIED** para el perímetro activo. No se declara `AUDITED` ni `ACCEPTED`: esas transiciones pertenecen al Auditor Independiente y al Director, respectivamente.

## 6. Decisiones que se escalan

1. Aprobar o rechazar el cableado OTE en `fine_execution` y definir si es metadata, filtro blando o gate duro.
2. Fijar la convención única de timestamp/confirmación de Order Block.
3. Declarar el perímetro oficial de pruebas: retirar/marcar legacy y establecer el contrato de equivalencia real de replay con límite operativo.
4. Resolver el contrato semántico de `labels.py` frente a metadatos descriptivos ERL/IRL y estados event-driven.
5. Decidir qué hacer con las referencias a `.hermes.md` y `engineering.md` ausentes.

No se hizo commit ni push.
