# CRONOGRAMA Y ROADMAP - SMC-SYSTEMS

**Proyecto:** SMC-SYSTEMS (renombrado desde SMC_SUCCESSOR)
**Repositorio:** https://github.com/vjack666/SMC-SYSTEMS
**Versión del Roadmap:** 2.2 (post-edge-diagnosis + arranque automático FundedNext)
**Fecha de Actualización:** 2026-07-10
**Estado General:** 🟢 Modo observador FundedNext operativo 24/7 + edge diagnosis completa. Pendiente: walk-forward OOS de celda ganadora, expansión de datos y deployment.

---

## 1. Principios Rectores (NO NEGOCIABLES)

1. **Este Cronograma es la ÚNICA fuente de verdad.** `docs/HOJA_DE_RUTA_SMC-SYSTEMS.md` quedó OBSOLETO (versión 2.0, 04-jul) y redirige aquí. Cualquier decisión de alcance/prioridad se alinea en este documento.
2. **Harness-First Development.** Todo nuevo módulo/feature/refactor debe integrarse vía `harness/` y pasar 100% de escenarios antes de considerarse completo.
3. **Limpieza y Enfoque.** Solo lo esencial versionado. Nada de contenido legacy disperso (ver commit de auditoría de archivos 340597f).
4. **Documentación Dual.** Consumible por humanos y agentes IA (estructura clara, listas accionables).
5. **Cierre de Ciclo con Informe Semanal.** Al completar hito importante, generar informe.

---

## 2. Estado Actual del Repositorio (2026-07-10)

### Modo de operación real
- **OBSERVADOR FUNDEDNEXT (SIN BOT):** el sistema corre como analizador 24/7 para el challenge prop firm FundedNext (cuenta demo MetaQuotes en fase de prueba; la real se toma sola al loguearla). El loop `scripts/loop_analisis.py` (lun-vie 07:00-20:00, finde off) genera ficha + informe + semáforo + alertas locales. **NUNCA abre órdenes.**
- `scripts/vigilante_riesgo.py` SOLO CIERRA posiciones (2%/4% flotante) si operás manualmente.
- Arranque automático vía `start_hermes_session.ps1` (abre MT5 FundedNext, baja datos en vivo, lanza loop + vigilante + observador, reporte de salud). Se invoca desde la Carpeta de Inicio (`.lnk` con Bypass).
- El código de bot heredado (`run_paper_trading.py`, `run_live_trading.py`, MQL5 EA) está implementado pero NO cableado al flujo diario.

### Estructura confirmada
- **Entry points activos:** `app_observador/main.py` (observador), `scripts/loop_analisis.py`, `scripts/rutina_eurusd.py`, `scripts/hermes_startup_routine.py`, `start_hermes_session.ps1`.
- **Componentes:** `agents/`, `risk/`, `signals/`, `detectors/`, `ml/`, `governance/`, `orchestration/`, `app_observador/`, `MQL5/SMC_SYSTEMS_BRIDGE/`, `harness/`.
- **Reportes:** `COMPLETION_REPORT.md`, `AUDIT_REPORT.md`, `MT5_INTEGRATION_REPORT.md`, `docs/EDGE_DIAGNOSIS_REPORT.md`, `docs/ESTADO_ACTUAL.md`, `docs/RUTINA_EURUSD.md`, `docs/AUDITORIA_USO_2026-07-09.md`.

### Edge Diagnosis (COMPLETADA 2026-07-10)
Matriz **21 variantes × 8 símbolos = 168 celdas**, 0 errores, 0 insufficient.
- Mejor variante promedio: `no_session` → OOS PF **1.159**.
- Peor: `prox_1` → OOS PF **1.084** (el filtro de proximidad OB/FVG erosiona el edge).
- Mejor símbolo: **XAUUSD OOS PF 1.376**; peor: AUDUSD (0.849) y NZDUSD (0.809) PIERDEN.
- Celda TOP: `no_session` × XAUUSD → OOS PF **1.642**, N=900, Sharpe 3.28, WR 55.1%.
- Detalle completo en `docs/EDGE_DIAGNOSIS_REPORT.md` y `results/edge_diagnosis/full_results.json`.
- **Próximo paso pendiente:** walk-forward OOS real (PurgedKFold, DSR>0, N>=200/fold, PF>=1.10) de la celda ganadora antes de cualquier automatización.

---

## 3. Hitos y Objetivos

| ID | Objetivo | Descripción | Estado | Prioridad |
|----|----------|-------------|--------|-----------|
| A1 | Actualizar documentación | README, AGENT_ARCHITECTURE, harness docs, paths alineados | ✅ Completado | Alta |
| A2 | Parameter Tuning (F12) | Optuna integrado al pipeline, CLI listo, 7 tests | ✅ Completado | Alta |
| A4 | Stochastic Exhaustion (F10) | Implementado en `agents/wyckoff_agent.py:73` (divergencias, cruces, volumen) + verificado en pipeline | ✅ Completado | Alta |
| A5 | Tests + cobertura | Tests para 6 módulos + escenarios harness backtest | ✅ Completado | Alta |
| A7 | Validación cuantitativa (F9/F13) | PurgedKFold, CVaR, DSR, PBO, bootstrap en `ml/stats_validator.py`, 10 tests | ✅ Completado | Alta |
| A9 | Plan mejora estrategia (A-F) | ML filter off, symbol breakdown, confluence weights, sweep+OTE, detector invalidation, conflict mode | ✅ Completado | Alta |
| A10 | Edge Diagnosis (21×8) | 168/168 celdas, 0 errores, celda ganadora documentada | ✅ Completado | Alta |
| A11 | Arranque automático FundedNext | `start_hermes_session.ps1` + mutex + loop/vigilante headless + reporte salud + `.lnk` Inicio | ✅ Completado | Alta |
| A3 | Resolver discrepancia Harness | 11 adapters documentados en AGENT_ARCHITECTURE.md | ✅ Completado | Media |
| A6 | Expandir datos | >3-4 años históricos para OOS robusto (scripts listos: `download_multiyear.py`) | 🟡 Pendiente | Media |
| A12 | Walk-forward OOS celda ganadora | `no_session` × XAUUSD: PurgedKFold, DSR>0, N>=200, PF>=1.10 antes de live | 🔴 Pendiente | Alta |
| A8 | Deployment Guide (F8) | VPS, systemd/NSSM, recovery, monitoring. **AL FINAL** | 🔴 Pendiente | Baja |

**Criterio de completitud:** A1-A11 en 🟢 + A12 validado. El harness pasa 100% de escenarios. Solo entonces se considera production-ready para bot.

---

## 4. Fases Futuras (una vez cerrado el Hito Actual)

- **Fase Walk-Forward OOS:** validación dura de la celda ganadora `no_session` × XAUUSD (filtro antes de cualquier live automation).
- **Fase Live Trading & Robustez:** validación full en paper trading con harness, kill-switch testing, drift detection en producción, ML retraining scheduler.
- **Fase Deployment (F8):** ÚLTIMA. Solo cuando todo esté funcional y validado.
- **Fase Expansión:** soporte multi-símbolo/timeframe más amplio, UI enhancements, gobernanza de modelos.

---

## 5. Métricas de Éxito del Proyecto (Gate de Calidad)

- Profit Factor ≥ 1.25 (actual 1.61 ✅ backtest)
- Win Rate ≥ 52% (actual 63.74% ✅)
- Max Drawdown ≤ 10% (actual 4.96% ✅)
- Sharpe > 1.0 (actual 3.33 ✅)
- Expectancy > 0 (actual 0.1145R ✅)
- **Edge diagnosis OOS PF ≥ 1.10 en >1 símbolo:** ✅ (XAUUSD 1.376, USDCAD 1.264, etc.) — falta walk-forward.
- **Trade count por backtest ≥ 200** (actual 91 ⚠️ — mejorar con menos filtros o más datos, A6)
- Harness: 100% escenarios passing antes de cualquier merge.

---

## 6. Próximos Pasos Inmediatos

1. A12 — Walk-forward OOS de `no_session` × XAUUSD (PurgedKFold, DSR>0, N>=200/fold, PF>=1.10). Gate duro antes de live.
2. A6 — Expandir datos históricos (>3-4 años) para OOS robusto.
3. A8 — Deployment Guide queda AL ÚLTIMO.
4. Cualquier nuevo desarrollo pasa primero por el harness actualizado.

---

*Este documento es la ÚNICA fuente de verdad a partir de 2026-07-10. Reemplaza `docs/HOJA_DE_RUTA_SMC-SYSTEMS.md` (obsoleta, v2.0 04-jul) y cualquier versión anterior de CRONOGRAMA_Y_ROADMAP.md. Alineado con COMPLETION_REPORT.md, AUDIT_REPORT.md, EDGE_DIAGNOSIS_REPORT.md y ESTADO_ACTUAL.md.*
