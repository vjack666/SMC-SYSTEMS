# Cronograma de Trabajo — SMC SYSTEMS

> **Este documento centraliza Roadmap + Cronograma + Protocolo de Operación.**
> Debe mantenerse sincronizado con los cambios en el repositorio y las instrucciones de operación.
> Cualquier modificación se registra aquí y se justifica en el siguiente Informe Semanal.

---

## 1. Protocolo de Operación

| Situación                    | Qué hace Ruben          | Qué responde Grok/opencode                     |
|-----------------------------|-------------------------|-----------------------------------------------|
| Nuevo día / nuevo ciclo     | Escribe `start`         | Revisión del repo + prompt(s) para opencode   |
| opencode terminó            | Escribe `ya esta listo` | Inspecciona repo + análisis + siguiente prompt o confirmación |
| Quiere avanzar              | Da orden de alto nivel  | Prompt alineado con Roadmap                   |

**Reglas:**
- Toda tarea completada se commitea antes de pasar a la siguiente.
- El cronograma se actualiza cuando cambia el roadmap o se completa una fase.
- El Informe Semanal resume el progreso y justifica cambios.

---

## 2. Roadmap Consolidado

### Leyenda
| Símbolo | Significado |
|---------|-------------|
| ✅ | Completada |
| 🔄 | En progreso |
| ⬜ | Pendiente |
| ⏸️ | En pausa/bloqueada |

### FASES de Integración MT5

| Fase | Objetivo | Esfuerzo | Dependencias | Estado |
|------|----------|----------|--------------|--------|
| **FASE 1** | Project Audit — inventario completo de activos | – | – | ✅ |
| **FASE 2** | Research — métodos de comunicación MT5 | – | F1 | ✅ |
| **FASE 3** | Target Architecture — diseño end-to-end | – | F2 | ✅ |
| **FASE 4** | Data Contracts — esquemas señal/resultado | – | F3 | ✅ |
| **FASE 5** | Bridge Module — `integration/mt5_bridge/` (orchestrator, exporter, receiver, schema, config) | 2-3 d | F4 | 🔄 |
| **FASE 6** | MQL5 EA — `SMC_SYSTEMS_BRIDGE.mq5` (señal, orden, monitoreo, salidas, resultado) | 2-3 d | F5 | ⬜ |
| **FASE 7** | Backtest Validation — 14,344 trades vs Python | 1-2 d | F5+F6 | ⬜ |
| **FASE 8** | Deployment Guide — semana x semana, go-live, troubleshooting | 1 d | F7 | ⬜ |

### FASES de Validación Cuantitativa (Quant Audit)

| Fase | Objetivo | Esfuerzo | Dependencias | Estado |
|------|----------|----------|--------------|--------|
| **FASE 9** | Robustez Experimento E (8 tests) | – | – | ✅ |
| **FASE 10** | Wyckoff + Stochastic Exhaustion | – | – | ✅ |
| **FASE 11** | ML Expansion + Confluence Scoring | – | F10 | ✅ |
| **FASE 12** | Parameter Tuning + Documentación | – | F11 | ✅ |
| **FASE 13** | Validación Robusta (Purged KFold, bootstrap, CVaR, Drawdown Duration, rolling metrics, DSR, PBO) | 4-6 sem | F12 | ✅ |
| **FASE 14** | Feature Enrichment (liquidity sweeps, inducements, displacement, premium/discount arrays, regime labels, interaction features) | 4-6 sem | F13 | ✅ |
| **FASE 15** | Production Monitoring (drift detection, alerts, equity telemetry, governance dashboards) | 3-5 sem | F14 | ⬜ |
| **FASE 16** | Governance & Automation (auto-retraining, model selection, reports, deployment) | 4-6 sem | F15 | ⬜ |

---

## 3. Dependencias entre streams

```
MT5 Integration Stream              Quant Audit Stream
══════════════════════               ══════════════════
F1 (Audit) ✅                        F9 (Robustez E) ✅
F2 (Research) ✅                     F10 (Wyckoff) ✅
F3 (Architecture) ✅                 F11 (ML Expansion) ✅
F4 (Data Contracts) ✅               F12 (Parameter Tuning) ✅
    ↓                                     ↓
F5 (Bridge) 🔄 ──→ ←── F13 (Robust Validation) ✅
    ↓                                     ↓
F6 (MQL5 EA) ⬜                       F14 (Features) ✅
    ↓                                     ↓
F7 (Backtest Val) ⬜                  F15 (Monitoring) ⬜
    ↓                                     ↓
F8 (Deployment) ⬜                    F16 (Governance) ⬜
```

**Nota:** Ambos streams son mayormente independientes. F5-F8 requieren F4; F14-F16 requieren F13.
No hay dependencia cruzada fuerte entre MT5 y Quant Audit, pero F15 (monitoreo) se beneficia de F5 (bridge).

---

## 4. Timeline Estimado

| Período | Fases | Prioridad |
|---------|-------|-----------|
| **Julio 2026** (Sem 1-2) | F14 — Feature Enrichment ✅ | Alta |
| **Julio 2026** (Sem 2-3) | F5 — Bridge Module 🔄 | Alta |
| **Julio-Agosto 2026** (Sem 3-4) | F6 — MQL5 EA | Alta |
| **Agosto 2026** (Sem 4-5) | F7 — Backtest Validation | Alta |
| **Agosto 2026** (Sem 5-6) | F15 — Production Monitoring | Alta |
| **Agosto-Sept 2026** (Sem 6-8) | F16 — Governance & Automation | Media |
| **Sept 2026** (Sem 8) | F8 — Deployment Guide | Media |

---

## 5. Historial de Sesiones

| Sesión | Fecha | Fases tocadas | Archivo |
|--------|-------|---------------|---------|
| ses_0ef2 | 28-29/Jun/2026 | ML Dataset v4, multi-symbol, SMC_SUCCESSOR | `session-ses_0ef2.md` |
| — | 29/Jun/2026 | F13 validación robusta, cronograma | Actual |
| — | 02/Jul/2026 | F14 scaffolding — adapter + fixture + scenario feature_enrichment | Actual |
| — | 02/Jul/2026 | F14 liquidity sweeps + inducements (real logic), fixed inducement oversensitivity | Actual |
| — | 02/Jul/2026 | F14 wired displacement, zones, regime, sweep_x_inducement interaction — all 6 groups active | Actual |
| — | 02/Jul/2026 | F5 scaffolding — mt5_bridge/ (schema, config, exporter, receiver, orchestrator, harness adapter, README) | Actual |

**Nota:** Las sesiones se registran como archivos `session-{id}.md` en la raíz del proyecto.

---

## 6. Instrucciones de Operación del Proyecto

### Commit Convention
```
feat:     Nueva funcionalidad (FASE N)
fix:      Corrección de bug
chore:    Mantenimiento, gitignore, config
docs:     Documentación
refactor: Refactor sin cambio funcional
test:     Tests
```

### Estructura de reportes
- `docs/reports/informe-semanal-{YYYY-MM-DD}.md` — Reporte semanal
- `docs/reports/sesion-{YYYY-MM-DD}.md` — Notas de sesión

### Archivos maestros
| Archivo | Propósito |
|---------|-----------|
| `PROJECT_OVERVIEW.md` | Visión general del sistema |
| `docs/CRONOGRAMA_Y_ROADMAP.md` | **Este archivo** — plan, roadmap, protocolo |
| `results/quant_audit/roadmap.csv` | Roadmap de validación cuantitativa |
| `results/quant_audit/quant_audit.md` | Auditoría cuantitativa detallada |
| `results/mt5_integration/00_INDEX_AND_SUMMARY.md` | Plan de integración MT5 |
