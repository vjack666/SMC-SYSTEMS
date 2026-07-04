# CRONOGRAMA Y ROADMAP - SMC-SYSTEMS

**Proyecto:** SMC-SYSTEMS (renombrado desde SMC_SUCCESSOR)  
**Repositorio:** https://github.com/vjack666/SMC-SYSTEMS  
**Versión del Roadmap:** 2.0 (post-limpieza y auditoría)  
**Fecha de Actualización:** 2026-07-04  
**Estado General:** 🟡 Alineación en progreso (Fase 1 completada, gaps críticos identificados en auditoría)

---

## 1. Principios Rectores (NO NEGOCIABLES)

1. **El Roadmap es la única fuente de verdad.** Todo avance se mide exclusivamente por hitos/objetivos cumplidos (no por tiempo ni por "casi listo").
2. **Harness-First Development.** Todo nuevo módulo, feature o refactor **debe** integrarse a través del `harness/` y pasar el 100% de los escenarios definidos antes de considerarse completo. No hay excepciones.
3. **Limpieza y Enfoque.** Después de la limpieza masiva realizada por el usuario, solo se mantiene lo esencial. Nada de contenido legacy o disperso.
4. **Documentación Dual.** Todos los documentos MD deben ser consumibles tanto por humanos (explicaciones simples) como por agentes IA (estructura clara, secciones bien definidas, listas accionables).
5. **Cierre de Ciclo con Informe Semanal.** Cada vez que se completa un hito importante o se cierra un ciclo de trabajo, se genera el Informe Semanal usando la skill correspondiente.

---

## 2. Estado Actual del Repositorio (Post-Limpieza)

### Estructura Confirmada (limpia y modular)
- **Entry points:** `scripts/run_desktop.py`, `scripts/run_paper_trading.py`, `scripts/run_live_trading.py` (ya no existe `run_system.py`)
- **Harness:** Carpeta `harness/` presente y declarada como gate de calidad.
- **Documentación:** Carpeta `docs/` con `DESKTOP_UI.md`, `DEPLOYMENT_GUIDE.md` (incompleto), `AGENT_ARCHITECTURE.md`, `ICT_RULEBOOK.md`, `WYCKOFF_RULEBOOK.md`.
- **Componentes clave implementados:** `agents/`, `risk/`, `signals/`, `detectors/`, `ml/`, `governance/`, `orchestration/`, `desktop/`, `MQL5/SMC_SYSTEMS_BRIDGE/`.
- **Reportes existentes:** `COMPLETION_REPORT.md`, `AUDIT_REPORT.md`, `MT5_INTEGRATION_REPORT.md`.

### Progreso Real vs Roadmap Anterior (Comparación)
| Aspecto | Expectativa Anterior (memoria F14 + Harness Phase 1) | Estado Actual (post-limpieza) | Semáforo |
|---------|-------------------------------------------------------|--------------------------------|----------|
| Fase 1 / Harness baseline | 5% progreso general | Completada + muchos F avanzados | 🟢 |
| F5 - MT5 Bridge | Prioridad Julio 2026 | Presente + reportes de integración | 🟢 |
| F6 - MQL5 EA | Prioridad Julio 2026 | Presente en `MQL5/SMC_SYSTEMS_BRIDGE` | 🟢 |
| F8 - Deployment Guide | No iniciado | Faltante (gap crítico) | 🔴 |
| F10 - Stochastic Exhaustion | No implementado | Aún no implementado (gap Wyckoff) | 🔴 |
| Documentación | Actualizada | Desactualizada (README stale, paths incorrectos, harness adapters discrepancy 10 vs 4) | 🟡 |
| Tests / Harness scenarios | Harness como gate | 6 módulos sin tests, backtest sin escenarios completos | 🟡 |
| Backtest métricas | — | PF 1.61, WR 63.74%, Sharpe 3.33 (buenos) pero solo 91 trades (bajo vs objetivo ≥200) | 🟡 |
| Out-of-sample validation | Suficiente | Insuficiente (solo 2 años de datos) | 🟡 |

**Conclusión de la comparación:** El proyecto avanzó significativamente en implementación (F4-F7, F9-F16 parciales completados), pero el **Roadmap y la documentación no se actualizaron**. La auditoría revela que el repo está "sucio" por refactor incompleto y que el harness no está fully alineado. Esta versión 2.0 del Roadmap corrige eso.

---

## 3. Hitos y Objetivos Actuales (Actualizado Post-Limpieza)

### Hito Actual: **Funcionalidad Completa + Validación** (Julio 2026)

Todo debe estar funcional antes de pensar en deployment. F8 (Deployment Guide) se mueve al final.

| ID | Objetivo | Descripción | Estado | Prioridad |
|----|----------|-------------|--------|-----------|
| A1 | Actualizar documentación stale | Corregir README.md, AGENT_ARCHITECTURE.md, harness/adapters docs, paths y descripciones. | 🟡 En progreso | Alta |
| A4 | Stochastic Exhaustion (F10) | Detección de divergencias estocásticas + volumen + patrones Wyckoff. Integrar al pipeline de signals. | 🔴 Pendiente | Alta |
| A2 | Parameter Tuning (F12) | Integrar Optuna para tuning de hyperparams del ML. Reemplazar valores hardcodeados por búsqueda sistemática. | 🔴 Pendiente | Alta |
| A7 | Validación cuantitativa (F9/F13) | PurgedKFold, CVaR, DSR, PBO, bootstrap confidence intervals. Integrar en `ml/` con scenarios harness. | 🔴 Pendiente | Alta |
| A5 | Tests + cobertura | Tests para 6 módulos sin cobertura. Escenarios harness para backtest. | 🔴 Pendiente | Alta |
| A3 | Resolver discrepancia Harness | Alinear 10 adapters reales vs 4 documentados. Escenarios faltantes. | 🔴 Pendiente | Media |
| A6 | Expandir datos | Incrementar dataset histórico (>3-4 años) para out-of-sample robusto. | 🟡 Pendiente | Media |
| A8 | Deployment Guide (F8) | VPS, systemd, recovery, monitoring. **Se hace AL FINAL**, cuando todo lo demás funcione. | 🔴 Pendiente | Baja |

**Criterio de completitud:** Todos los items A1-A8 en 🟢. El harness pasa 100% de escenarios. Solo entonces se considera production-ready.

---

## 4. Fases Futuras (una vez cerrado el Hito Actual)

- **Fase Live Trading & Robustez:** Validación full en paper trading con harness, kill-switch testing, drift detection en producción, ML retraining scheduler.
- **Fase Deployment (F8):** ÚLTIMA. Solo cuando todo esté funcional y validado.
- **Fase Expansión:** Soporte multi-símbolo/timeframe más amplio, UI enhancements, gobernanza de modelos.

---

## 5. Métricas de Éxito del Proyecto (Gate de Calidad)

- Profit Factor ≥ 1.25 (actual 1.61 ✅)
- Win Rate ≥ 52% (actual 63.74% ✅)
- Max Drawdown ≤ 10% (actual 4.96% ✅)
- Sharpe > 1.0 (actual 3.33 ✅)
- Expectancy > 0 (actual 0.1145R ✅)
- **Trade count por backtest ≥ 200** (actual 91 ⚠️ — debe mejorarse con menos filtros estrictos o más datos)
- Harness: 100% escenarios passing antes de cualquier merge.

---

## 6. Próximos Pasos Inmediatos

1. Usuario revisa y aprueba este `CRONOGRAMA_Y_ROADMAP.md` (versión 2.0).
2. Arrancar con A1 (docs stale) para despejar confusión, luego A4 (Stochastic).
3. F8 (Deployment) queda AL ÚLTIMO — no se toca hasta que todo lo demás esté funcional.
4. Cualquier nuevo desarrollo debe pasar primero por el harness actualizado.

---

**Este documento reemplaza cualquier versión anterior de CRONOGRAMA_Y_ROADMAP.md. Es la única fuente de verdad a partir de ahora.**

*Generado automáticamente por Grok tras revisión del estado actual del repo post-limpieza y rename. Alineado con COMPLETION_REPORT.md y AUDIT_REPORT.md existentes.*