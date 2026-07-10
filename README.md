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

## 📌 Fuente de verdad del proyecto

**La única fuente de verdad para hitos, estado y roadmap es
[`docs/CRONOGRAMA_Y_ROADMAP.md`](docs/CRONOGRAMA_Y_ROADMAP.md) (v2.2, 2026-07-10).**
`docs/HOJA_DE_RUTA_SMC-SYSTEMS.md` quedó obsoleta y redirige al Cronograma.

---

## Features

| Area | Status | Description |
|------|--------|-------------|
| **App observador (UI)** | ✅ Producción | `app_observador/` PySide6: semáforo FundedNext, sesgo + alineación Wyckoff D1/H4/M15, mapa ICT embebido, noticias rojas, black-box JSON 90d |
| **Rutina EURUSD diaria** | ✅ Producción | `scripts/rutina_eurusd.py` + `scripts/loop_analisis.py` 24/7 (lun-vie) → ficha + informe + semáforo + alertas |
| **Arranque automático** | ✅ Producción | `start_hermes_session.ps1` abre MT5 FundedNext, baja datos en vivo, lanza loop + vigilante + observador, reporte de salud (Carpeta de Inicio) |
| **Vigilante de riesgo** | ✅ Producción | `scripts/vigilante_riesgo.py` SOLO CIERRA posiciones (2%/4% flotante) |
| **Edge Diagnosis (SMC puro)** | ✅ Completada | 21 variantes × 8 símbolos = 168 celdas, 0 errores. Mejor celda `no_session`×XAUUSD OOS PF 1.642 |
| **Multi-agent analysis** | ✅ Production | ICT, Wyckoff (+ stochastic exhaustion), Structure, Decision Agent (weighted voting) |
| **ML quality filter** | ✅ Wired | XGBoost model gates trades en backtest, paper, live, y desktop UI |
| **ML training pipeline** | ✅ Offline | Dataset builder, chronological training, walk-forward, Optuna tuning, stats validation |
| **Backtest engine** | ✅ Production | Combined multi-symbol backtest with ML filter and governor |
| **Risk governor** | ✅ Production | NORMAL → CAUTION → DEFENSIVE → LOCKDOWN |
| **MT5 bridge + MQL5 EA** | ✅ Implemented | ZeroMQ bridge for live execution (bot heredado, no usado en modo observador) |
| **Monitoring & governance** | ⚠️ Harness-level | Drift baseline (PSI), model registry; scheduler via harness adapters |
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
PaperTradingRunner (PAPER / LIVE) + Risk Governor   [bot heredado, NO en modo observador]
    │
    ▼
Desktop UI (PySide6) ← DataStreamer + TradingWorker
```

---

## Quick Start

### Prerequisites

- Python 3.11+ (se usa `C:\Python314\python.exe` con MT5 real; el venv `smc_probe` solo tiene stub de MT5 para backtests offline)
- [MetaTrader 5](https://www.metatrader5.com/) terminal (build 4000+), logged in a la cuenta FundedNext
- PySide6 instalado para la app del observador

### Install

```bash
git clone https://github.com/vjack666/SMC-SYSTEMS.git
cd SMC-SYSTEMS
pip install -e .
```

Dependencies include `PySide6`, `MetaTrader5`, `xgboost`, `pyarrow`, `scipy`, `optuna`, `langgraph`.

### Arranque automático diario (modo observador)

Al iniciar sesión en Windows se ejecuta `start_hermes_session.ps1` (vía `.lnk` en la
Carpeta de Inicio con Bypass). Hace:

1. Abre el terminal MT5 de FundedNext (si no está corriendo).
2. Baja datos EN VIVO a `data/raw/` (EURUSD D1/H4/M15).
3. Lanza `scripts/loop_analisis.py` (ficha + informe + alertas, 24/7 lun-vie).
4. Lanza `scripts/vigilante_riesgo.py` (solo cierra, 2%/4%).
5. Lanza `run_app.py` (observador PySide6).
6. Imprime reporte de salud (MT5 abierto, procesos vivos, estado git).

Para arrancar a mano:

```bat
start_hermes_session.ps1        # PowerShell (recomendado)
rem o bien:
start_all_session.bat
```

### Rutina EURUSD manual

```bat
C:\Python314\python.exe scripts\rutina_eurusd.py         # ver ficha
C:\Python314\python.exe scripts\rutina_eurusd.py --save  # guardar al diario (docs/diario/)
```

### Run Observador UI (app_observador)

```bash
python app_observador/main.py
```

Ventana del observador: semáforo FundedNext, sesgo + alineación Wyckoff D1/H4/M15,
mapa ICT embebido, noticias rojas y estado del loop/vigilante. Refresca cada 5 min.
Black-box en `data/blackbox/` (JSON, retención 90 días).

### Run Paper / Live Trading (bot heredado, NO usado en modo observador)

```bash
python scripts/run_paper_trading.py --symbols EURUSD,GBPUSD --timeframe M15
python scripts/run_live_trading.py --symbols EURUSD,GBPUSD --risk 1.0 --min-confidence 0.7
```

### Train / refresh ML model

```bash
python scripts/run_ml_pipeline.py
```

Pipeline steps: build v4 dataset from `data/raw` → chronological holdout training → save `ml/models/quality_filter.pkl` → integration checks. Progress in `results/ml_pipeline_status.json`. On completion prints `ML_PIPELINE_COMPLETE`.

---

## Edge Diagnosis (SMC puro, sin ML ni agentes)

Matriz **21 variantes × 8 símbolos = 168 celdas**, gobernador neutralizado.
Resultado (2026-07-10, ver [`docs/EDGE_DIAGNOSIS_REPORT.md`](docs/EDGE_DIAGNOSIS_REPORT.md)):

- Mejor variante promedio: `no_session` → **OOS PF 1.159**.
- Peor: `prox_1` → **OOS PF 1.084** (el filtro de proximidad OB/FVG erosiona el edge).
- Mejor símbolo: **XAUUSD OOS PF 1.376**; peor: AUDUSD (0.849) y NZDUSD (0.809) PIERDEN.
- Celda TOP: `no_session` × XAUUSD → **OOS PF 1.642, N=900, Sharpe 3.28, WR 55.1%**.
- **Próximo paso (pendiente A12):** walk-forward OOS real (PurgedKFold, DSR>0, N>=200/fold, PF>=1.10) de la celda ganadora antes de cualquier automatización.

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
├── app_observador/     # App PySide6 del observador (semáforo, mapa ICT, black-box)
├── backtest/           # Combined backtest engine with ML gate
├── data/               # MT5 connector, raw parquets, ML datasets
├── detectors/          # BOS, CHOCH, FVG, OB, displacement, zones
├── docs/               # CRONOGRAMA_Y_ROADMAP.md (fuente de verdad) + rulebooks
├── features/           # FeatureEngine (30+ features for ML)
├── governance/         # Model registry, retraining scheduler
├── harness/            # Harness-first testing framework
├── integration/        # MT5 ZeroMQ bridge
├── ml/                 # Dataset, trainer, inference, walk-forward, tuner, stats
├── monitoring/         # Drift detection (PSI), alerts, telemetry
├── MQL5/               # MQL5 EA bridge
├── paper_trading/      # Runner (PAPER/LIVE), models, persistence
├── risk/               # Governor, sizer, dynamic thresholds
├── scripts/            # CLI entry points (loop_analisis, rutina_eurusd, etc.)
├── signals/            # Scalping pipeline + ScalpingConfig
├── tests/              # pytest modules
└── tools/              # fundednext_compliance.py (reglas Stellar Lite $5K)
```

### Key scripts

| Script | Purpose |
|--------|---------|
| `start_hermes_session.ps1` | Arranque automático diario (MT5 + datos + loop + vigilante + observador) |
| `app_observador/main.py` | App observador (UI PySide6) |
| `scripts/loop_analisis.py` | Loop de análisis 24/7 (observador) |
| `scripts/rutina_eurusd.py` | Ficha top-down EURUSD D1/H4/M15 |
| `scripts/vigilante_riesgo.py` | Cierra posiciones manuales al 2%/4% flotante |
| `run_paper_trading.py` | Headless paper loop (bot heredado) |
| `run_live_trading.py` | Live / paper CLI runner (bot heredado) |
| `run_ml_pipeline.py` | Full ML train + verify pipeline |
| `scripts/edge_diagnosis/run.py` | Edge diagnosis 21×8 (SMC puro) |

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
| [CRONOGRAMA_Y_ROADMAP.md](docs/CRONOGRAMA_Y_ROADMAP.md) | **ÚNICA fuente de verdad** — hitos y estado (v2.2) |
| [COMPLETION_REPORT.md](COMPLETION_REPORT.md) | Pipeline wiring, backtest metrics, entry protocol |
| [EDGE_DIAGNOSIS_REPORT.md](docs/EDGE_DIAGNOSIS_REPORT.md) | Resultado edge diagnosis 21×8 (2026-07-10) |
| [ESTADO_ACTUAL.md](docs/ESTADO_ACTUAL.md) | Estado edge diagnosis cerrada |
| [RUTINA_EURUSD.md](docs/RUTINA_EURUSD.md) | Manual de uso diario de la rutina EURUSD |
| [AUDITORIA_USO_2026-07-09.md](docs/AUDITORIA_USO_2026-07-09.md) | Cadena real de uso de la rutina vs código bot heredado |
| [Agent Architecture](docs/AGENT_ARCHITECTURE.md) | Agent system design |
| [App Observador](docs/specs/app_observador.md) | SDD de la UI del observador |
| [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) | VPS, systemd, NSSM (pendiente A8) |
| [ICT Rulebook](docs/ICT_RULEBOOK.md) | ICT specifications |
| [Biblioteca ICT](docs/ict/00_INDICE.md) | Libros por concepto |
| [Wyckoff Rulebook](docs/WYCKOFF_RULEBOOK.md) | Wyckoff specifications |

---

## Current Status (2026-07-10)

| Component | State |
|-----------|-------|
| Observador FundedNext (loop 24/7) | ✅ Producción |
| Arranque automático (PowerShell + Inicio) | ✅ Producción |
| Rutina EURUSD + diario | ✅ Producción |
| Edge Diagnosis (SMC puro, 168 celdas) | ✅ Completada |
| Signal pipeline + agents | ✅ Complete |
| Backtest (4 symbols, ML) | ✅ WR 63.7%, PF 1.61, Sharpe 3.33, DD 4.96% |
| ML inference in trading loop | ✅ Complete |
| ML training pipeline | ✅ Complete (modest holdout AUC — retrain as data grows) |
| Desktop UI | ✅ Stable (main-thread chart, single instance) |
| Statistical validation (CVaR, DSR, PBO, bootstrap) | ✅ Implemented |
| Optuna tuning | ✅ Implemented |
| MT5 bridge + MQL5 EA | ✅ Implemented (bot heredado) |
| Walk-forward OOS celda ganadora | ⚠️ Pendiente (A12) |
| Production monitoring in live loop | ⚠️ Drift baseline saved on train; live drift check not in runner yet |
| Deployment automation | ⚠️ Documented (A8); not fully automated |

**Bottom line:** research, backtest, edge-diagnosis, paper, and desktop trading paths are functional end-to-end with ML. Live deployment still requires operational hardening (walk-forward OOS validation, monitoring in loop, VPS setup, model refresh cadence).
