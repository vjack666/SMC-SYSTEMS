# Documentation Index — SMC-SYSTEMS

Índice maestro de la documentación del proyecto, ordenado por el flujo de
ingeniería estándar (VISION → PRD → SRS → SAD → SDD → TEST PLAN). Todos los
documentos están anclados a la realidad del código (no especificaciones
imaginadas).

> Convención: los libros de la biblioteca ICT son carpetas en `docs/ict/`
> (carpeta = libro, archivos = temas). Los documentos de arquitectura/producto
> viven sueltos en `docs/`.

> **CAPA FUENTE SPEC (2026-07-17, DEC-009e):** la cadena documental ahora arranca
> en SPEC (QUÉ dice la tesis) → ADS (=SAD, CÓMO se organiza) → MDS (=SDD,
> CON QUÉ se implementa) → CÓDIGO. `docs/ict/SPEC_TESIS_FORMAL.md` es el CONTRATO
> FUENTE de la estrategia (Fase 0 del roadmap maestro). No reemplaza la cadena
> VISION→PRD→SRS→SAD→SDD→TEST; la precede como fuente de la estrategia ICT.

## Flujo de documentación

| Orden | Documento | Ruta | Estado | Propósito |
|-------|-----------|------|--------|-----------|
| 1 | **Vision Document** | `docs/VISION.md` | ✅ v1.0 | Propósito, misión, principios rectores, no-objetivos |
| 2 | **PRD** (Product Requirements) | `docs/PRD.md` | ✅ v1.0 | Funcionalidades del producto, alcance, usuarios |
| 3 | **SRS** (Software Requirements Spec) | `docs/SRS.md` | ✅ v1.0 | Requisitos funcionales + no funcionales (NFR) |
| 4 | **SAD** (Software Architecture Doc) | `docs/SAD.md` | ✅ v1.0 | Arquitectura, capas, componentes, flujo de datos |
| 5 | **AGENTS.md** | `AGENTS.md` | ✅ existente | Reglas de operación del agente autónomo |
| 6 | **PROMPTS.md** | `docs/PROMPTS.md` | ✅ v1.0 | Guía de prompts para agentes IA del proyecto |
| 7 | **SDD general ict_backtest** | `docs/ict/SDD_ICT_BACKTEST.md` | ✅ v1.0 | Diseño de módulos de backtest ICT |
| 8 | **SDD refacción auditoría** | `docs/ict/SDD_REFACCION_2026-07-11.md` | ✅ v1.0 | Fixes de auditoría externa (look-ahead, CHOCH, costos, WF) |
| 9 | **API SPEC** | `docs/ict/API_SPEC.md` | ✅ v1.0 | Interfaz pública de `ict_backtest/` |
| 10 | **TEST PLAN** | `docs/ict/TEST_PLAN.md` | ✅ v1.0 | Estrategia de pruebas y cobertura |
| — | **Deployment Guide** | `docs/DEPLOYMENT_GUIDE.md` | ✅ existente | VPS, systemd, NSSM, recovery |
| — | **Cronograma/Roadmap** | `docs/CRONOGRAMA_Y_ROADMAP.md` | ✅ fuente de verdad | Hitos y estado (v2.2) |
| — | **Completion Report** | `COMPLETION_REPORT.md` | ✅ existente | Wiring del pipeline, métricas |
| — | **Biblioteca ICT** | `docs/ict/00_INDICE.md` | ✅ 01–13 | Reglas ICT + backtest profesional (13) |
| — | **Backtest profesional** | `docs/ict/13_BACKTEST_PROFESIONAL/` | ✅ v1.0 docs | Reloj MTF, fill, costos, OOS; plan R6 |
| — | **Plan R6 backtest** | `docs/plan/PLAN_BACKTEST_PROFESIONAL.md` | ⏳ código | Aplicación G1–G3 |
| — | **Libro auditoría** | `docs/ict/10_AUDITORIA_REFACCION/` | ✅ v1.0 | Hallazgos de auditoría externa + fixes |

## Cómo leer esto
- **Nuevo en el proyecto:** lee VISION → PRD → SAD. Tienes el qué, el para qué y el cómo.
- **Queriendo extender `ict_backtest`:** lee SDD_ICT_BACKTEST → API_SPEC → TEST_PLAN.
- **Operando el observador:** README + CRONOGRAMA_Y_ROADMAP + docs/specs/.
- **Auditando calidad:** SRS (NFR) + TEST_PLAN + SDD_REFACCION (lecciones de la auditoría).

## Mantenimiento
Todo documento de este índice se actualiza tras el cambio de código
correspondiente. El agente autónomo (AGENTS.md) versiona y sincroniza con git
tras cada avance. No se documenta una funcionalidad que no esté implementada
(salvo que se marque explícitamente como "pendiente/plan").
