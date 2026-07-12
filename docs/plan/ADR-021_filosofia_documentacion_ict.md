# ADR-021 — Filosofía de Documentación ICT

**Status:** Accepted
**Date:** 2026-07-12
**Supersedes:** ninguna
**Relacionado:** RFC-001 (Modernización de la Biblioteca ICT)

## Decisión (Decision)
Todo documento ICT debe contener, en este orden:

1. **Teoría** — definición y reglas operativas del concepto.
2. **Uso práctico** — cómo lo usan los traders reales (entrada, gestión,
   sesiones, multi-TF HTF/LTF).
3. **Algoritmo** — cómo lo detectan las aplicaciones automáticas (MQL5 /
   detectores del proyecto), incluyendo riesgos (look-ahead, Chart Shift,
   profundidad de histórico).
4. **Mapeo a código** — cómo lo implementa SMC-SYSTEMS, con rutas de archivo
   reales (`detectors/`, `ict_backtest/`, `ml/`).
5. **Hallazgos de auditoría** — qué bugs/correcciones afectaron el concepto.
6. **Impacto de rendimiento** — métricas medidas (PF, WR, trades, etc.).

## Razón (Reason)
Evitar la divergencia entre documentación, implementación, backtests y
producción. Con múltiples agentes IA (Hermes, ChatGPT, auditor externo)
trabajando el proyecto, la estructura fija permite que cualquier agente continúe
el trabajo sin depender de un prompt gigante ni de recordar conversaciones
previas. La teoría ICT es estable; lo que cambia es nuestra implementación y los
hallazgos de auditoría, que deben quedar anclados al libro.

## Consecuencias (Consequences)
- Los libros ICT futuros siguen esta filosofía por defecto.
- RFC-001 aplica la filosofía a la biblioteca actual (libros 03-08).
- Los SDD (`docs/plan/SAD.md`, `docs/ict/SDD_*.md`) deben reflejar la misma
  cadena para mantener trazabilidad regla → detector → código → resultado.
- Referencias externas (MQL5, FluxCharts, etc.) solo como respaldo verificable;
  la fuente de verdad es el código y las auditorías del repo.
