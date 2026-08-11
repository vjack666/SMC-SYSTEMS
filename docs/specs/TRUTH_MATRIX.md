# TRUTH_MATRIX.md — Matriz de Fuentes de Verdad (SMC-SYSTEMS)

> Fuente de autoridad para determinar qué documento manda sobre qué. Generada por la
> Misión 1 (2026-08-11) contra el árbol REAL en HEAD `1b322b0`. Si aparece una referencia
> muerta en el futuro, `scripts/check_truth_sources.py` la detecta.
> Clasificación: CURRENT / HISTORICAL / OBSOLETE / DISCARDED / EXTERNAL / UNKNOWN.

## 1. Fuentes CURRENT (autoridad vigente)

| Fuente | Existe | Autoridad | Estado | Referenciada por | Vigente |
|--------|:------:|-----------|--------|------------------|:------:|
| `AGENTS.md` (raíz) | ✓ | Constitución operativa | CURRENT | todo agente | ✓ |
| `README.md` (raíz) | ✓ | Estado del repo | CURRENT | todo agente | ✓ |
| `docs/ict/SPEC_TESIS_FORMAL.md` | ✓ | Tesis formal firmada | CURRENT | AGENTS, SDD | ✓ |
| `docs/DECISION_BACKTEST_UNICO.md` | ✓ | Arquitectura backtest | CURRENT | AGENTS | ✓ |
| `engine/` | ✓ | Única fuente de decisión | CURRENT | AGENTS, tesis | ✓ |
| `ict_backtest/` | ✓ | Consumidor puro motor | CURRENT | AGENTS | ✓ |
| `docs/specs/SDD_GOVERNANCE.md` | ✓ | Proceso SDD | CURRENT | AGENTS §16, PROTOCOLO | ✓ |
| `docs/specs/INDICE_MDS.md` | ✓ | Índice componentes | CURRENT | AGENTS, CONTRATO_ORDEN | ✓ |
| `docs/tesis/SDD_*.md` | ✓ | Specs diseño estrategia | CURRENT | AGENTS §16 | ✓ |
| `docs/architecture/RESEARCH_CONTRACT.md` | ✓ | Contrato investigación | CURRENT | openspec.json | ✓ |
| `docs/architecture/DIRECTORY_CONTRACT.md` | ✓ | Contrato de carpetas | CURRENT | openspec.json | ✓ |
| `docs/architecture/{ARCHITECTURE,DEPENDENCY_RULES}.md` | ✓ | Arquitectura motor | CURRENT | — | ✓ |
| `agents/governance/ROLES_GOBERNANZA.md` | ✓ | Roles gobernanza | CURRENT | AGENTS, openspec.json | ✓ |
| `agents/governance/{ORQUESTADOR,PROTOCOLO_AGENTE,CONTRATO_ORDEN}.md` | ✓ | Procedimiento agentes | CURRENT | AGENTS | ✓ |
| `docs/ict/00_INDICE.md` + libros 01–21 | ✓ | Biblioteca ICT | CURRENT | tesis | ✓ |
| `docs/specs/app_observador.md` | ✓ | SDD observador | CURRENT | README | ✓ |

## 2. Fuentes HISTORICAL (conservadas, fuera de autoridad activa)

| Fuente | Existe | Estado | Por qué |
|--------|:------:|--------|---------|
| `docs/planificacion/_roadmap_historico/*` | ✓ | HISTORICAL | Roadmaps purgados de `docs/plan/` (2026-08-03); marcados HISTÓRICO en cada archivo |
| `docs/METRICS_CANON.md` | ✓ | HISTÓRICO | Números R6 julio 2026, previos al motor `engine/` actual |
| `openspec/` | ✓ | HISTÓRICAL | Línea base forense SDD-00 (2026-08-07, baseline 9842394); congelada |
| `docs/architecture/REVISION_2.2_REPORT.md`, `MICRO_AUDIT_*` | ✓ | HISTÓRICAL | Auditorías previas |
| Bot "SMC_SUCCESSOR" (`ml/`, `paper_trading/`, `signals/`, `integration/`, `MQL5/`, `risk/`, `features/`, `monitoring/`, `governance/`, `detectors/`, `bin/smc_trading.spec`) | ✓ | HISTÓRICO | Descrito en README (secciones marcadas HISTÓRICAS); no cableado al flujo diario ni a la Ley Fundamental |

## 3. Fuentes OBSOLETE / eliminadas (NO reusar)

| Fuente | Existe | Estado | Nota |
|--------|:------:|--------|------|
| `COMPLETION_REPORT.md` (raíz) | ✗ | OBSOLETE | Borrado; copias en `docs/_descartado/` |
| `docs/plan/` (entero) | ✗ | OBSOLETE | Purgado intencionalmente; refs en AGENTS/README/opencode.json eliminadas en Misión 1 |
| `docs/CRONOGRAMA_Y_ROADMAP.md` | ✗ | OBSOLETE | Nunca existió en esta ubicación; README lo citaba mal |
| `docs/HOJA_DE_RUTA_SMC-SYSTEMS.md` | ✗ | OBSOLETE | Idem |
| `harness/` (framework) | ✗ | OBSOLETE | Solo `harness/README.md`; `python -m harness` falla |
| `docs/tesis/TRUTH_SOURCES.md` | ✗ | OBSOLETE | Eliminado en reset; rol absorbido por cadena de autoridad |
| `docs/tesis/SPEC_TESIS_FORMAL.md` | ✗ | OBSOLETE ruta | Ruta real es `docs/ict/SPEC_TESIS_FORMAL.md` |
| `scripts/r6_ablation.py` | ✗ | OBSOLETE ruta | Real: `scripts/_legacy/r6_ablation.py` |
| `docs/plan/RUNNER_MONITOR.md` | ✗ | OBSOLETE | Detalle de runner vive en `AGENTS.md` (sección Runner Monitor) |

## 4. Fuentes DESCARTED

| Fuente | Existe | Estado |
|--------|:------:|--------|
| `docs/_descartado/` (roadmaps, arquitectura, auditorias, proposals) | ✓ | DISCARDED |
| `docs/_archivo/`, `docs/analisis/`, `docs/avances/`, `docs/auditorias/` (sin marcador vigencia) | ✓ | DISCARDED / sin marcador — revisar antes de citar |

## 5. Contaminación entre proyectos (QUOTEX / binarias / OTC)

SMC-SYSTEMS es exclusivamente **Forex + ICT/SMC**. Hallazgos de Misión 1:

| Referencia | Ubicación | Decisión |
|-----------|-----------|----------|
| "QUOTEX" en `docs/architecture/project-context.md` | openspec, HISTÓRICO | Conservar marcado HISTÓRICAL; no autoridad |
| "QUOTEX" en `openspec/README.md` (origen del CONTRATO_ORDEN) | HISTÓRICO | Conservar; nota de congelación añadida |
| "QUOTEX" en `openspec/changes/sdd-00-truth-authority/evidence-docs.md` | HISTÓRICO | Conservar; evidencia forense |
| "QUOTEX" en `docs/_descartado/roadmaps_historico/PROJECT_PROTOCOL.md` | DESCARTADO | Conservar; fuera de autoridad |
| "QUOTEX"/"binarias"/"OTC" en `docs/motor/PROMPT_MAESTRO_MOTOR_SECUENCIAS.md` | línea ~80 (backtest de secuencias, agnóstico de teoría) | Documento de referencia de backtest; NO define la tesis del proyecto. Marcado como contexto de backtest, no instrucción de producto |

**Conclusión de contaminación:** no hay referencias ACTIVAS a QUOTEX/binarias/OTC en la cadena de
autoridad CURRENT (`AGENTS.md`, `README.md`, tesis `docs/ict/SPEC_TESIS_FORMAL.md`, `engine/`,
`SDD_GOVERNANCE.md`, `docs/tesis/SDD_*.md`). Las referencias restantes están confinadas a
documentación HISTÓRICA/DESCARTADA y a un prompt de backtest agnóstico. **ACTIVE CROSS-PROJECT
REFERENCES = 0.** El motor `engine/` no usa indicadores ni lógica de binarias.

## 6. Regla de precedencia (cuando dos documentos discrepan)

`AGENTS.md` → `docs/ict/SPEC_TESIS_FORMAL.md` → `docs/DECISION_BACKTEST_UNICO.md` → `engine/` →
`docs/specs/SDD_GOVERNANCE.md` → `docs/tesis/SDD_*.md` → `docs/specs/INDICE_MDS.md`.

Un documento marcado HISTÓRICO / OBSOLETE / DISCARDED **nunca** prevalece sobre un CURRENT.
