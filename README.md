<div align="center">
  <h1>SMC SYSTEMS</h1>
  <p><em>Algorithmic Trading Framework — Smart Money Concepts + Wyckoff + PAC State Machine</em></p>
  <p>
    <a href="#architecture">Architecture</a> •
    <a href="#quick-start">Quick Start</a> •
    <a href="#backtest-results">Backtest Results</a> •
    <a href="#key-modules">Key Modules</a> •
    <a href="#project-structure">Structure</a>
  </p>
</div>

---

SMC SYSTEMS es un framework de trading algorítmico que implementa **Smart Money Concepts (ICT)**, **Wyckoff Method** y un **PAC State Machine** (Price Action Confirmation) para generar señales de scalping en forex y metales preciosos.

Combina detección de estructuras de mercado (BOS, FVG, CHOCH, Order Blocks), análisis multi-timeframe, fases Wyckoff, y un sistema de risk management adaptativo.

---

## Architecture

```
Market Data (MT5 Parquet)
        │
        ▼
  build_scalping_context()
    ├── BOS, CHOCH, FVG, OB detection
    ├── Trend context (D1/H4/M15)
    ├── Stochastic Exhaustion
    ├── Wyckoff phases (Accumulation → Distribution)
    ├── PAC State Machine (FVG→Mitigation→BOS→Entry)
    └── Structural Stop Loss
        │
        ▼
  Confluence Scorer (regime-adaptive weights)
        │
        ▼
  Risk Governor + ML Quality Filter
        │
        ▼
  Backtest → Results
```

### Pipeline Flow

```
OHLC → Indicators → Structures → Regime → Trend → 
  Wyckoff → PAC → Filters → Confluence Score → 
  Signal → Risk Gate → Trade
```

---

## Quick Start

```bash
git clone https://github.com/vjack666/SMC-SYSTEMS.git
cd SMC-SYSTEMS
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Run Backtest

```python
from backtest.combined_backtest import run_combined_backtest, CombinedBacktestConfig
from pathlib import Path

cfg = CombinedBacktestConfig(
    data_dir=Path("data/mt5"),
    symbols=("EURUSD", "GBPUSD", "XAUUSD"),
    min_confidence=0.52,
    use_ml_quality_filter=False,
)
metrics, trades = run_combined_backtest(cfg)
```

### Debug Signal Pipeline

```bash
python scripts/debug_signal_pipeline.py
```

---

## Backtest Results

### Latest (10k bars, TP=3R, 3 symbols, Jun 2026)

| Metric | Value |
|--------|-------|
| Trades | 11 |
| Win Rate | 27.3% |
| Profit Factor | **1.258** |
| Expectancy | +0.168R |
| Sharpe | 1.45 |
| Max DD | -4.16R |

### Per Direction

| Direction | Trades | WR | PF | EV(R) |
|-----------|--------|----|----|-------|
| LONG | 1 | 0% | 0.0 | -0.16 |
| SHORT | 10 | 30% | 1.286 | +0.20 |

---

## Key Modules

| Module | Purpose |
|--------|---------|
| **`modules/bos/`** | Break of Structure detection |
| **`modules/fvg/`** | Fair Value Gap detection (3-candle gaps) |
| **`modules/choch/`** | Change of Character (structure flips) |
| **`modules/ob/`** | Order Block detection |
| **`modules/trend/`** | Multi-timeframe trend + ML confidence |
| **`modules/wyckoff/`** | Full Wyckoff cycle (accumulation → distribution) |
| **`modules/structural_sl/`** | ICT-origin swing stop loss |
| **`modules/indicators/`** | ATR, RSI, EMA |
| **`pac_sequence/`** | PAC state machine (FVG→Entry) |
| **`strategy/`** | Confluence scorer, signal generation |
| **`ml/`** | Feature pipeline, XGBoost quality filter |
| **`risk/`** | Dynamic thresholds, meta risk governor |
| **`backtest/`** | Multi-symbol backtest engine |

### Wyckoff Integration

El detector Wyckoff cubre el ciclo completo:

| Fase | Eventos | Uso en pipeline |
|------|---------|----------------|
| **Accumulation** | SC → AR → ST → Spring → SOS → LPS | Exhaustion signal para LONG entries |
| **Markup** | HH/HL swing sequence | Filtro de fase alcista |
| **Distribution** | UT → SOW → LPSY | Exhaustion signal para SHORT entries |
| **Markdown** | LH/LL swing sequence | Filtro de fase bajista |

### Filters Applied (ordered by selectivity)

| Filter | % Pass (EURUSD 10k) | Config |
|--------|--------------------|--------|
| `filter_swing` | 69.2% | Max 1.5 ATR from nearest swing |
| `filter_atr` | 51.4% | ATR ratio > 1.0 |
| `filter_session` | 41.7% | London + New York |
| `filter_ob_fvg` | 3.6% | Max 1.5 ATR from OB/FVG |
| `filter_choch` | 3.7% | No opposite CHOCH in 10 bars |
| `filter_bos` | 2.3% | BOS aligned with macro direction |
| `filter_trend` | 2.1% | Macro direction + confidence ≥ 0.45 |
| `filter_exhaustion` | 2.1% | Wyckoff or stochastic exhaustion |
| `filter_wyckoff` | 1.4% | Phase aligned with macro direction |

---

## Project Structure

```
SMC SYSTEMS/
├── backtest/              # Backtest engine
├── data/mt5/              # OHLCV parquet cache
├── ml/                    # Feature pipeline + model training
├── modules/               # Core detection modules
│   ├── bos/               # Break of Structure
│   ├── fvg/               # Fair Value Gap
│   ├── choch/             # Change of Character
│   ├── ob/                # Order Block
│   ├── trend/             # Multi-timeframe trend
│   ├── wyckoff/           # Wyckoff cycle detector
│   ├── structural_sl/     # Structural stop loss
│   ├── indicators/        # ATR, RSI, EMA
│   └── ...
├── pac_sequence/          # PAC state machine
├── risk/                  # Risk management
├── strategy/              # Signal generation
├── scripts/               # Debug + analysis scripts
├── results/               # Backtest outputs
├── agent/                 # Session documentation
└── knowledge/             # KOS research + learnings
```

---

## Related

- [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md) — full technical documentation
- [LEGACY_AUDIT_REPORT.md](./LEGACY_AUDIT_REPORT.md) — initial audit findings
- [agent/](./agent/) — session state and task tracking

---

<div align="center">
  <sub>Built with Python 3.11 · MetaTrader 5 · XGBoost · scikit-learn · pandas</sub>
</div>
