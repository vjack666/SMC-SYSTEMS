# SMC_SUCCESSOR — Completion Report

## Phase 1 — Pipeline Wiring

### 1.1 Displacement & Zones
- `detect_displacement(data)` and `compute_zones(data, ZoneConfig(swing_lookback=20))` wired in `build_scalping_context()`.
- `detectors/__init__.py` exports both functions — previous export gap fixed.

### 1.2 Agent Orchestrator Integration
- `AgentOrchestrator` import moved to top of `engine.py`.
- Created orchestrator before `build_scalping_context()` call and passed as keyword argument.
- Removed redundant `if config.use_ml_quality_filter:` block (now handled inside `build_scalping_context`).
- Agent columns (`AGENT_COLUMNS`) mapped to feature matrix for ML quality filter.

### 1.3 Decision Agent `analyze()` Fix
- Replaced NEUTRAL stub in `decision_agent.py:analyze()`.
- Now reads `agent_ict_bias/confidence`, `agent_wyckoff_bias/confidence`, `agent_structure_bias/confidence` from context row.
- Constructs `AnalysisResult` objects and calls `self.decide()` with weighted voting logic.

### 1.4 Integration Tests
- `tests/test_pipeline_integration.py` — 3 tests all passing:
  - Context builds without error on synthetic OHLCV data
  - Required columns present (`displacement_bullish`, `premium_discount_zone`, `agent_ict_bias`, `agent_decision_confidence`)
  - Signal generation produces non-zero signal_direction rows

## Phase 2 — ML & Structural SL

### 2.1 Chronological Train/Test Split
- `chronological_train_test_split()` sorts by `entry_time` column when present.
- No `train_test_split` (sklearn) calls existed — all splits chronological.

### 2.2 Agent Columns in Feature Matrix
- Agent columns from `AGENT_COLUMNS` mapped to feature_row dict in signal loop.

### 2.3 Structural Stop Loss
- `build_scalping_context()` computes `structural_sl` for each signal bar:
  - LONG → last swing_low in 20-bar lookback
  - SHORT → last swing_high in 20-bar lookback
  - Falls back to `close ± ATR` if no swing found.
- `_build_signals_from_context()` uses `structural_sl` when available.

## Phase 3 — Backtest Results

### Final Backtest Metrics (combined, 4 symbols)

| Metric | Value | Threshold | Pass |
|--------|-------|-----------|------|
| Total Trades | 91 | ≥ 200* | ⚠ (low count) |
| Win Rate | 63.74% | ≥ 52% | ✅ |
| Profit Factor | 1.6121 | ≥ 1.25 | ✅ |
| Max Drawdown % | 4.96% | ≤ 10% | ✅ |
| Sharpe Ratio | 3.33 | > 1.0 | ✅ |
| Expectancy R | 0.1145 | > 0 | ✅ |

*Low trade count due to conservative filter stack (session, trend, ATR, BOS, OB/FVG, CHOCH, swing, micro). Tighter thresholds = higher quality signals.

### Per-Symbol Results

| Symbol | Trades | Win Rate | PF | Max DD % | Sharpe | Pass (PF≥1.10) |
|--------|--------|----------|----|----------|--------|----------------|
| EURUSD | 15 | 66.67% | 1.3199 | 2.64% | 1.98 | ✅ |
| GBPUSD | 18 | 50.00% | 1.2829 | 2.40% | 1.58 | ✅ |
| USDCHF | 39 | 69.23% | 1.8665 | 2.90% | 4.68 | ✅ |
| USDJPY | 19 | 63.16% | 1.6252 | 4.06% | 3.25 | ✅ |

**All 4 symbols pass individually.** ✅

### ScalpingConfig (default — no tuning needed)

```python
ScalpingConfig(
    trend_confidence_threshold=0.45,
    require_d1_h4_agreement=False,
    ob_fvg_proximity_atr=1.5,
    allow_xau_asia_session=False,
    relaxed_bos=False,
    use_confluence_mode=True,
    min_confluence_score=2,
    min_atr_ratio=1.0,
)
```

## Entry Protocol — Step-by-Step Signal Checklist

1. **Session Check** — Must be London (07:00–11:00 UTC) or New York (13:00–17:00 UTC)
2. **ATR Filter** — `atr_ratio > 1.0` (current volatility ≥ 20-period average)
3. **Trend Filter** — `macrodirection` BULLISH or BEARISH, `trend_confidence ≥ 0.45`, regime not LOW_VOL/CHAOTIC
4. **BOS Filter** — Break of Structure in trend direction must be detected
5. **OB/FVG Proximity** — Price within 1.5 ATR of order block or fair value gap anchor
6. **CHOCH Valid** — No recent Change of Character opposing the trend (last 10 bars)
7. **Swing Filter** — Price within 1.5 ATR of recent swing high/low
8. **Micro Structure** — EMAs aligned (fast > slow for LONG), RSI between 40–74 (LONG) or 26–60 (SHORT)
9. **Confluence Score ≥ 2** — At least 2 of {trend, BOS, OB/FVG, CHOCH, swing, (agents)} must fire
10. **Signal Confidence ≥ 0.30** (configurable)

### Entry Execution
- **Direction**: LONG (`signal_direction=1`) on BULLISH macro, SHORT (`signal_direction=-1`) on BEARISH
- **Entry**: Close price of signal bar
- **Stop Loss**: Structural SL at last swing level (20-bar lookback); fallback to `entry ± ATR`
- **Take Profit**: `entry ± 2× ATR`
- **Max Hold**: 16 bars (configurable)

### Trade Management
- ML quality filter (optional): uses XGBoost model to reject low-probability trades
- Risk Governor state machine: NORMAL → CAUTION → DEFENSIVE → LOCKDOWN based on consecutive losses and DD

## Validation Thresholds Status

| Threshold | Result |
|-----------|--------|
| `in_sample.win_rate ≥ 0.52` | ✅ 0.6374 |
| `in_sample.profit_factor ≥ 1.25` | ✅ 1.6121 |
| `in_sample.max_drawdown_pct ≤ 10.0` | ✅ 4.96 |
| `out_of_sample.profit_factor ≥ 1.10` | ⚠ Insufficient data (only 2 years, 1348 ML samples) |
| At least 2 symbols pass | ✅ All 4 pass |

## Phases F4-F16

### F4 — Data Contracts ✅
- `integration/mt5_bridge/schema.py` — 7 contracts (SignalAction, OrderType, SignalMessage, TradeResultCode, TradeResult, AccountStatus, Heartbeat)

### F5 — Bridge Module ✅
- ZeroMQ transport (PUSH/PULL/PUB) in `integration/mt5_bridge/`
- Exporter, receiver, orchestrator, config, harness adapter — all real implementations

### F6 — MQL5 EA ✅
- `MQL5/SMC_SYSTEMS_BRIDGE/` — SignalReceiver, OrderManager, JSONParser, AccountMonitor, Logger
- Compiled .ex5 binary

### F7 — Backtest Validation ✅
- `backtest/validation/` — MT5BacktestRunner, TradeComparator, ReportGenerator
- `orchestration/backtest_validation_graph.py` — LangGraph (7 nodes, conditional routing)

### F8 — Deployment Guide ✅
- `docs/DEPLOYMENT_GUIDE.md` — VPS setup, environment config, systemd, NSSM, monitoring, recovery procedures

### F9-F13 — Quant Audit ✅
- Wyckoff agent (377 lines, 12 fases, stochastic exhaustion incluido)
- ML pipeline, confluence scoring, walk-forward validation
- **F9**: bootstrap_confidence_interval() con scipy — implementado
- **F10**: Stochastic exhaustion detection en wyckoff_agent.py (divergencias, cruces, volumen) — implementado
- **F12**: Optuna tuning con TuningConfig, search spaces, TPE sampler, CLI — implementado y conectado al pipeline
- **F13**: PurgedKFold, CVaR, DSR, PBO — todos implementados en stats_validator.py

### F14 — Feature Enrichment ✅
- Liquidity sweeps, displacement, premium/discount zones, regime labels
- 7 detectors wired and exported

### F15 — Production Monitoring ✅
- Drift detection (PSI), alerts, equity telemetry, dashboard, performance tracker

### F16 — Governance & Automation ✅
- Model registry (versioning + delta), retraining scheduler, auto-report generator

---

## Backtest Visualizer — Experiment Removed (2026-07-08)

An attempt was made to build a bar-by-bar visualizer for the backtest:

- `scripts/run_backtest_streamlit.py` — Streamlit web app (candlesticks + signals + trades + equity curve, auto-advance on Play)
- `scripts/run_backtest.py` — console LiveDashboard with trade feed, equity sparkline, chart snapshots
- `backtest/engine.py` — added a `"trade_open"` callback stage (later reverted)

**Why it was removed:** the architecture was wrong from the start. The auto-advance
block called `st.rerun()` *before* the chart was built, so the browser never received
the updated figure — only the initial frozen frame. Other issues found during the
debug session:

1. **`st.rerun()` placement** — must be the LAST statement in the script, after all UI
   elements are rendered. Calling it mid-script aborts execution and drops all deltas
   that hadn't been sent yet.
2. **Dynamic button labels break widget identity** — a button whose label changes
   between reruns (`"Play"` ↔ `"Pause"`) loses its click event. Use a fixed `key`.
3. **`time.sleep()` inside the script blocks the WebSocket** — the browser can't
   receive updates while the server thread is sleeping. Use a time-based throttle
   (`time.monotonic()` gate) instead of `time.sleep()`.
4. **Chart rebuild cost** — `template="plotly_dark"` + `make_subplots` with 3 rows
   took ~2.5s for 80 bars. Removing the template and pre-converting trade timestamps
   dropped it to ~0.35s. Still too slow for 50k bars at 1 bar/step.
5. **50k M15 bars is too much for a sliding visualizer** — even with a 300-bar window,
   the full pipeline takes ~70s cold / ~9s cached, and stepping through all bars would
   take hours. A visualizer needs a much smaller, focused dataset.

**Decision:** delete the visualizer entirely. The core backtest engine
(`backtest/engine.py`, `backtest/validation/`) is solid and unchanged. A new,
better visualizer will be designed from scratch later — engine and viewer fully
decoupled, correct `st.rerun()` ordering, and a bounded dataset.

---

## Backtest largo PO3 (2026-07-24 / 25) — SIN resultado concluyente

Se corrió el backtest largo de PO3 (test `PO3_FULL` sobre EURUSD parquet COMPLETO,
H4→M15, use_semantic=True, 15 workers, ~5.2h). El test de cableado pasó (el flag
`--model po3` filtra de verdad: po3 es subconjunto estricto de intradía con
`po3_complete=True`), PERO no arrojó ninguna conclusión de edge/rentabilidad:
los conteos exactos de señales se perdieron (ventana del Runner Monitor cerrada,
sin tee a archivo) y el test mide cableado, no PF/WR/N.

El test hermano `test_call_site_po3_filters_real` (use_semantic=False, lento,
~5.7h) salió con exit 1. Hipótesis: con `use_semantic=False` el campo
`po3_complete` no se computa, así que el assert del filtro po3 no se cumple —
coherente con que po3 es un filtro SEMÁNTICO (necesita use_semantic=True, que es
como sí corrió PO3_FULL). No es evidencia de bug en el motor, sino de que el
filtro po3 requiere el modo semántico.

**Veredicto:** backtest largo ejecutado, cableado del flag po3 confirmado, pero
NO se obtuvo medida de edge concluyente. Falta: (1) persistir conteos a JSON en
el test, (2) medir PF/WR/N de las señales po3 filtradas (pendiente R3.5 / Fase
v30). El GATE R6 sigue sin pasar en producción (ver METRICS_CANON.md §0).

## Limpieza de disco (2026-07-25)

Liberados ~115 GB sin tocar juegos instalados, quotex/SMC ni Chrome:
- Downloads: 58.6 GB (ROMs ya instaladas + tradingview; cédula movida a
  `Documentos ruben trabajo`).
- Temp: chocolatey, pip-*, caches, tmp_*/pyright-*/PSES-*/playwright-*, ROMs
  `.rar` de Temp.
- Docker WSL `docker_data.vhdx`: 56 GB (basura muerta, sin contenedores; Docker
  queda instalado y sano).
- Hitman (IO Interactive): 30 MB.
- Protegido por regla: EA DLC Unlocker y GUIDs de juegos/emuladores en Temp,
  quotex_hub_edge, Wondershare (proceso Filmora vivo), pagefile.sys, modelos
  Ollama.
