# SMC-SYSTEMS

**Smart Money Concepts trading system** — modular, event-driven, with a full PySide6 desktop UI, MT5 integration, and ML-powered validation.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.6%2B-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

---

## Features

- **Desktop UI** — real-time candlestick charts with EMA/Stochastic overlays, OB/FVG zones, signal markers, dark theme (6 tabs)
- **Live Trading** — PAPER and LIVE modes via MT5 + ZeroMQ bridge + MQL5 EA, margin validation, position sync, kill switch
- **Multi-Agent Analysis** — ICT, Wyckoff, and Structure agents + Decision Agent with weighted voting
- **Stochastic Exhaustion Detection** — divergence + volume confirmation, integrated in Wyckoff agent
- **Risk Governor** — dynamic state machine (NORMAL → CAUTION → DEFENSIVE → LOCKDOWN) based on drawdown and consecutive losses
- **ML Pipeline** — XGBoost quality filter, walk-forward validation, dataset builder
- **Statistical Validation** — CVaR, Deflated Sharpe Ratio, Probability of Backtest Overfitting, bootstrap confidence intervals (planned)
- **Concepts** — Order Blocks (OB), Fair Value Gaps (FVG), displacement, zones, BOS, CHOCH, liquidity sweeps
- **Production Monitoring** — drift detection (PSI), equity telemetry, alerting, performance dashboard
- **Model Governance** — model registry with versioning, retraining scheduler, auto-report generation
- **Harness-First Testing** — every module is introduced through its harness before production use (11 adapters, 14 scenarios)
- **LangGraph Orchestration** — backtest validation graph with 7 nodes and conditional routing

## Architecture

```
MT5 Terminal (live) / Parquet (historical)
    │
    ▼
build_scalping_context()
    │ detectors: BOS, CHOCH, FVG, OB, displacement, zones, trend
    │ indicators: EMA, RSI, Stochastic, ATR
    │ trend_context: multi-timeframe D1/H4/LTF
    │
    ▼
AgentOrchestrator
    │ ICTAgent ────┐
    │ WyckoffAgent ─┤ (+ stochastic exhaustion)
    │ StructureAgent─┘
    │ DecisionAgent → weighted voting
    │
    ▼
Confluence scoring → Signal confidence → GovernorPool
    │
    ▼
PaperTradingRunner (PAPER / LIVE via MT5 Bridge + MQL5 EA)
    │
    ▼
Desktop UI (PySide6) ←→ Worker QThread
    │
    ▼
Monitoring (drift, alerts, telemetry) + Governance (registry, retraining)
```

## Quick Start

### Prerequisites

- Python 3.11+
- [MetaTrader 5](https://www.metatrader5.com/) terminal (build 4000+)
- MT5 demo or live account

### Install

```bash
git clone <repo-url>
cd SMC-SYSTEMS
pip install -e .
```

### Run Desktop UI

```bash
python scripts/run_desktop.py
```

### Run Paper Trading (headless)

```bash
python scripts/run_paper_trading.py --symbols EURUSD,GBPUSD --timeframe M15
```

### Run Live Trading

```bash
python scripts/run_live_trading.py --symbols EURUSD,GBPUSD --risk 1.0 --min-confidence 0.7
```

## Desktop UI

6-tab interface with dark Fusion theme:

| Tab       | Content |
|-----------|---------|
| Dashboard | Account info, live prices with RSI/Stoch status, system status with governor color coding |
| Chart     | Candlestick chart with EMA20/50, Stoch %K/%D, signal markers, OB/FVG zones, symbol selector |
| Positions | Open positions table with P&L and pips |
| Trade Log | Historical trades with filter by symbol |
| Log       | Real-time log output (auto-scroll, 10k line cap) |
| Control   | Start/Stop/Emergency Stop, risk % and min confidence spinboxes, symbol input |

See [docs/DESKTOP_UI.md](docs/DESKTOP_UI.md) for details.

## Indicators

All in `indicators.py`:

| Function | Description |
|----------|-------------|
| `add_ema()` | Exponential Moving Average |
| `add_rsi()` | Relative Strength Index |
| `add_stochastic()` | Stochastic Oscillator with %K/%D/smoothed |
| `add_atr()` | Average True Range |
| `add_order_blocks()` | Detects bullish/bearish OBs (last candle before 3+ consecutive moves) |
| `add_fvg()` | Detects Fair Value Gaps with filled/unfilled state tracking |

## Data

- Parquet files in `data/raw/` for each symbol+timeframe
- Auto-download from MT5 when files are missing or stale
- Staleness thresholds: M1=30m, M5=1h, M15=2h, M30=4h, H1=6h, H4=12h, D1=48h
- Supported symbols: EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, NZDUSD, USDCHF, XAUUSD

## Packaging

Build a standalone Windows executable with PyInstaller:

```bash
pip install pyinstaller
pyinstaller smc_trading.spec
```

Output: `dist/SMC_Trading.exe` (~480 MB). Requires MT5 terminal on the target machine.

## Project Structure

```
SMC-SYSTEMS/
├── agents/             # ICT, Wyckoff, Structure, Decision agents + orchestrator
├── adapters/           # Harness adapters (signal, risk, backtest, MT5, etc.)
├── backtest/           # Backtest engine + validation (MT5 comparison, report generator)
├── data/               # MT5 connector, parquet raw data, ML datasets
├── desktop/            # PySide6 UI (main_window, chart, control, dashboard, positions, etc.)
├── detectors/          # BOS, CHOCH, FVG, OB, displacement, zones, trend
├── features/           # Feature engineering engine (30+ features)
├── fixtures/           # Test fixtures (synthetic OHLCV)
├── governance/         # Model registry, retraining scheduler, auto-report generator
├── harness/            # Harness-first testing (runners, scenarios, validators, fixtures, reports)
├── integration/        # MT5 ZeroMQ bridge (exporter, receiver, orchestrator, schema)
├── ml/                 # ML pipeline (trainer, validator, walk_forward, tuner, stats_validator)
├── models/             # Production model artifacts
├── monitoring/         # Drift detection (PSI), alerting, equity telemetry, dashboard
├── MQL5/               # MQL5 EA bridge (compiled .ex5 + source)
├── orchestration/      # LangGraph backtest validation graph + harness adapter
├── paper_trading/      # Runner, models, persistence
├── results/            # Backtest metrics, equity curves, trade CSVs
├── risk/               # Risk governor state machine, sizer, thresholds
├── scripts/            # CLI entry points (run_desktop, run_paper_trading, run_live, etc.)
├── signals/            # Signal pipeline (confluence scoring, filters)
├── tests/              # 19 pytest test files
├── docs/               # Documentation
│   ├── AGENT_ARCHITECTURE.md
│   ├── CRONOGRAMA_Y_ROADMAP.md
│   ├── DEPLOYMENT_GUIDE.md
│   ├── DESKTOP_UI.md
│   ├── HOJA_DE_RUTA_SMC-SYSTEMS.md
│   ├── ICT_RULEBOOK.md
│   └── WYCKOFF_RULEBOOK.md
├── indicators.py       # Technical indicators
├── regime.py           # Market regime classifier
├── trend_context.py    # Multi-timeframe trend context
├── _data_legacy.py     # Parquet load with staleness check
├── _progress.py        # Progress tracker
└── smc_trading.spec    # PyInstaller spec
```

## Running Tests

```bash
pytest tests/ -v
```

## Harness

```bash
python -m harness
```

11 registered adapters with 14 scenarios across all modules.

## Documentation

| Document | Description |
|----------|-------------|
| [Roadmap y Cronograma](docs/CRONOGRAMA_Y_ROADMAP.md) | Plan de trabajo priorizado |
| [Hoja de Ruta](docs/HOJA_DE_RUTA_SMC-SYSTEMS.md) | Visión, principios, hitos |
| [Agent Architecture](docs/AGENT_ARCHITECTURE.md) | Agent system design |
| [Desktop UI](docs/DESKTOP_UI.md) | Full desktop UI reference |
| [ICT Rulebook](docs/ICT_RULEBOOK.md) | ICT concept specifications |
| [Wyckoff Rulebook](docs/WYCKOFF_RULEBOOK.md) | Wyckoff concept specifications |
| [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) | VPS, systemd, NSSM, monitoring (pending) |

## Status

- **Core pipeline & UI**: ✅ Complete
- **ML, backtest, entry protocol**: ✅ Complete (WR 63.74%, PF 1.61, Sharpe 3.33, DD 4.96%)
- **MT5 bridge & MQL5 EA**: ✅ Complete
- **Production monitoring & governance**: ✅ Complete
- **Stochastic exhaustion detection**: ✅ Implemented in Wyckoff agent
- **Parameter tuning (Optuna)**: ⬜ Pending
- **Robust validation (PurgedKFold, CVaR, DSR, PBO)**: ⬜ Pending
- **Deployment guide (F8)**: ⬜ Postponed — last priority

Overall: ~75% toward production-ready.
