# CRONOGRAMA Y ROADMAP - SMC-SYSTEMS

**Proyecto:** SMC-SYSTEMS (renombrado desde SMC_SUCCESSOR)
**Repositorio:** https://github.com/vjack666/SMC-SYSTEMS
**Versión del Roadmap:** 2.3 (post-R4 audit + SL estructural + tesis ejecución 3 capas + libro 18)
**Fecha de Actualización:** 2026-07-14
**Estado General:** 🟢 Modo observador FundedNext operativo 24/7. R4 (ICT puro) auditado: backtests previos contaminados por look-ahead (97%), corregidos; modelos re-medidos sin edge real salvo Turtle Soup limpio pendiente. Tesis de ejecución óptima documentada (libro 18). Pendiente: Turtle Soup v2.8 limpio, libros 21/22/23 (SMT/Breaker/OTE), cablear exec_tf en motor (v30).

---

## 1. Principios Rectores (NO NEGOCIABLES)

1. **Este Cronograma es la ÚNICA fuente de verdad.** `docs/HOJA_DE_RUTA_SMC-SYSTEMS.md` quedó OBSOLETO y redirige aquí. Cualquier decisión se alinea en este documento.
2. **Harness-First Development.** Todo nuevo módulo/feature/refactor pasa por `harness/` y 100% de escenarios antes de completo.
3. **Limpieza y Enfoque.** Solo lo esencial versionado.
4. **Documentación Dual.** Consumible por humanos y agentes IA.
5. **Cierre de Ciclo con Informe Semanal.**
6. **Medir antes de afirmar.** Ningún PF sin costos ni sin re-auditar look-ahead (lección R4: 97% de velas M15/M5 contaminadas por HTF futuro en v2.7).
7. **Trader manda.** No bot de órdenes hasta A12 + autorización.

---

## 2. Estado Actual del Repositorio (2026-07-14)

### Modo de operación real
- **OBSERVADOR FUNDEDNEXT (SIN BOT):** loop `scripts/loop_analisis.py` 24/7 (lun-vie). NUNCA abre órdenes. `vigilante_riesgo.py` SOLO CIERRA (2%/4%).
- Arranque automático vía `start_hermes_session.ps1` (✅ A11 operativo).
- Código de bot heredado (`run_paper_trading.py`, `run_live_trading.py`, MQL5 EA) implementado pero NO cableado al flujo diario.

### Hallazgo crítico post-auditoría R4 (2026-07-13 → 2026-07-14)
- **Look-ahead cross-timeframe (CRÍTICO, ya corregido):** el join H4→M5 usaba velas que aún NO cerraban. Medido: **97.4% de las velas M15/M5 estaban contaminadas por precio futuro del HTF**. Los backtests "buenos" de R4 (PF 1.14 de Turtle) eran FALSO positivo — el modelo veía el futuro. Corregido en `6d4b158`/`07afc0e` (exigir barra cerrada vía `TF_FREQ` + `row_at_time`).
- Tras limpiar look-ahead, modelos R4 re-medidos (v2.7):
  - Silver Bullet: PF 0.896 / 0.639 → **RECHAZADO** (el modelo de verdad pierde).
  - PO3 + displacement: 2 y 0 trades → INCONCLUSO.
- **Turtle Soup v2.8 ALINEADO A TESIS 18 (2026-07-14):** `run_backtest.py` camino sequence usa SL mecha sweep + RR 1:3 + killzone. EURUSD M15 H4→M15: **0 señales** (1787 sweep → 170 displace → 92 BOS → 0 entry). El retorno al cuadro (mitigation) no ocurre tras el BOS con el SL estructural; el modelo no llega a operar. Veredicto: **no concluyente** (no PF<1.10, sino 0 trades). Requiere diagnóstico de por qué el `_touches_zone` no se cumple (cuadro fallback o killzone). GBPUSD pendiente.

### SL Estructural (v29, commit `e2a9c11` 2026-07-13)
- El SL ahora se ancla a la **mecha del sweep** (no ATR de fallback). Filtro `STRUCT_SL_MAX_ATR`.
- Backtest v29: EURUSD PF 1.128, GBPUSD PF 2.101 — PERO sostenidos en `hold_limit` (7/11 y 11/13 trades cerraron por hold, no TP). Rentable vs ATR v28 (<1), pero el éxito vive del hold, no del TP real.

### Tesis de ejecución óptima (2026-07-14, commit `46b074e`)
- **Libro 18** fija la regla dura: 3 capas HTF/ITF/exec; **SL y entry SIEMPRE en exec TF**; RR mínimo 1:3; 3 killzones (London/NY AM/NY PM); M5 estándar / M1 avanzado.
- Libros 15/16/17/20 corregidos a esa regla (ITF agregado, RR 1:3, M3, killzones completas).
- **Hueco de código (v30) PARCIALMENTE cerrado (2026-07-14):** el camino `sequence`/Turtle Soup en `run_backtest.py` YA usa SL estructural de mecha de sweep (`calc_structural_sl`), RR 1:3 y filtro killzone (alineado a libro 18). Falta: `build_signals_from_frames` recibir `exec_tf`/`itf` separados de `ltf` (hoy `exec_tf == ltf`) para el camino checklist/scalping y agregar M3 en `TF_FREQ`.

### Fragmentación confirmada por grafo (2026-07-14, graph.json @ 46b074e)
- 5 módulos ICT en **6 comunidades distintas** (pipeline=1/2/5/73, ict_agent=39/62, sequence=36/70, rules=57, engine=18).
- **Solo 2 aristas cruzadas** en todo el sistema: `engine.py ↔ rules.py` (el motor llama a los checklists). `pipeline.py`, `ict_agent.py`, `sequence.py` son **islas totales** (0 aristas cruzadas).
- Consecuencia: backtest (`sequence.py`/`engine.py`) y señales en vivo (`pipeline.py`) salen de motores distintos con pesos que divergen. Deuda de arquitectura (ver R7).

---

## 3. Hitos y Objetivos

| ID | Objetivo | Descripción | Estado | Prioridad |
|----|----------|-------------|--------|-----------|
| A1 | Actualizar documentación | README, AGENT_ARCHITECTURE, harness | ✅ | Alta |
| A2 | Parameter Tuning (F12) | Optuna integrado | ✅ | Alta |
| A4 | Stochastic Exhaustion (F10) | Wyckoff agent | ✅ | Alta |
| A5 | Tests + cobertura | 6 módulos + harness | ✅ | Alta |
| A7 | Validación cuantitativa (F9/F13) | PurgedKFold, CVaR, DSR, PBO | ✅ | Alta |
| A9 | Plan mejora estrategia | ML off, symbol breakdown | ✅ | Alta |
| A10 | Edge Diagnosis (21×8) | 168/168 celdas | ✅ | Alta |
| A11 | Arranque automático FundedNext | PowerShell + mutex + loop | ✅ | Alta |
| A3 | Discrepancia Harness | 11 adapters documentados | ✅ | Media |
| A6 | Expandir datos | >3-4 años históricos | 🟡 En curso | Alta |
| **R0** | **Contratos PO3 congelados** | A/M/D aprobados (libro 08) | ✅ | Alta |
| **R1** | **Capa de estado PO3** | `po3_state`, tests, UI | ✅ | Alta |
| **R2** | **Killzones + TZ unificadas** | UTC canónico, helper único | ✅ | Alta |
| **R3** | **Huecos arquitectura (liquidez, open día, CHOCH-gate)** | canonical_sweep, PO3-2 | ✅ | Alta |
| **R3.5** | **Huecos canon ICT en tesis (SMT/Breaker/OTE)** | Libros 14-17/20 hechos; **21/22/23 pendientes** | 🔶 Parcial | Alta |
| **R4** | **Auditoría + medición ICT puro** | Look-ahead corregido; Silver Bullet/PO3 sin edge; **Turtle limpio pendiente** | 🔶 En curso | Alta |
| **R4-tesis** | **Tesis ejecución óptima (libro 18)** | 3 capas + SL/entry exec TF + RR 1:3 | ✅ | Alta |
| A12 | Walk-forward OOS celda ganadora | `no_session`×XAUUSD falló 1er pase (PF -0.058, N bajo). **Re-evaluar tras R4 limpio** | 🔴 Pendiente (re-run) | Alta |
| A8 | Deployment Guide (F8) | VPS, systemd/NSSM | 🔴 Pendiente | Baja |
| **R5** | **Datos A6 (bloqueante A12)** | ≥3-4 años M15 XAUUSD/EURUSD | 🟡 En curso | Alta |
| **R6** | **Backtest profesional (reloj/fill/costos)** | Libro 13 + plan; código G1-G3 pendiente | 🔶 Docs ✅ / Código ⏳ | Alta |
| **R7** | **Unificar motores ICT (anti-islas)** | pipeline/ict_agent/sequence/rules/engine → single source of truth | 🔴 Pendiente (deuda grafo) | Alta |

**Criterio de completitud:** A1-A11 + R0-R4 + libro 18 en 🟢. Harness 100%. A12 validado con datos suficientes. Solo entonces production-ready para bot.

---

## 4. Fases Futuras

- **Fase R4-clean:** Turtle Soup v2.8 SIN look-ahead + YA ALINEADO A TESIS 18 (SL mecha sweep, RR 1:3, killzone) en `run_backtest.py` camino sequence. Veredicto final del único modelo que rozó el gate. Si PF<1.10, R4 se documenta "sin edge para live".
- **Fase R3.5-libros:** escribir 21 (SMT), 22 (Breaker/MMXM), 23 (OTE) y cablear detectores (bloquea R4-honesto v30).
- **Fase R6 WF/OOS:** re-run A12 tras R5.
- **Fase R7 unificación:** un solo motor de evaluación ICT (matar las 4 islas del grafo) antes de cualquier live.
- **Fase Live (A8):** ÚLTIMA, solo con OK humano.

---

## 5. Métricas de Éxito / Gate

- Profit Factor ≥ 1.25 (backtest 1.61 ✅ — pero ese número es del stack SMC heredado, NO del ICT puro R4).
- **R4 ICT puro:** gate PF OOS ≥ 1.10 por modelo. Hoy: Silver Bullet RECHAZADO, PO3 INCONCLUSO, **Turtle Soup PENDIENTE v2.8**.
- Win Rate ≥ 52% · Max DD ≤ 10% · Sharpe > 1 · Expectancy > 0 (del stack SMC, no R4).
- Edge diagnosis OOS PF ≥ 1.10 en >1 símbolo: ✅ (XAUUSD 1.376, etc.) — falta walk-forward A12.
- Trade count ≥ 200/backtest (actual 91 ⚠️).
- Harness: 100% escenarios antes de merge.

---

## 6. Próximos Pasos Inmediatos

1. **R4-clean:** Turtle Soup v2.8 limpio YA ALINEADO a tesis 18 → veredicto final (corriendo EURUSD/GBPUSD en fondo).
2. **R3.5:** libros 21/22/23 (SMT/Breaker/OTE) + detectores.
3. **R4-tesis→código (v30, resto):** `build_signals_from_frames` con `exec_tf`/`itf` explícitos + M3 en `TF_FREQ` (el camino sequence/Turtle Soup YA usa SL estructural+RR1:3+killzone). Cierra la regla dura del libro 18 para scalping/checklist.
4. **R7:** unificar motores ICT (anti-islas del grafo).
5. **A6/R5:** expandir datos para A12.
6. Cualquier nuevo desarrollo pasa por harness actualizado.

---

*ÚNICA fuente de verdad a partir de 2026-07-14 (v2.3). Reemplaza versiones previas. Alineado con COMPLETION_REPORT.md, docs/auditorias/AUDIT_R4_FINAL_2026-07-13.md, docs/ict/18_EJECUCION_OPTIMA_TF_SL_ENTRY.md, y graph.json @ 46b074e (auditoría de islas ICT: 2 aristas cruzadas / 5 módulos).*
