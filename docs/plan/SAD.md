# SAD — Software Architecture Document

**Proyecto:** SMC-SYSTEMS
**Versión:** 1.0
**Fecha:** 2026-07-11
**Estado:** Borrador para revisión

---

## 1. Resumen de arquitectura

SMC-SYSTEMS es un sistema **modular, event-driven**, dividido en dos grandes
familias que comparten la misma base de datos OHLCV (Parquet / MT5):

1. **Plano de observación (producción):** loop 24/7 que analiza y alerta. No
   ejecuta.
2. **Plano de backtest/validación (`ict_backtest/`):** motor ICT desde cero
   para medir edges antes de cualquier automatización.

Ambos planes leen de `data/raw/*.parquet` y de la biblioteca de reglas
`docs/ict/`. La trazabilidad regla→código→métrica es el eje transversal.

---

## 2. Capas y componentes

```
┌─────────────────────────────────────────────────────────────┐
│                   CAPA DE PRESENTACIÓN                       │
│   app_observador/ (PySide6)  │  scripts/loop_analisis.py     │
│   semáforo · mapa ICT · black-box                            │
└───────────────────────────┬─────────────────────────────────┘
                            │ contexto + alertas
┌───────────────────────────▼─────────────────────────────────┐
│              CAPA DE ANÁLISIS MULTI-AGENTE                    │
│   agents/ : ICT · Wyckoff(+stoch exhaustion) · Structure ·   │
│            Decision (voting ponderado) → Orchestrator         │
└───────────────────────────┬─────────────────────────────────┘
                            │ señales + scores
┌───────────────────────────▼─────────────────────────────────┐
│           CAPA DE DETECCIÓN / ESTRUCTURA DE MERCADO           │
│   detectors/ : BOS · CHOCH · FVG · OB · displacement · zones  │
│   ict_backtest/market_structure.py : trend/BOS/CHOCH/liq MT  │
│   features/ : FeatureEngine (30+ features para ML)            │
└──────────────┬───────────────────────────────┬───────────────┘
               │                               │
┌──────────────▼──────────────┐ ┌─────────────▼────────────────┐
│  CAPA DE SEÑALES / PIPELINE │ │   CAPA DE BACKTEST ICT         │
│  signals/ + ml/inference.py │ │   ict_backtest/ (sin ML)      │
│  (filtro calidad XGBoost)   │ │   engine · sequence · optimize │
└──────────────┬──────────────┘ └─────────────┬────────────────┘
               │                               │
┌──────────────▼──────────────┐ ┌─────────────▼────────────────┐
│  CAPA DE RIESGO / GOVERNANCE│ │   CAPA DE VALIDACIÓN ESTAD.   │
│  risk/ governor · sizing    │ │   ml/stats_validator (CVaR,   │
│  scripts/vigilante_riesgo   │ │   DSR, PBO) · harness/        │
└──────────────┬──────────────┘ └─────────────┬────────────────┘
               │                               │
┌──────────────▼──────────────────────────────▼───────────────┐
│              CAPA DE DATOS (data/raw/*.parquet · MT5)         │
│   MT5 connector · datasets ML · black-box JSON (90d)         │
└─────────────────────────────────────────────────────────────┘

        [OPCIONAL, NO CABLEADO] CAPA DE EJECUCIÓN
   integration/mt5_bridge (ZeroMQ) · MQL5/ · paper_trading/
   → solo se activa con aprobación de Ruben + cumplimiento
```

---

## 3. Flujo de datos — observador (producción)

```
MT5 (live) / Parquet (hist)
   │ build_scalping_context()
   ▼ detectors (BOS/CHOCH/FVG/OB/displacement/zones) + indicators + trend
   ▼ AgentOrchestrator → ICT/Wyckoff/Structure/Decision (voting)
   ▼ Confluence scoring → signal confidence → regime threshold
   ▼ (opcional) QualityFilter XGBoost gate
   ▼ scripts/loop_analisis.py → ficha + informe + semáforo + alertas
   ▼ app_observador (PySide6) ← DataStreamer + TradingWorker
   ▼ vigilante_riesgo.py (SOLO cierra si Ruben opera manual)
```

---

## 4. Flujo de datos — backtest ICT (`ict_backtest/`)

```
data/raw/{SYMBOL}_{TF}.parquet
   │ data_feed.load_frames(symbol, htf, ltf)
   ▼ detect_market_structure(df)  [SIN look-ahead]
   ▼ run_sequence(ms_htf, ms_ltf, config)  [event-driven]
   │   sweep → displacement → BOS → retorno al cuadro
   ▼ build_signals_from_frames() → ICTSignal[]
   ▼ simulate_trade(frame, signal, max_hold, cost)  [vela a vela, con costos]
   ▼ sequence_pf() → {trades, winrate, pf, total_r, max_dd_r}
   │
   ├─ run_backtest.py (Capa 2, params fijos)
   ├─ optimize.py (Capa 3: Optuna TPE + walk-forward multi-fold)
   └─ plot_equity_curve.py (PNG equidad + DD)
```

---

## 5. Decisiones arquitectónicas (ADR resumidas)

- **ADR-01:** `ict_backtest/` SIN ML por diseño (edge "SMC puro" verificable).
  El filtro ML vive en `ml/` y es opcional/desacoplado.
- **ADR-02:** El observador NUNCA ejecuta; la ejecución es capa separada
  (ZeroMQ/MQL5) no cableada. Puerta dura de activación.
- **ADR-03:** Backtest lee Parquet local; NO requiere MT5 abierto.
- **ADR-04:** `_row_at_time` vive en `ict_backtest/_util.py` (único punto de
  verdad) para evitar duplicación (hallazgo #7 auditoría).
- **ADR-05:** Swing points SIN look-ahead mediante ventana no centrada +
  `shift(lookback).ffill()` (hallazgo #1 auditoría).
- **ADR-06:** Walk-forward ROLLING multi-fold con dirección temporal correcta
  (pasado→futuro), no single-split (hallazgo #5 auditoría).

---

## 6. Tecnologías

| Capa | Tecnología |
|------|-----------|
| UI | PySide6 |
| Análisis | Python 3.11+ (C:\Python314 para MT5) |
| Datos | pandas, pyarrow (Parquet), MetaTrader5 |
| Backtest | pandas (vela a vela), Optuna (TPE) |
| ML | XGBoost, scikit-learn, scipy |
| Gráficos | matplotlib |
| Orquestación | LangGraph (backtest validation graph) |
| Testing | pytest, harness (11 adapters, 14 scenarios) |
| Doc graph | graphify (AST + semantic) |

---

## 7. Calidad transversal (NFR del SRS)
- Sin look-ahead (NFR-Q1) — `_swing_points` con `shift(lookback)`.
- Reproducibilidad (NFR-A1) — logs con params + SHA; `tests/` deterministas.
- Trazabilidad (NFR-A3) — regla ICT → detector → test.

---

## 8. Riesgos arquitectónicos
- **RA-01:** Performance del loop vela-a-vela (no vectorizado) — medio plazo.
- **RA-02:** Acoplamiento de `ml/walk_forward.py` al ML (no reusable para
  `ict_backtest` sin refactor) — ya resuelto en `ict_backtest/optimize.py`.
- **RA-03:** Activación prematura de ejecución en vivo sin walk-forward OOS
  validado — mitigado por ADR-02 (puerta dura).

---

## 9. Relación con otros documentos
- `docs/VISION.md` — propósito.
- `docs/PRD.md` — funcionalidades.
- `docs/SRS.md` — requisitos.
- `docs/ict/SDD_ICT_BACKTEST.md` — diseño de módulos de backtest.
- `docs/ict/SDD_REFACCION_2026-07-11.md` — fixes de auditoría.
- `COMPLETION_REPORT.md` — wiring detallado.
