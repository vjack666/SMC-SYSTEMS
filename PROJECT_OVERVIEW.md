# SMC SYSTEMS - Project Comprehensive Overview

**Project Date**: June 2026  
**Purpose**: SMC (Smart Market Context) - An algorithmic trading system using ICT principles (Smart Money Concepts), Fair Value Gaps, Break of Structure, and Order Blocks for forex and precious metals trading.

---

## 1. Directory Structure & Purpose

```
SMC SYSTEMS/
├── backtest/                    # Backtesting framework for strategy validation
│   ├── combined_backtest.py     # Main backtest orchestrator (M15 multi-symbol)
│   ├── trend_backtest.py        # Trend-only backtest module
│   ├── bos_backtest.py          # Break of Structure (BOS) backtest
│   ├── fvg_mitigation_backtest.py # Fair Value Gap (FVG) mitigation variant
│   ├── fvg_pac_experiments.py   # PAC (Price Action Confirmation) + FVG experiments
│   └── retrain_models.py        # ML model retraining pipeline
│
├── data/                        # Market data and data infrastructure
│   └── mt5/
│       ├── downloader.py        # MetaTrader 5 OHLCV data fetcher
│       └── [SYMBOL]_[TF].parquet # Cached data (EURUSD, GBPUSD, XAUUSD @ M15/H1/H4/D1)
│
├── ml/                          # Machine Learning for trade quality filtering
│   ├── feature_pipeline.py      # Feature engineering and schema validation
│   ├── train_quality_model.py   # XGBoost/LightGBM quality filter training
│   ├── regime_detector.py       # Market regime classification (TRENDING/RANGING/etc)
│   ├── features_schema.json     # ML feature definitions
│   ├── model_metrics.json       # Model performance metadata
│   └── models/
│       └── quality_filter.pkl   # Trained scikit-learn model
│
├── modules/                     # Core trading logic modules (reusable)
│   ├── trend/                   # Multi-timeframe trend detection
│   │   ├── detector.py          # Trend signal generation
│   │   ├── ml_model.py          # Trend ML confidence scoring
│   │   ├── context_engine.py    # Build context frame with indicators
│   │   ├── mtf_analyzer.py      # Multi-timeframe analysis (D1/H4/M15)
│   │   ├── structure_classifier.py # Identify trend structure
│   │   ├── session_filter.py    # Trading session filtering
│   │   ├── swing_detector.py    # Swing point detection
│   │   ├── data_loader.py       # Symbol/TF data loading
│   │   ├── backtest.py          # Trend backtest harness
│   │   └── backtest_impl.py     # Trend backtest implementation
│   │
│   ├── bos/                     # Break of Structure detection
│   │   ├── detector.py          # BOS signal generation
│   │   ├── ml_model.py          # BOS strength/quality scoring
│   │   ├── data_loader.py       # BOS data utilities
│   │   ├── backtest.py          # BOS backtest harness
│   │   └── README.md            # BOS module documentation
│   │
│   ├── fvg/                     # Fair Value Gap detection
│   │   ├── detector.py          # FVG signal (3-candle gaps)
│   │   ├── ml_model.py          # FVG quality/size scoring
│   │   ├── backtest.py          # FVG backtest harness
│   │   └── README.md            # FVG module documentation
│   │
│   ├── choch/                   # Change of Character (structure flip)
│   │   ├── detector.py          # CHOCH signal generation
│   │   ├── ml_model.py          # CHOCH confidence scoring
│   │   ├── backtest.py          # CHOCH backtest harness
│   │   └── README.md            # CHOCH documentation
│   │
│   ├── ob/                      # Order Block detection
│   │   ├── detector.py          # OB signal generation
│   │   ├── ml_model.py          # OB quality scoring
│   │   ├── backtest.py          # OB backtest harness
│   │   ├── models/              # Pre-trained OB models
│   │   └── README.md            # OB documentation
│   │
│   ├── swing/                   # Swing point detection
│   │   ├── detector.py          # Swing high/low identification
│   │   ├── swing_detector.py    # Alternative swing algorithm
│   │   ├── ml_model.py          # Swing quality scoring
│   │   ├── backtest.py          # Swing backtest harness
│   │   └── README.md            # Swing documentation
│   │
│   ├── structural_sl/           # Structural Stop Loss calculation
│   │   ├── detector.py          # Origin swing + structural SL detection
│   │   ├── backtest.py          # Structural SL backtest harness
│   │   └── __init__.py          # Module exports
│   │
│   ├── indicators/              # Technical indicators
│   │   ├── core.py              # ATR, RSI, EMA calculations
│   │   └── ml_model.py          # Indicator quality scoring
│   │
│   ├── pullback/                # Pullback (retracement) detection
│   │   └── view.py              # Pullback visualization/analysis
│   │
│   └── fractal/                 # Fractal pattern detection
│       ├── detector.py          # Fractal signal generation
│       ├── fractal_detector.py  # Alternative fractal algorithm
│       ├── ml_model.py          # Fractal quality scoring
│       ├── backtest.py          # Fractal backtest harness
│       └── README.md            # Fractal documentation
│
├── pac_sequence/                # PAC State Machine for entry sequencing
│   ├── state_machine.py         # FVG→Mitigation→Entry state transitions
│   ├── feature_builder.py       # Build features from PAC events
│   ├── event_schema.py          # Define PAC event structures
│   ├── validation.py            # Validate PAC sequences
│   └── __init__.py              # Module exports
│
├── risk/                        # Risk management framework
│   ├── dynamic_threshold_engine.py # Regime-based dynamic thresholds
│   ├── meta_risk_governor.py    # NORMAL/CAUTION/DEFENSIVE/LOCKDOWN modes
│   └── __init__.py              # Module exports
│
├── strategy/                    # Strategy entry/exit logic
│   └── scalping_setup.py        # Scalping signal generation with filters
│
├── scripts/                     # Utility and experimental scripts (33 scripts)
│   ├── rebuild_experiment_f_structural.py  # Phase 4&5: Full rebuild from raw OHLC
│   ├── rebuild_experiment_f_fixed.py       # Fixed variant of Experiment F
│   ├── run_forward_validation.py           # Out-of-sample forward test
│   ├── run_fvg_mitigation_backtest.py      # FVG mitigation sensitivity tests
│   ├── run_risk_funding_analysis.py        # Funding/capital allocation analysis
│   ├── run_forensic_analytics.py           # Trade-level forensic audit
│   ├── generate_comparison.py              # E vs Broken-F vs Fixed-F report
│   ├── generate_edge_report.py             # Edge decomposition analysis
│   ├── audit_experiment_f_structural.py    # Structural SL validation audit
│   ├── train_fvg_only.py                   # FVG-only model training
│   ├── train_trend_lower_tf.py             # Lower timeframe trend training
│   ├── paper_trading_*.py                  # Paper trading monitoring
│   ├── forward_validation_*.py             # Forward validation reporting
│   ├── plot_*.py                           # Chart generation
│   └── [28 more audit, analysis, setup scripts]
│
├── paper_trading/               # Paper trading configuration & logs
│   ├── config.json              # Trading parameters (capital, risk %, symbols)
│   ├── status.json              # Real-time trading status
│   ├── data/                    # Intraday execution logs
│   ├── logs/                    # Detailed trade logs
│   └── reports/                 # Performance reports
│
├── results/                     # Backtest outputs (CSVs, JSONs, reports)
│   ├── experiment_*.csv         # Experiment trade logs (A-F)
│   ├── experiment_*_metrics.json # Experiment performance metrics
│   ├── combined_trades.csv      # Master trade dataset
│   ├── combined_metrics.json    # System-wide performance
│   ├── *_robustness_audit.md    # Robustness audit reports
│   ├── forensic_*.csv           # Forensic analysis datasets
│   ├── forensic_report.md       # Trade-level forensic analysis
│   ├── drawdown_*.csv           # Drawdown analysis
│   ├── expectancy_report.csv    # Edge/expectancy analysis
│   ├── [90+ result files]
│   └── forensic_f/              # Deep forensic analysis of Experiment F
│
├── run_system.py                # Main orchestrator - runs full pipeline
├── requirements.txt             # Python dependencies
├── PROJECT_OVERVIEW.md          # This file
└── .venv/                       # Python virtual environment

```

---

## 2. Key Python Modules & Architecture

### **Core Trading Modules** (under `/modules/`)

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| **trend/** | Multi-timeframe trend detection & ML confidence | `get_trend_signal()`, `analyze_mtf()` |
| **bos/** | Break of Structure (liquidity sweep + followthrough) | `detect_bos()` |
| **fvg/** | Fair Value Gap (3-candle gaps) | `detect_fvg()` |
| **choch/** | Change of Character (structure invalidation) | `detect_choch()` |
| **ob/** | Order Block (support/resistance zones) | `detect_order_blocks()` |
| **swing/** | Swing point detection (highs/lows) | `detect_swings()` |
| **structural_sl/** | Structural Stop Loss (origin swing placement) | `detect_origin_swing()`, `detect_liquidity_sweep()` |
| **indicators/** | Technical indicators | `add_atr()`, `add_ema()`, `add_rsi()` |
| **pullback/** | Pullback/retracement analysis | Pullback detection logic |
| **fractal/** | Fractal pattern recognition | `detect_fractals()` |

### **ML Pipeline** (under `/ml/`)

| Component | Purpose |
|-----------|---------|
| **feature_pipeline.py** | Transforms trade context → 30+ features (numeric + categorical) |
| **train_quality_model.py** | Trains XGBoost/LightGBM classifier on trade outcomes |
| **regime_detector.py** | Classifies market regime (TRENDING/RANGING/HIGH_VOL/CHAOTIC) |
| **quality_filter.pkl** | Pre-trained model for trade quality probability |

### **Risk Management** (under `/risk/`)

| Component | Purpose |
|-----------|---------|
| **dynamic_threshold_engine.py** | Adjusts entry thresholds by market regime |
| **meta_risk_governor.py** | Risk state machine (NORMAL→CAUTION→DEFENSIVE→LOCKDOWN) |

### **Strategy Logic** (under `/strategy/`, `/pac_sequence/`)

| Component | Purpose |
|-----------|---------|
| **scalping_setup.py** | Main entry signal logic + confluence scoring |
| **state_machine.py** | PAC sequence: FVG→Mitigation→Entry states |
| **validation.py** | Validates PAC sequences for correctness |

---

## 3. Script Analysis

### **Rebuild/Experiment Scripts** (Core Workflow)
- **rebuild_experiment_f_structural.py** - Full pipeline rebuild from raw OHLC
- **rebuild_experiment_f_fixed.py** - Fixed variant with corrections
- Result: `experiment_F_structural_sl.csv` + `experiment_F_structural_sl_metrics.json`

### **Validation & Audit Scripts**
- **run_forward_validation.py** - Out-of-sample validation (forward data)
- **run_forensic_analytics.py** - Trade-level forensic audit
- **audit_experiment_f_structural.py** - Validates structural SL calculations
- **generate_comparison.py** - Compare experiments (E vs F-broken vs F-fixed)

### **ML & Training Scripts**
- **train_fvg_only.py** - Train model on FVG-only setup
- **train_trend_lower_tf.py** - Train trend detection on lower timeframes
- **run_risk_funding_analysis.py** - Funding/Masaniello capital allocation

### **Paper Trading & Monitoring**
- **paper_trading_setup.py** - Initialize paper trading environment
- **paper_trading_logger.py** - Log real-time trades
- **paper_trading_drift_monitor.py** - Monitor model drift vs backtest
- **paper_trading_funding_simulator.py** - Simulate funding milestones

### **Analysis & Reporting**
- **generate_edge_report.py** - Decompose edge by symbol/regime/session
- **generate_fvg_setup_gallery.py** - Visualize FVG setups
- **plot_last_backtest_trade.py** - Chart recent trade
- **run_e_robustness_audit.py** - Test experiment E robustness

---

## 4. Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MARKET DATA INGESTION                        │
├─────────────────────────────────────────────────────────────────┤
│  MetaTrader 5 Terminal  →  downloader.py  →  OHLCV Parquet     │
│  (EURUSD, GBPUSD, XAUUSD @ M15/H1/H4/D1)                        │
│  Data retention: 2+ years per symbol/timeframe                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   FEATURE ENGINEERING LAYER                      │
├─────────────────────────────────────────────────────────────────┤
│  1. Load OHLC data for [M15 primary, H1, H4, D1]                │
│  2. Calculate indicators: ATR, RSI, EMA (fast/slow)              │
│  3. Detect structures: BOS, FVG, CHOCH, OB, Swings              │
│  4. Classify regime: Trending/Ranging/HighVol/LowVol/Chaotic    │
│  5. Detect trend signal (MTF analysis + ML confidence)           │
│  6. Build PAC sequence (state machine transitions)               │
│  7. Calculate structural stops (origin swing placement)          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   SIGNAL GENERATION (M15)                        │
├─────────────────────────────────────────────────────────────────┤
│  Signal = Trend + BOS + FVG + MTF Alignment + Session Filter    │
│  Signal Confidence = ML(trend, confluence factors)               │
│  Entry = FVG mitigation price                                    │
│  SL = Structural stop (origin swing)                             │
│  TP = 2:1 Risk/Reward ratio                                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   TRADE QUALITY FILTERING                        │
├─────────────────────────────────────────────────────────────────┤
│  Input: Signal context frame (30+ features)                      │
│  Model: XGBoost quality_filter.pkl                               │
│  Output: Quality probability (0.0-1.0)                           │
│  Filter: Only trade if probability >= min_threshold (0.60)       │
│  Risk Adjustment: Dynamic threshold per regime                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   POSITION MANAGEMENT                            │
├─────────────────────────────────────────────────────────────────┤
│  Limit: max 16 bars hold (for scalping)                          │
│  Exits: SL hit / TP hit / Hold limit                             │
│  Track: MFE (Max Favorable Excursion) & MAE (Max Adverse)        │
│  PnL: Calculate in risk units (R) and percent                    │
│  Risk Governor: Adjust mode (LOCKDOWN if DD > threshold)         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   BACKTEST OUTPUTS                               │
├─────────────────────────────────────────────────────────────────┤
│  CSV: Trade log (entry/exit time, price, pnl_r, hold_bars, etc) │
│  JSON: Metrics (win_rate, profit_factor, max_dd, sharpe, etc)    │
│  JSON: Trade features (for ML retraining)                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   VALIDATION & AUDIT                             │
├─────────────────────────────────────────────────────────────────┤
│  Forward validation (out-of-sample test)                         │
│  Forensic analysis (trade-level deep dive)                       │
│  Robustness audit (sensitivity testing)                          │
│  Model drift monitoring (backtest vs paper trading)              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. System Outputs & Results

### **Trade Outputs**
- **`combined_trades.csv`** - Master dataset of all backtested trades
- **`experiment_F_structural_sl.csv`** - Experiment F trade log (40+ columns)
  - Columns: symbol, direction, entry_time, exit_time, entry_price, sl_price, tp_price, pnl_r, holding_bars, mfe_r, mae_r, structural_stop_price, stop_distance_atr, fvg_type, zone_size_atr, exit_reason, etc.

### **Performance Metrics**
- **`combined_metrics.json`** - Overall system metrics
  - Keys: `total_trades`, `win_rate`, `profit_factor`, `expectancy_r`, `max_drawdown_r`, `sharpe_ratio`, `calmar_ratio`, `sortino_ratio`, etc.
- **`experiment_*_metrics.json`** - Per-experiment metrics (A-F)

### **Analysis Reports** (Markdown)
- **`audit_report.md`** - PAC/FVG audit findings
- **`forensic_report.md`** - Trade-level forensic analysis
- **`e_robustness_audit.md`** - Robustness testing results
- **`final_funding_diagnostic.md`** - Capital allocation & Masaniello analysis

### **Decomposition Analysis**
- **`expectancy_report.csv`** - Edge breakdown by symbol, regime, session, timeframe
- **`e_side_breakdown.csv`** - Win rate/expectancy by LONG vs SHORT
- **`e_symbol_breakdown.csv`** - Per-symbol profitability
- **`e_month_breakdown.csv`** - Monthly performance
- **`drawdown_*.csv`** - Drawdown timeline & analysis
- **`stress_test.csv`** - Stress testing under adverse conditions

### **ML & Research**
- **`feature_importance.csv`** - Top 20 features by ML importance
- **`ml_trade_dataset.csv`** - Feature dataset for model training
- **`filter_diagnostics.csv`** - Quality filter effectiveness analysis
- **`fvg_mitigation_*.csv`** - FVG mitigation sensitivity tests
- **`fvg_symbol_audit.csv`** - FVG performance per symbol

### **Paper Trading**
- **`status.json`** - Current paper trading status
- **`paper_trading/logs/`** - Intraday trade logs
- **`paper_trading/reports/`** - Performance reports

### **Forensic Deep Dive** (under `results/forensic_f/`)
- **`forensic_trades_dataset.csv`** - Every trade with forensic metadata
- **`forensic_event_timeline.csv`** - Minute-by-minute event timeline
- **`code_flow_map.md`** - Code execution flow documentation

---

## 6. Key Classes & Functions

### **Detector Classes** (per module)

```python
# BOS Detection
from modules.bos.detector import detect_bos, BosConfig

# FVG Detection
from modules.fvg.detector import detect_fvg

# Trend Signal
from modules.trend import get_trend_signal, TrendSignalResult

# Structural SL
from modules.structural_sl.detector import (
    detect_origin_swing, 
    detect_liquidity_sweep, 
    StructuralStop
)

# Order Blocks
from modules.ob.detector import detect_order_blocks

# Scalping Signal
from strategy.scalping_setup import (
    build_scalping_context, 
    ScalpingSignal, 
    ScalpingConfig
)
```

### **Backtest Orchestrator**

```python
from backtest.combined_backtest import (
    run_combined_backtest,
    run_oos_backtest,
    run_filter_diagnosis,
    run_calibration,
    CombinedBacktestConfig,
)

# Configuration example
config = CombinedBacktestConfig(
    data_dir=Path("data/mt5"),
    symbols=("EURUSD", "GBPUSD", "XAUUSD"),
    timeframe="M15",
    min_confidence=0.52,
    max_hold_bars=16,
    use_ml_quality_filter=True,
    ml_model_path=Path("ml/models/quality_filter.pkl"),
)

trades, metrics = run_combined_backtest(config)
```

### **ML Pipeline**

```python
from ml.feature_pipeline import build_feature_pipeline
from ml.train_quality_model import train_quality_model, TrainingConfig

# Build features
dataset_with_features, schema = build_feature_pipeline(raw_dataset)

# Train model
config = TrainingConfig(
    test_size=0.2,
    model_type="xgboost",
    hyperparams={"max_depth": 6, "learning_rate": 0.1}
)
model = train_quality_model(dataset_with_features, config)
```

### **Risk Management**

```python
from risk.meta_risk_governor import (
    GovernorState, 
    GovernorConfig, 
    next_state
)

governor = GovernorState(mode="NORMAL", consecutive_losses=0)
new_state = next_state(governor, GovernorConfig())
# Output: CAUTION (if losses >= 2) or DEFENSIVE (if losses >= 3) or LOCKDOWN (if losses >= 5)
```

---

## 7. Current Pipeline (from Raw Data to Experiment Output)

### **Step 1: Data Refresh** (`run_system.py` → `_refresh_data_if_needed()`)
```
Check if OHLC parquets are < 24h old
├─ YES: Skip download, use local data
└─ NO:  Connect to MetaTrader 5, download fresh 2-year history per symbol/TF
```

### **Step 2: Feature Engineering** (`backtest/combined_backtest.py` → `_build_signals_from_context()`)
```
For each symbol in [EURUSD, GBPUSD, XAUUSD]:
  For each M15 bar:
    1. Load D1/H4/M15 frames at current time
    2. Calculate ATR, RSI, EMA (fast/slow)
    3. Detect BOS, FVG, CHOCH, OB
    4. Classify market regime (TRENDING/RANGING/etc)
    5. Get trend signal (MTF consensus + ML confidence)
    6. Filter by session (London 7-11 UTC, New York 13-17 UTC)
    7. Generate scalping signal if all conditions met
```

### **Step 3: ML Quality Filtering**
```
For each signal:
  1. Extract 30+ features (trend_confidence, atr_ratio, bos_strength, fvg_size, etc)
  2. Load quality_filter.pkl model
  3. Predict: P(trade_win) = model.predict_proba(features)
  4. Filter: Keep only if P(trade_win) >= threshold (0.60 base, regime-adjusted)
  5. Track feature values + prediction for audit/retraining
```

### **Step 4: Trade Simulation** (`_simulate_trade_with_stats()`)
```
For each filtered signal:
  1. Find entry candle (bar where signal generated)
  2. Set SL = entry - ATR (LONG) or entry + ATR (SHORT)
  3. Set TP = entry + 2*ATR (LONG) or entry - 2*ATR (SHORT)
  4. Simulate holding for up to 16 bars:
     - Track MFE (max favorable) & MAE (max adverse)
     - Exit on SL hit / TP hit / bar limit
     - Calculate PnL in Risk units (R) and %
```

### **Step 5: Risk Governance**
```
After each trade:
  1. Update consecutive_loss counter
  2. Calculate daily & total drawdown
  3. Next state: NORMAL → CAUTION → DEFENSIVE → LOCKDOWN
  4. Adjust thresholds per risk mode for next trades
```

### **Step 6: Outputs**
```
Save to results/:
  ├── combined_trades.csv (master trade log)
  ├── combined_metrics.json (performance metrics)
  ├── ml_trade_dataset.csv (features for retraining)
  ├── filter_diagnosis.json (quality filter analysis)
  └── forensic_*.csv (audit datasets)
```

### **Step 7: Validation** (optional)
```
If run_forward_validation.py:
  → Out-of-sample test on forward data
  → Compare backtest vs forward metrics
  → Detect model drift
```

---

## 8. Configuration & Settings

### **Main Configuration Files**

| File | Purpose | Key Settings |
|------|---------|--------------|
| **run_system.py** | System orchestrator | Symbols, timeframes, data retention |
| **backtest/combined_backtest.py** | Backtest config | `CombinedBacktestConfig` dataclass |
| **paper_trading/config.json** | Paper trading setup | Capital ($25k), risk/trade (0.5%), symbols, sessions |
| **ml/features_schema.json** | ML feature definitions | Feature names, types, transformations |
| **risk/meta_risk_governor.py** | Risk thresholds | Loss limits, DD limits, mode transitions |
| **strategy/scalping_setup.py** | Strategy params | `ScalpingConfig`: confluence, session filters, thresholds |
| **pac_sequence/state_machine.py** | PAC config | TTL, mitigation method (wick/close/average) |

### **Key Tunable Parameters**

```python
# Backtest
min_confidence: float = 0.52                # Min signal confidence to trade
max_hold_bars: int = 16                     # Max bars to hold scalp trade
use_ml_quality_filter: bool = True          # Enable ML trade quality filter
base_ml_threshold: float = 0.60             # ML probability threshold

# Strategy
require_d1_h4_agreement: bool = False       # Require macro TF alignment
min_confluence_score: int = 2               # Min structure confirmations
min_atr_ratio: float = 1.0                  # Min volatility for entry

# Risk
caution_after_losses: int = 2               # Losses to trigger CAUTION mode
defensive_after_losses: int = 3             # Losses to trigger DEFENSIVE
lockdown_after_losses: int = 5              # Losses to trigger LOCKDOWN
lockdown_day_dd: float = 4.0                # Daily DD % for LOCKDOWN

# Data
data_dir: Path = Path("data/mt5")           # OHLC cache location
symbols: tuple = ("EURUSD", "GBPUSD", "XAUUSD")
timeframe: str = "M15"                      # Main trading timeframe
```

---

## 9. Data Flow Diagram (Text-based)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           MARKET DATA SOURCE                                  │
│                        (MetaTrader 5 Terminal)                               │
│                                                                              │
│    EURUSD    GBPUSD    XAUUSD  (3 symbols)                                  │
│    M15/H1    M15/H1    M15/H1  (Multiple timeframes)                        │
│    @ 2+ year history preserved locally                                       │
└─────────────────────────┬────────────────────────────────────────────────────┘
                          │ downloader.py
                          ↓
        ┌─────────────────────────────────┐
        │  Parquet OHLCV Caches           │
        │  data/mt5/*.parquet             │
        │  (240K+ bars per symbol/TF)     │
        └────────┬────────────────────────┘
                 │
    ┌────────────┴────────────┬──────────────────────┐
    ↓                         ↓                      ↓
┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
│ EURUSD frame │    │ GBPUSD frame │    │ XAUUSD frame     │
│ (M15 primary)│    │ (M15 primary)│    │ (M15 primary)    │
└──────────────┘    └──────────────┘    └──────────────────┘
    │                    │                      │
    │                    │                      │
    ↓                    ↓                      ↓
┌──────────────────────────────────────────────────────┐
│        For each M15 candle timestamp:                │
│                                                      │
│  1. Load D1, H4, M15 frames at that time            │
│  2. Calculate indicators: ATR, RSI, EMA             │
│  3. Detect structures:                               │
│     ├─ Swing points (high/low)                       │
│     ├─ BOS (breakout + followthrough)               │
│     ├─ FVG (3-candle gaps)                          │
│     ├─ CHOCH (structure invalidation)               │
│     ├─ OB (order blocks)                            │
│     └─ Fractals (pattern recognition)               │
│  4. Classify regime: TRENDING/RANGING/VOL            │
│  5. Trend signal: MTF consensus + ML confidence     │
│  6. Validate: Session filter, confluence score      │
│  7. Build signal context (30+ features)             │
└─────────────────────────────┬──────────────────────┘
                              │
                              ↓
                ┌──────────────────────────┐
                │  ML Quality Filter       │
                │  quality_filter.pkl      │
                │  (XGBoost)               │
                │                          │
                │  P(trade_win) = model()  │
                │  Filter: P >= threshold  │
                └─────────┬────────────────┘
                          │
                   ┌──────┴─────┐
                   │ PASS       │ FAIL
                   ↓            ↓
            ┌─────────────┐   (skip)
            │   Trade     │
            │ Simulation  │
            │             │
            │ • Set SL/TP │
            │ • 16-bar max│
            │ • Track MFE/│
            │   MAE       │
            │ • Calc PnL  │
            └─────┬───────┘
                  │
                  ↓
        ┌─────────────────────┐
        │  Risk Governor      │
        │  • Track drawdown   │
        │  • Update state:    │
        │    NORMAL/CAUTION/  │
        │    DEFENSIVE/       │
        │    LOCKDOWN         │
        └────────┬────────────┘
                 │
                 ↓
    ┌─────────────────────────────────┐
    │  BACKTEST OUTPUT FILES          │
    │  results/                        │
    │                                  │
    │  ├─ combined_trades.csv          │
    │  ├─ combined_metrics.json        │
    │  ├─ ml_trade_dataset.csv         │
    │  ├─ filter_diagnostics.csv       │
    │  └─ forensic_*.csv               │
    └─────────────────────────────────┘
```

---

## 10. System Performance Summary

### **Current Configuration** (as of June 2026)
- **Symbols**: EURUSD, GBPUSD, XAUUSD
- **Primary Timeframe**: M15 (scalping)
- **Analysis Timeframes**: D1, H4, M15
- **Trading Sessions**: London (7-11 UTC), New York (13-17 UTC)
- **Max Hold**: 16 bars (~4 hours for M15)
- **Risk per Trade**: 0.5% of capital
- **ML Quality Threshold**: 0.60 (base)
- **Target Profit Factor**: 1.3+
- **Target Win Rate**: 52%+
- **Max Drawdown Limit**: 10% (triggers LOCKDOWN)

### **Key Modules Status**
✅ **Complete**: BOS, FVG, CHOCH, OB, Swing, Indicators, Trend, Structural SL  
✅ **ML-Integrated**: Quality filter, Regime detector, Feature pipeline  
✅ **Risk Management**: Dynamic thresholds, Risk governor modes  
✅ **Audit/Validation**: Forensic analysis, Robustness testing, Forward validation  

---

## 11. Entry Points & Usage

### **Run Full System** (from `run_system.py`)
```bash
python run_system.py
```
Output: Combined backtest metrics + system status report

### **Rebuild Experiment** (from `scripts/`)
```bash
python scripts/rebuild_experiment_f_structural.py
```
Output: `experiment_F_structural_sl.csv` + metrics JSON

### **Forward Validation** (test on unseen data)
```bash
python scripts/run_forward_validation.py
```
Output: Forward test metrics + drift analysis

### **Forensic Audit** (deep dive analysis)
```bash
python scripts/run_forensic_analytics.py
```
Output: Forensic CSV + detailed report

### **Generate Comparison** (E vs F variants)
```bash
python scripts/generate_comparison.py
```
Output: `final_comparison_table.csv` + metrics

---

## 12. Important Notes

1. **Data Freshness**: System checks MT5 data age (24h threshold). If data is stale, it automatically refreshes from MetaTrader 5 terminal.

2. **Experiments A-F**: Different variants tested:
   - **A-E**: Incremental refinements (different filters/thresholds)
   - **F (Structural SL)**: Uses origin swing for structural stop placement (latest iteration)

3. **PAC Sequence**: Proprietary state machine ensures:
   - FVG created → Mitigation level reached → Entry signal generated
   - Invalidations tracked (OPPOSITE CHOCH, OPPOSITE BOS, TTL expired)

4. **ML Quality Filter**: 
   - Trained on historical trade outcomes
   - Updated when enough new trades generated (retraining pipeline)
   - Reduces false signals but may filter out edge trades

5. **Risk Governor**:
   - Automatically enters LOCKDOWN mode if losses/DD exceed thresholds
   - Prevents over-trading during adverse conditions
   - Can be manually overridden in paper trading

6. **Forensic Capability**: 
   - Every trade has complete audit trail
   - Minute-by-minute event timeline available
   - Enables root-cause analysis of failures

---

## 13. Next Steps for Exploration

- **Deep Dive Modules**: Review individual module READMEs under `/modules/*/README.md`
- **Experiment Results**: Check `results/*.csv` for trade-level data
- **Paper Trading**: Monitor `paper_trading/status.json` for live performance
- **Audit Reports**: Read `results/*_robustness_audit.md` for findings
- **Feature Importance**: Check `results/feature_importance.csv` for model drivers

---

**End of Project Overview** — Last Updated: June 1, 2026
