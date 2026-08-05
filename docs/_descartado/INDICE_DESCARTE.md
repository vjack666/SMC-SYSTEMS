# Índice de Descarte — docs/_descartado/

Estos MD se movieron aquí porque **no sirven a un trader humano ni ayudan a la
tesis** en el estado actual del proyecto (2026-08-05). Son reversibles: están
en git, se pueden restaurar con `git mv` de vuelta. NO se borraron físicamente.

## Criterio aplicado (decisión del trader humano)
- El motor (engine/) es permanente; el backtest es desechable y demuestra la
  tesis. La documentación debe reflejar eso y ayudar al humano a operar/leer el
  gráfico, no describir proyectos bot heredados ni roadmaps ya purgados.

## Motivo por archivo

### Raíz / auditorías de "SMC_SUCCESSOR" (proyecto bot no cableado al flujo actual)
- `COMPLETION_REPORT.md` — habla de "SMC_SUCCESSOR", Phase 1 Pipeline Wiring,
  AgentOrchestrator, build_scalping_context. Ese proyecto NO está cableado al
  observador FundedNext de hoy. Engaña sobre el estado real.
- `auditorias/COMPLETION_REPORT.md` — ídem (duplicado en docs/auditorias).

### Auditorías que cruzan roadmaps YA PURGADOS (AGENTS.md: docs/plan/ purgado 2026-08-03)
- `auditorias/ROADMAP_FASES_R4_IA.md` — cruza CRONOGRAMA_Y_ROADMAP / IMPLEMENTATION_PLAN / ETAPA_4_BUGS / DECISION_LOG, todos purgados. Basura.
- `auditorias/R4_CIERRE_FUNDING_2026-07-17.md` — ídem, depende de esos roadmaps.
- `auditorias/AUDITORIA_CRUZADA_ROADMAP_2026-07-17.md` — cruza los roadmaps purgados.
- `auditorias/AUDIT_REPORT.md` (2026-07-03) — viejo, pre-refactor del motor.
- `auditorias/DIAGNOSTICO_EJECUCION_2026-07-09.md` — diagnóstico de demo viejo.
- `auditorias/AUDITORIA_USO_2026-07-09.md` — auditoría de uso vieja (pre-refactor).

### Datos/cuentas desactualizados
- `auditorias/MT5_INTEGRATION_REPORT.md` — dice "ForexClub MT5 — Account
  500236073". La cuenta correcta es **FundedNext** (ForexClub descartado). Engaña.

### Arquitectura de "producción bot" no aplicable al observador actual
- `arquitectura/DEPLOYMENT_GUIDE.md` (F8) — "production trading deployment",
  reference-only, no aplica al observador 24/7 sin bot.
- `arquitectura/AGENT_ARCHITECTURE.md` — capa de agentes del bot SMC_SUCCESSOR.
- `arquitectura/DOCUMENTATION_INDEX.md` — flujo VISION→PRD→SRS→SAD del bot
  heredado; no es el flujo actual (AGENTS.md + tesis + engine/).

### Propuestas de cambios MEDIBLES para backtest ML (no del observador humano)
- `proposals/item_B.md` .. `item_F.md` — borradores de walk-forward OOS /
  PurgedKFold / conflicto ICT-Wyckoff del proyecto bot. No ayudan al trader
  humano de hoy (observador FundedNext). Se conservan por si se reactiva el bot.

## NO se tocó (fuente de verdad)
- `docs/tesis/` — tesis del trader humano (intacta por orden expresa).
- `docs/ict/20_TESIS_ICT.md`, `docs/ict/SPEC_TESIS_FORMAL.md`, `docs/ict/21_POI.md` — tesis.
- `docs/planificacion/` — planes de trabajo VIGENTES (sesgo vela-a-vela).
- `docs/auditorias/AUDITORIA_FIDELIDAD_TESIS_ICT_2026-07-17.md` — vigente.
- `docs/ict/10_AUDITORIA_REFACCION/` — libro de lecciones vigente.
