# SMC Successor

**Smart Money Concepts trading system** — modular, event-driven, with a full PySide6 desktop UI and MT5 integration.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.6%2B-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

---

## Features

- **Desktop UI** — real-time candlestick charts with EMA/Stochastic overlays, OB/FVG zones, signal markers, dark theme
- **Live Trading** — PAPER and LIVE modes via MT5, including margin validation, position sync, and kill switch
- **Multi-Agent Analysis** — ICT, Wyckoff, and Structure agents producing structured evidence for each bar
- **Risk Governor** — dynamic state machine (NORMAL → CAUTION → DEFENSIVE → LOCKDOWN) based on drawdown and consecutive losses
- **ML Tuning** — Optuna hyperparameter optimization with PurgedKFold cross-validation
- **Statistical Validation** — CVaR, Deflated Sharpe Ratio, Probability of Backtest Overfitting, bootstrap confidence intervals
- **Stochastic Exhaustion Detection** — divergence + volume confirmation for trend reversal signals
- **Concepts** — Order Blocks (OB) and Fair Value Gaps (FVG) with automatic zone detection and chart rendering
- **Harness-First Testing** — every module is introduced through its harness before production use

## Architecture

```
MT5 Data (live/parquet)
    |
    v
FeatureEngine / Context
    |
    +---> ICT Agent ──┐
    +---> Wyckoff Agent ──┤
    +---> Structure Agent ─┘
    |                   |
    v                   v
Decision Agent ───> Signal Confidence
    |
    v
Risk Governor ───> Trade Execution
    |
    v
PaperTradingRunner (PAPER / LIVE)
    |
    v
Desktop UI (PySide6) ←→ Worker QThread
```

## Quick Start

### Prerequisites

- Python 3.11+
- [MetaTrader 5](https://www.metatrader5.com/) terminal (build 4000+)
- MT5 demo or live account

### Install

```bash
git clone <repo-url>
cd smc-successor
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
smc-successor/
├── desktop/              # PySide6 UI panels
│   ├── main_window.py    # QMainWindow with tabs, tray, menu
│   ├── worker.py         # QThread worker bridging UI ↔ runner
│   ├── chart_widget.py   # Candlestick chart with indicators
│   ├── control_panel.py  # Start/Stop/Config
│   ├── dashboard_panel.py# Account info, prices, status
│   ├── position_panel.py # Open positions table
│   ├── trade_log_panel.py# Trade history with filter
│   ├── log_panel.py      # Real-time log viewer
│   ├── settings_dialog.py# 4-tab configuration dialog
│   └── models.py         # Qt table models
├── agents/               # ICT, Wyckoff, Structure, Decision
├── paper_trading/        # Runner, models, persistence
├── risk/                 # Governor state machine
├── signals/              # Signal pipeline
├── data/                 # MT5 connector, parquet data
├── ml/                   # Optuna tuner, stats validator
├── detectors/            # Displacement, zone detection
├── scripts/              # CLI entry points
├── tests/                # Pytest test suite
├── docs/                 # Documentation
│   ├── DEPLOYMENT_GUIDE.md
│   ├── AGENT_ARCHITECTURE.md
│   ├── ICT_RULEBOOK.md
│   ├── WYCKOFF_RULEBOOK.md
│   └── DESKTOP_UI.md
├── indicators.py         # Technical indicators
├── _data_legacy.py       # Parquet load with staleness check
└── smc_trading.spec      # PyInstaller spec
```

## Running Tests

```bash
pytest tests/ -v
```

## Documentation

| Document | Description |
|----------|-------------|
| [Desktop UI](docs/DESKTOP_UI.md) | Full desktop UI reference |
| [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) | VPS, systemd, NSSM, monitoring |
| [Agent Architecture](docs/AGENT_ARCHITECTURE.md) | Agent system design |
| [ICT Rulebook](docs/ICT_RULEBOOK.md) | ICT concept specifications |
| [Wyckoff Rulebook](docs/WYCKOFF_RULEBOOK.md) | Wyckoff concept specifications |

## Status

Phase 1 complete. Active development on the desktop UI and live trading pipeline.
