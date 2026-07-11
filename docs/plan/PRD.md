# PRD — Product Requirements Document

**Proyecto:** SMC-SYSTEMS
**Versión:** 1.0
**Fecha:** 2026-07-11
**Estado:** Borrador para revisión de Ruben

---

## 1. Visión general

SMC-SYSTEMS es un sistema de trading algorítmico basado en **Smart Money
Concepts (ICT)** y **Wyckoff**, diseñado para el desafío de prop firm
**FundedNext**. Hoy opera como **observador de análisis** (no abre órdenes):
genera contexto accionable diario para que Ruben decida. Incluye un motor de
backtest ICT desde cero (`ict_backtest/`) para validar edges antes de cualquier
automatización.

El PRD describe QUÉ hace el producto, para QUIÉN, y cuál es su alcance. La
arquitectura (CÓMO) vive en el SAD; los requisitos técnicos en el SRS.

---

## 2. Usuarios y personas

| Persona | Rol | Necesidad principal |
|---------|-----|---------------------|
| **Ruben Mujica** | Radiologo / Trader prop firm | Contexto ICT/Wyckoff diario, ficha accionable, semáforo de sesgo, alertas |
| **Agente autónomo (Hermes)** | IA operative | Documentación clara de propósito/arquitectura para extender el sistema sin romper nada |
| **Auditor externo** | Revisor de calidad | Trazabilidad regla→código→métrica, tests reproducibles, PF con costos y OOS |

---

## 3. Funcionalidades del producto

### 3.1 Observador FundedNext (producción)
- **F-01:** Loop de análisis 24/7 (lun-vie, finde off) que genera ficha técnica
  EURUSD D1/H4/M15 + informe + semáforo + alertas locales (popup + beep).
- **F-02:** App de escritorio PySide6 (`app_observador/`) con semáforo, mapa
  ICT embebido, alineación Wyckoff, noticias rojas, black-box JSON (90 días).
- **F-03:** Vigilante de riesgo que SOLO cierra posiciones manuales al 2%/4%
  flotante (no abre nada).
- **F-04:** Arranque automático (`start_hermes_session.ps1` en Carpeta de
  Inicio) que abre MT5, baja datos en vivo, lanza loop + vigilante + observador.

### 3.2 Motor de backtest ICT (`ict_backtest/`) (producción)
- **F-10:** Detección de estructura de mercado multi-TF (trend, BOS, CHOCH,
  liquidity) SIN look-ahead.
- **F-11:** Motor event-driven de secuencia ICT (sweep → displacement → BOS →
  retorno al cuadro) vela a vela.
- **F-12:** Simulación de trades vela a vela con SL/TP, hold limit, y costos
  (spread/comisión/slippage).
- **F-13:** Optimizador bayesiano (Optuna TPE) + walk-forward multi-fold para
  validar el edge OUT-OF-SAMPLE.
- **F-14:** Curva de equidad (R acumulado + drawdown) graficada por trade.

### 3.3 Edge Diagnosis (SMC puro, sin ML) (completada)
- **F-20:** Matriz 21 variantes × 8 símbolos = 168 celdas, gobernador
  neutralizado. Mejor celda `no_session` × XAUUSD OOS PF 1.642.

### 3.4 Backtest combinado + ML (producción, bot heredado)
- **F-30:** Backtest combinado multi-símbolo con filtro de calidad XGBoost.
- **F-31:** Risk governor (NORMAL → CAUTION → DEFENSIVE → LOCKDOWN).
- **F-32:** Pipeline ML offline (dataset, train cronológico, walk-forward,
  Optuna, validación estadística CVaR/DSR/PBO).

### 3.5 Multi-agente (producción)
- **F-40:** ICTAgent, WyckoffAgent (+ stochastic exhaustion), StructureAgent,
  DecisionAgent (voting ponderado).

---

## 4. Alcance

### 4.1 Incluido (in-scope)
- Modo observador completo (análisis, no ejecución).
- Backtest ICT desde cero con validación OOS rigurosa.
- Edge diagnosis SMC puro.
- Filtro ML de calidad (opcional, desacoplado de `ict_backtest`).
- Documentación viva (este PRD + VISION/SRS/SAD/SDD/TEST PLAN).

### 4.2 Fuera de alcance (out-of-scope, hoy)
- **Automatización de órdenes en vivo** (bot). El puente MT5 ZeroMQ existe
  pero NO está cableado al flujo diario. Requiere aprobación de Ruben +
  cumplimiento FundedNext + walk-forward OOS validado.
- Trading de opciones binarias (framework QUOTEX, proyecto hermano separado).
- Multi-cuenta / multi-broker masivo.

---

## 5. Requisitos de experiencia (UX)
- **UX-01:** El observador debe ser legible en 5 segundos (semáforo + sesgo).
- **UX-02:** Alertas popup + beep en horario de operación (07:00–20:00 EC).
- **UX-03:** El launcher pesado (`run_capa3_optuna.bat`) debe mostrar barra de
  progreso + ETA y NO cerrarse solo (PowerShell -NoExit).

---

## 6. Métricas de éxito del producto
- **M-01:** El observador entrega ficha diaria sin intervención (24/7 lun-vie).
- **M-02:** Todo PF reportado por `ict_backtest` es reproducible, con costos y
  OOS multi-fold (sobrevive auditoría externa).
- **M-03:** Trazabilidad regla ICT → detector → test → número es completa.

---

## 7. Dependencias y supuestos
- **D-01:** MetaTrader 5 terminal (FundedNext) para datos en vivo.
- **D-02:** Python 3.11+ (se usa `C:\Python314\python.exe` para MT5 real).
- **S-01:** Ruben revisa y aprueba antes de cualquier automatización de órdenes.
- **S-02:** Los datos históricos en `data/raw/*.parquet` están actualizados.

---

## 8. Relación con otros documentos
- `docs/VISION.md` — propósito y principios.
- `docs/SRS.md` — requisitos funcionales/NO funcionales detallados.
- `docs/SAD.md` — arquitectura.
- `docs/CRONOGRAMA_Y_ROADMAP.md` — hitos (fuente de verdad).
- `COMPLETION_REPORT.md` — wiring y métricas.
