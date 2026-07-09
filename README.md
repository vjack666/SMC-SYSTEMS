# SMC-SYSTEMS

> **⚠️ MODO ACTUAL: OBSERVADOR FUNDEDNEXT (SIN BOT)**
> El sistema se usa hoy como **observador de análisis** para el challenge de
> prop firm FundedNext (cuenta demo). El loop `scripts/loop_analisis.py` corre
> 24/7 (lun-vie, finde apagado) y genera ficha técnica + informe + semáforo +
> alertas locales. **NUNCA abre órdenes.** El `vigilante_riesgo.py` solo CIERRA
> posiciones (2%/4% flotante) si operás manualmente.
> Las secciones de abajo (desktop PySide6, live/paper trading, ML gate, puente
> MQL5) describen el proyecto "SMC_SUCCESSOR" original y **NO están cableadas
> al flujo diario actual**. Están en el repo por si se activa el bot en el futuro.

**Smart Money Concepts trading system** — modular, event-driven, observador de análisis ICT/Wyckoff para prop firm (FundedNext) con app de escritorio PySide6 del observador, integración MetaTrader 5, análisis multi-agente y filtro ML.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![PySide6](https://img.shields.io/badge/PySide6-observador-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

---

## Features

| Area | Status | Description |
|------|--------|-------------|
| **App observador (UI)** | ✅ En construcción | `app_observador/` PySide6: semáforo FundedNext, sesgo + alineación Wyckoff D1/H4/M15, mapa ICT embebido, noticias rojas, black-box JSON 90d |
| **Paper / Live trading** | ✅ Production | `PaperTradingRunner` with agents, structural SL, ML gate, risk governor, kill switch |
| **Multi-agent analysis** | ✅ Production | ICT, Wyckoff (+ stochastic exhaustion), Structure, Decision Agent (weighted voting) |
| **ML quality filter** | ✅ Wired | XGBoost model gates trades in backtest, paper, live, and desktop UI |
| **ML training pipeline** | ✅ Offline | Dataset builder, chronological training, walk-forward, Optuna tuning, stats validation |
| **Backtest engine** | ✅ Production | Combined multi-symbol backtest with ML filter and governor |
| **Risk governor** | ✅ Production | NORMAL → CAUTION → DEFENSIVE → LOCKDOWN |
| **MT5 bridge + MQL5 EA** | ✅ Implemented | ZeroMQ bridge for live execution |
| **Monitoring & governance** | ⚠️ Harness-level | Drift baseline (PSI), model registry; scheduler runs via harness adapters |
| **Harness-first testing** | ✅ Production | 11 adapters, 14 scenarios |
| **LangGraph orchestration** | ✅ Implemented | Backtest validation graph |

### SMC concepts

Order Blocks (OB), Fair Value Gaps (FVG), displacement, premium/discount zones, BOS, CHOCH, liquidity sweeps, multi-timeframe trend (D1/H4/LTF).

---

## Architecture

```
MT5 Terminal (live) / Parquet (historical)
    │
    ▼
build_scalping_context()
    │ detectors: BOS, CHOCH, FVG, OB, displacement, zones
    │ indicators: EMA, RSI, Stochastic, ATR
    │ trend_context: D1 / H4 / LTF alignment
    │
    ▼
AgentOrchestrator (when ML or agents enabled)
    │ ICTAgent ────┐
    │ WyckoffAgent ─┤ (+ stochastic exhaustion)
    │ StructureAgent┘
    │ DecisionAgent → weighted voting
    │
    ▼
Confluence scoring → signal confidence → regime-based threshold
    │
    ▼
QualityFilter (ml/inference.py) — XGBoost predict_proba gate
    │
    ▼
PaperTradingRunner (PAPER / LIVE) + Risk Governor
    │
    ▼
Desktop UI (PySide6) ← DataStreamer + TradingWorker
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- [MetaTrader 5](https://www.metatrader5.com/) terminal (build 4000+), logged in
- MT5 demo or live account

### Install

```bash
git clone https://github.com/vjack666/SMC-SYSTEMS.git
cd SMC-SYSTEMS
pip install -e .
```

Dependencies include `PySide6`, `MetaTrader5`, `xgboost`, `pyarrow`, `scipy`, `optuna`, `langgraph`.

### Run Observador UI (app_observador)

```bash
# Requiere MT5 abierto y PySide6 instalado
python app_observador/main.py
```

Ventana del observador: semáforo FundedNext, sesgo + alineación Wyckoff D1/H4/M15,
mapa ICT embebido, noticias rojas y estado del loop/vigilante. Refresca cada 5 min.
Black-box en `data/blackbox/` (JSON, retención 90 días).

### Run Paper Trading (headless) — bot heredado, NO usado en modo observador

```bash
python scripts/run_paper_trading.py --symbols EURUSD,GBPUSD --timeframe M15
python scripts/run_paper_trading.py --no-ml          # disable ML filter
python scripts/run_paper_trading.py --ml-model path/to/model.pkl
```

### Run Live Trading

```bash
python scripts/run_live_trading.py --symbols EURUSD,GBPUSD --risk 1.0 --min-confidence 0.7
python scripts/run_live_trading.py --no-ml
```

### Train / refresh ML model

```bash
python scripts/run_ml_pipeline.py
```

Pipeline steps: build v4 dataset from `data/raw` → chronological holdout training → save `ml/models/quality_filter.pkl` → integration checks. Progress is written to `results/ml_pipeline_status.json`. On completion prints `ML_PIPELINE_COMPLETE`.

---

## App Observador (app_observador)

Ventana PySide6 del observador (reemplaza el antiguo `desktop/` del bot):

| Panel | Contenido |
|-------|-----------|
| **Semáforo** | VERDE/AMARILLO/ROJO FundedNext + motivo |
| **Sesgo** | Sesgo del día + alineación Wyckoff D1/H4/M15 |
| **Mapa ICT** | Velas D1/H4/M15 con OB/FVG/Liquidez/Killzones (matplotlib embebido) |
| **Noticias** | Eventos rojos del día (news_report) |
| **Estado** | loop ON/OFF, vigilante ON/OFF, cuenta MT5, equity |

Black-box: `data/blackbox/app_AAAA-MM-DD.log` (JSON, rotación + retención 90 días).
Ver SDD en `docs/specs/app_observador.md`.

---

## ML Pipeline

### Modules (`ml/`)

| Module | Role |
|--------|------|
| `dataset_builder.py` | Builds labeled v4 parquets from real OHLCV via signal simulation |
| `trainer.py` | Train, save, load, `predict_proba`, chronological split |
| `inference.py` | `QualityFilter` — shared gate for backtest and live/paper |
| `walk_forward.py` | Date/index walk-forward with optional purged K-fold |
| `stats_validator.py` | CVaR, Deflated Sharpe, PBO, bootstrap CI |
| `tuner.py` | Optuna hyperparameter search |
| `validator.py` | Dataset schema and leakage checks |

### Production model

| Field | Value |
|-------|-------|
| Path | `ml/models/quality_filter.pkl` |
| Schema | v4 (67 features incl. agent columns) |
| Training samples | 1,649 (7 symbols, real data) |
| Holdout ROC-AUC | ~0.55 (chronological 80/20 split) |
| Backtest WR / PF / Sharpe | 63.7% / 1.61 / 3.33 (4-symbol combined) |

The ML filter is **conservative** — it rejects most candidate signals. Treat holdout AUC as modest; retrain with `run_ml_pipeline.py` as data grows.

### Where ML runs

| Context | Wired |
|---------|-------|
| `backtest/engine.py` | ✅ `use_ml_quality_filter` on `CombinedBacktestConfig` |
| `paper_trading/runner.py` | ✅ via `ScalpingConfig.use_ml_quality_filter` |
| `scripts/run_live_trading.py` | ✅ `--no-ml` flag |
| `app_observador/` | 🔧 En construcción (observador, reemplaza desktop/ del bot) |

---

## Entry Protocol (summary)

1. Session — London or New York (Asia optional for XAUUSD)
2. ATR filter — `atr_ratio ≥ min_atr_ratio`
3. Trend — macro direction + confidence threshold
4. BOS, OB/FVG proximity, CHOCH, swing, micro structure (EMA/RSI)
5. Confluence score ≥ 2
6. Signal confidence ≥ configured minimum
7. **ML quality filter** — `predict_proba ≥ dynamic regime threshold`
8. Risk governor — LOCKDOWN blocks all entries

**Execution:** structural SL (20-bar swing) with ATR fallback; TP at 2× ATR; max hold 16 bars.

Full checklist in [COMPLETION_REPORT.md](COMPLETION_REPORT.md).

---

## Data

- Parquet in `data/raw/` per symbol + timeframe (M15, H4, D1)
- ML datasets in `data/ml/` — per-symbol and `multi_symbol/v4_dataset.parquet`
- Auto-download from MT5 when files are missing or stale
- Symbols: EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, NZDUSD, USDCHF, XAUUSD

---

## Project Structure

```
SMC-SYSTEMS/
├── agents/             # ICT, Wyckoff, Structure, Decision + orchestrator
├── backtest/           # Combined backtest engine with ML gate
├── data/               # MT5 connector, raw parquets, ML datasets
├── app_observador/     # App PySide6 del observador (semáforo, mapa ICT, black-box)
├── detectors/          # BOS, CHOCH, FVG, OB, displacement, zones
├── features/           # FeatureEngine (30+ features for ML)
├── governance/         # Model registry, retraining scheduler
├── harness/            # Harness-first testing framework
├── integration/        # MT5 ZeroMQ bridge
├── ml/                 # Dataset, trainer, inference, walk-forward, tuner, stats
├── monitoring/         # Drift detection (PSI), alerts, telemetry
├── MQL5/               # MQL5 EA bridge
├── paper_trading/      # Runner (PAPER/LIVE), models, persistence
├── risk/               # Governor, sizer, dynamic thresholds
├── scripts/            # CLI entry points (see table below)
├── signals/            # Scalping pipeline + ScalpingConfig
├── tests/              # 21 pytest modules
└── docs/               # Architecture, rulebooks, deployment guide
```

### Key scripts

| Script | Purpose |
|--------|---------|
| `app_observador/main.py` | App observador (UI PySide6) |
| `run_paper_trading.py` | Headless paper loop |
| `run_live_trading.py` | Live / paper CLI runner |
| `run_ml_pipeline.py` | Full ML train + verify pipeline |
| `build_v4.py` | Build v4 ML dataset only |
| `walk_forward_quick.py` | Walk-forward report |
| `stats_validate.py` | Standalone statistical validation |

---

## Running Tests

```bash
pytest tests/ -v
```

ML-focused subset:

```bash
pytest tests/test_ml_inference.py tests/test_ml_stats_validator.py tests/test_ml_train.py -q
```

---

## Harness

```bash
python -m harness
```

11 registered adapters with 14 scenarios.

---

## Packaging

```bash
pip install pyinstaller
pyinstaller smc_trading.spec
```

Output: `dist/SMC_Trading.exe`. Requires MT5 on the target machine.

---

## Documentation

| Document | Description |
|----------|-------------|
| [COMPLETION_REPORT.md](COMPLETION_REPORT.md) | Pipeline wiring, backtest metrics, entry protocol |
| [Agent Architecture](docs/AGENT_ARCHITECTURE.md) | Agent system design |
| [App Observador](docs/specs/app_observador.md) | SDD de la UI del observador (reemplaza desktop/) |
| [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) | VPS, systemd, NSSM |
| [ICT Rulebook](docs/ICT_RULEBOOK.md) | ICT specifications |
| [Wyckoff Rulebook](docs/WYCKOFF_RULEBOOK.md) | Wyckoff specifications |
| [Roadmap](docs/CRONOGRAMA_Y_ROADMAP.md) | Prioritized work plan |

---

## Current Status (2026-07)

| Component | State |
|-----------|-------|
| Signal pipeline + agents | ✅ Complete |
| Backtest (4 symbols, ML) | ✅ WR 63.7%, PF 1.61, Sharpe 3.33, DD 4.96% |
| ML inference in trading loop | ✅ Complete |
| ML training pipeline | ✅ Complete (modest holdout AUC — retrain as data grows) |
| Desktop UI | ✅ Stable (main-thread chart, single instance) |
| Statistical validation (CVaR, DSR, PBO, bootstrap) | ✅ Implemented |
| Optuna tuning | ✅ Implemented |
| MT5 bridge + MQL5 EA | ✅ Implemented |
| Production monitoring in live loop | ⚠️ Drift baseline saved on train; live drift check not in runner yet |
| Deployment automation | ⚠️ Documented; not fully automated |

**Bottom line:** research, backtest, paper, and desktop trading paths are functional end-to-end with ML. Live deployment still requires operational hardening (monitoring in loop, VPS setup, model refresh cadence).