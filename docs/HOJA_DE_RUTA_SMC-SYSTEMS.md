# HOJA DE RUTA - SMC-SYSTEMS (SMC Successor)

**Versión:** 2.0 (Post-Limpieza y Refactor)  
**Fecha:** 04 de julio de 2026  
**Estado:** Canonical - Única fuente de verdad para objetivos y hitos del proyecto.  
**Repo:** https://github.com/vjack666/SMC-SYSTEMS  

---

## 1. Propósito del Proyecto

Sistema de trading automatizado y semi-automático basado en **Smart Money Concepts (SMC)**, **Wyckoff** e **ICT**. 

Arquitectura **modular event-driven** con:
- UI Desktop completa (PySide6, 6 tabs, dark theme, charts con OB/FVG/zones)
- Multi-agentes de análisis (ICT, Wyckoff, Structure → Decision Agent)
- Gobernador de Riesgo con state machine (NORMAL → CAUTION → DEFENSIVE → LOCKDOWN)
- ML para hyperparameter tuning (Optuna) + validación estadística robusta
- Detección de Order Blocks (OB), Fair Value Gaps (FVG) y Stochastic Exhaustion
- Ejecución Paper / Live trading vía MT5 (con bridge y MQL5 EA)
- Harness-first testing framework para garantizar calidad e integración controlada

**Visión:** Sistema production-ready, estadísticamente validado, con trazabilidad completa y deployment reproducible.

---

## 2. Principios Rectores (NO NEGOCIABLES)

1. **Esta Hoja de Ruta es la única fuente de verdad.** Cualquier decisión de alcance o prioridad debe alinearse aquí primero. Si surge idea nueva, se anota en Informe Semanal y se evalúa para inclusion futura. No se desarrolla hasta que corresponda.

2. **Avance medido por hitos cumplidos (no por tiempo).** El Cronograma es solo guía de planificación. El progreso real = % hitos alcanzados con criterios de aceptación cumplidos.

3. **Harness-first Development (100% compliance).** 
   - Todo nuevo módulo, feature o cambio significativo **debe** pasar por el harness/ antes de integrarse al pipeline principal.
   - Requisito: Implementar ModuleAdapter + fixtures + escenarios YAML + assertions que pasen 100%.
   - harness/ (con runners, scenarios, validators, reports) es el motor central de calidad y el gate de integración.

4. **Documentación viva y consistente.** Después de cada hito importante o limpieza, actualizar docs para que reflejen exactamente el código real. Se eliminaron docs obsoletos en la limpieza reciente.

5. **Calidad sobre velocidad.** Umbrales mínimos:
   - Win Rate ≥ 52% (in-sample)
   - Profit Factor ≥ 1.25 (in-sample) / ≥ 1.10 (out-of-sample)
   - Max Drawdown ≤ 10%
   - Validación estadística: CVaR, Deflated Sharpe, PBO, bootstrap CI donde aplique
   - 100% escenarios harness passing para módulos críticos

6. **Enfoque controlado y sin dispersión.** Usar tripartite workflow si aplica (User define objetivo → Grok genera prompt optimizado → opencode implementa → verificación commit). Pequeñas tareas enfocadas.

---

## 3. Estado Actual del Proyecto (Post-Limpieza)

**Estructura:** Flat en root (refactor flatten SMC_SUCCESSOR/ completado). Repo limpio de contenido sobrante y docs obsoletos.

**Componentes clave implementados:**
- `desktop/` : UI PySide6 completa (Dashboard, Chart con EMA/Stoch/OB/FVG, Positions, Trade Log, Log, Control)
- `agents/` : ICT, Wyckoff, Structure, Decision agents
- `harness/` : Framework completo de testing scenario-based (runners, scenarios YAML, assertions, reports, fixtures). Soporta ModuleAdapter pattern.
- `risk/` : Risk Governor state machine
- `paper_trading/` y runners para PAPER/LIVE
- `ml/` : Optuna + validación
- `data/` : MT5 connector + Parquet con staleness thresholds
- `indicators/` + `detectors/` : OB, FVG, EMA, RSI, Stochastic, etc.
- `MQL5/SMC_SYSTEMS_BRIDGE/` : Bridge para MT5
- Múltiples reports de auditoría y completitud actualizados

**Fase 1 (Core Pipeline & UI):** ✅ COMPLETADA (según README y COMPLETION_REPORT)

**Fase 2 (ML + Backtest + Protocolo de entrada):** ✅ COMPLETADA (backtest metrics cumplen la mayoría de umbrales)

**Integración MT5 (F5 Bridge + F6 MQL5 EA):** ✅ COMPLETADA

**Estado general estimado:** ~70-80% hacia sistema production-ready (Fase 1-3 + integraciones clave listas; faltan deployment y pulido quant/stochastic).

---

## 4. Hitos y Fases (Objetivos Medibles)

### Fase 1: Core Pipeline, Desktop UI y Multi-Agente (COMPLETADA ✅)
**Criterios de aceptación cumplidos:**
- UI 6 tabs funcional con rendering de zonas OB/FVG y señales
- Agentes ICT + Wyckoff + Structure generando evidencia estructurada por barra
- Risk Governor operativo
- Data pipeline MT5 → Parquet estable
- Indicadores base operativos
- Paper trading runner headless funcional

### Fase 2: ML, Validación Estadística y Backtesting (COMPLETADA ✅)
**Resultados clave:**
- Backtest multi-símbolo: 91 trades, WR 63.74%, PF 1.612, Sharpe 3.33, DD máx 4.96%
- Protocolo de entrada de 10 pasos definido e implementado
- SL estructural + ATR
- Integración ML quality filter (parcial)

### Fase 3: Integración MT5 Avanzada y MQL5 (COMPLETADA ✅)
- Bridge Module y MQL5 EA/SMC_SYSTEMS_BRIDGE presentes
- Soporte PAPER + LIVE modes con validaciones de margin y kill switch

### Hitos Pendientes (Actualizado Julio 2026)

**Hito 4: Verificar Stochastic Exhaustion (F10) — 🟡 Código listo, falta verificación**
- ✅ Ya implementado en `agents/wyckoff_agent.py:254-311` (detección de divergencias, cruces sobrecompra/sobreventa, confirmación por volumen)
- Pendiente: Scenarios harness específicos + verificar integración con pipeline de signals

**Hito 5: Parameter Tuning (F12) — ✅ Completado**
- ✅ `ml/tuner.py` con Optuna integration (TuningConfig, search spaces, TPE sampler)
- ✅ `WalkForwardConfig.tune_first=True` conectado al pipeline
- ✅ `scripts/run_tuning.py` como CLI
- ✅ 7 tests pasando

**Hito 6: Validación Cuantitativa (F9/F13) — ✅ Completado**
- ✅ PurgedKFold, CVaR, DSR, PBO, bootstrap confidence intervals — todo en `ml/stats_validator.py`
- ✅ 10 tests pasando

**Hito 7: Tests, Harness y Documentación**
- Tests para los 6 módulos sin cobertura (mt5_bridge, mt5_ea, monitoring, governance, orchestration, trend_context)
- Resolver discrepancia harness (10 adapters reales vs 4 documentados)
- Actualizar docs stale (README, AGENT_ARCHITECTURE.md, paths)
- Escenarios harness para backtest

**Hito 8: Validación Live Trading End-to-End con Harness**
- Escenarios harness que cubran path completo live (incluyendo transiciones de Risk Governor, margin checks, kill switch, reconexión)
- Métricas de paper trading extendido cumpliendo umbrales out-of-sample

**Hito 9: Deployment Guide (F8) — AL FINAL**
- **Entregable:** `docs/DEPLOYMENT_GUIDE.md` v1.0 (VPS setup, systemd/NSSM, recovery procedures, monitoring básico, prerequisites exactos)
- **Criterio:** Guía reproducible que permita deploy en < 2 horas en VPS limpio
- **Validación:** Checklist manual + scenarios harness si aplica para deploy scripts
- **Nota:** Se hace SOLO cuando todo lo anterior esté functional.

---

## 5. Reglas de Ejecución y Control de Cambios

- **Antes de cualquier tarea grande o feature nueva:** Preguntar internamente "¿Está dentro del objetivo actual de esta Hoja de Ruta o del hito en progreso?" Si no, documentar en Informe Semanal y posponer.
- **Integración obligatoria:** Todo código nuevo → harness/ primero (100% pass). Nunca saltar el gate.
- **Actualización de Roadmap:** Al completar un hito importante o al final de cada ciclo de limpieza/refactor, actualizar esta Hoja de Ruta + Cronograma.
- **Informe Semanal:** Obligatorio al cerrar cada ciclo/hito importante usando la estructura estandarizada (skill `informe-semanal-estado-proyecto`).
- **Colaboración:** Seguir protocolo tripartite si se usa opencode/Grok para implementación (User → prompt estratégico → implementación → verificación commit por Grok).
- **No dispersión:** Ideas nuevas se registran pero no se ejecutan hasta que el hito actual esté cerrado y priorizado.

---

## 6. Métricas de Éxito Globales

- % Hitos completados (meta: 100% Fase 1-8 para MVP production)
- Cobertura harness: 100% módulos críticos con scenarios passing
- Backtest / Live metrics consistentemente sobre umbrales
- Documentación sync: 100% (código = docs)
- Tiempo de deploy reproducible < 2h

**Próxima revisión de esta Hoja de Ruta:** Al completar Hito 4 (Deployment) o en el próximo Informe Semanal.

---

*Esta versión 2.0 reemplaza cualquier roadmap previo. Fue creada tras revisión exhaustiva del estado actual del repo post-limpieza (julio 2026) y alineada con los reportes de auditoría y completitud existentes.*