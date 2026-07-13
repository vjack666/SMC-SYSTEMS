# Índice Maestro de Documentación — SMC-SYSTEMS

Mapa de todos los documentos del proyecto. Reorganizado el 2026-07-11: los docs
sueltos de `docs/` y los reportes de proyecto sueltos en la raíz se clasificaron
en carpetas temáticas dentro de `docs/`.

> Regla: los archivos de la RAÍZ del repo (AGENTS.md, README.md) y los README de
> código/paquetes NO se mueven (afectarían imports/refs). Se listan abajo como
> "externos" y deben mantenerse actualizados en paralelo.

## Carpeta `docs/` (reorganizada)

### `arquitectura/` — cómo está hecho el sistema
- `AGENT_ARCHITECTURE.md` — arquitectura multi-agente (ICT/Wyckoff/Structure/Decision).
- `ARCHITECTURE_MAP.md` — mapa de grafo del código.
- `DEPLOYMENT_GUIDE.md` — guía de despliegue.
- `DOCUMENTATION_INDEX.md` — índice original de documentación.

### `reglas/` — especificaciones operativas (rulebooks)
- `ICT_RULEBOOK.md` — reglas ICT que sigue el ICT Agent.
- `WYCKOFF_RULEBOOK.md` — reglas Wyckoff que sigue el Wyckoff Agent.

### `plan/` — visión, requisitos y hoja de ruta
- `VISION.md` — propósito/dirección a largo plazo.
- `PRD.md` — Product Requirements Document.
- `SRS.md` — Software Requirements Specification.
- `SAD.md` — Software Architecture Document.
- `CRONOGRAMA_Y_ROADMAP.md` — cronograma y roadmap (hitos A6/A12).
- `ROADMAP_BIBLIOTECA_Y_APLICACION.md` — **roadmap 10/10 docs → código** (PO3, KZ, modelos).
- `ADR-021_filosofia_documentacion_ict.md` — estándar Teoría→…→Resultados.
- `HOJA_DE_RUTA_SMC-SYSTEMS.md` — hoja de ruta del sistema (histórica).
- `STRATEGY_IMPROVEMENT_PLAN.md` — plan de mejora de estrategia.

### Métricas canónicas (raíz de `docs/`)
- `METRICS_CANON.md` — **única fuente** de PF/WR/gates; los libros enlazan aquí.

### `prompts/` — prompts del sistema
- `PROMPTS.md` — prompts de agentes/sistema.

### `avances/` — reportes de progreso
- `AVANCES_ICT_BACKTEST_2026-07-10.md` — avances backtest (Capa 2/3).
- `AVANCES_ICT_BACKTEST_2026-07-11.md` — avances + auditoría + veredicto.
- `EDGE_DIAGNOSIS_REPORT.md` — diagnóstico de edge del stack.
- `ESTADO_ACTUAL.md` — estado actual del proyecto.

### `auditorias/` — auditorías y reportes de integración
- `AUDIT_REPORT.md` — reporte de auditoría del proyecto.
- `AUDITORIA_USO_2026-07-09.md` — auditoría de uso.
- `DIAGNOSTICO_EJECUCION_2026-07-09.md` — diagnóstico de ejecución.
- `COMPLETION_REPORT.md` — reporte de completitud.
- `MT5_INTEGRATION_REPORT.md` — reporte de integración MT5.
- `TASK3_PANDAS_VERIFICATION.md` — verificación pandas.

### `rutinas/` — rutinas específicas
- `RUTINA_EURUSD.md` — rutina EURUSD.

### `analisis/` — contexto de mercado
- `TREND_CONTEXT.md` — contexto de tendencia.

## Carpetas temáticas
- `ict/` — biblioteca ICT **v2 10/10** (libros 01–11 + plantilla). Ver `ict/00_INDICE.md`.
- `wyckoff/` — biblioteca Wyckoff v2 (índices + cruce ICT). Ver `wyckoff/00_indice.md`.
- `diario/` — registro diario.
- `specs/` — especificaciones técnicas.
- `proposals/` — propuestas.
- `images/` — assets de imágenes.

## Documentos EXTERNOS (en raíz / fuera de docs/) — NO mover, mantener actualizados
- `AGENTS.md` (raíz) — instrucciones del agente autónomo. Lo lee Hermes cada sesión.
- `README.md` (raíz) — descripción general del proyecto.
- `README.md` en código/paquetes (NO mover): `integration/mt5_bridge/`, `orchestration/`,
  `MQL5/SMC_SYSTEMS_BRIDGE/`, `legacy/*`, `dist/`, `.pytest_cache/`, `.atl/`,
  `smc_successor.egg-info/`, `results/` (outputs de edge_diagnosis).

## Outputs generados (no fuente, referenciar solo)
- `graphify-out/GRAPH_REPORT.md` — reporte del grafo (se regenera).
- `results/edge_diagnosis/` — CSV/JSON de diagnóstico de edge (outputs).
