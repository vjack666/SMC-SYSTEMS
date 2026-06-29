# SMC SYSTEMS - Project Inventory
## Complete Asset Map for MT5 Integration

**Generated**: June 1, 2026  
**Status**: Production-Ready System with Continuous Validation  
**Architecture**: Multi-symbol, multi-timeframe (H1), ML-filtered, risk-governed

---

## 1. DIRECTORY STRUCTURE & COMPONENTS

### 1.1 Core Trading Modules (`/modules`)

| Module | Files | Purpose | Status |
|--------|-------|---------|--------|
| **bos** | detector.py, schema.py | Break of Structure detection (price breaks swing high/low) | ✅ Complete |
| **fvg** | detector.py, schema.py | Fair Value Gap detection (candle gap before reversal) | ✅ Complete |
| **choch** | detector.py, schema.py | Change of Character detection (structural shift) | ✅ Complete |
| **ob** | detector.py, schema.py | Order Block detection (entry liquidity zones) | ✅ Complete |
| **swing** | detector.py, schema.py | Swing High/Low detection (local extrema) | ✅ Complete |
| **structural_sl** | detector.py, schema.py | Structural Stop Loss (origin swing + liquidity sweep) | ✅ Fixed (Phase 0) |
| **indicators** | atr.py, rsi.py, ema.py, momentum.py | Technical indicators (ATR, RSI, EMA, Momentum) | ✅ Complete |
| **pullback** | detector.py, schema.py | Pullback pattern detection | ✅ Complete |
| **fractal** | detector.py, schema.py | Fractal candle detection | ✅ Complete |
| **trend** | detector.py, schema.py | Trend direction classification | ✅ Complete |

**Signal Entry Points** (from confluence):
- BOS + Swing Low (LONG) / Swing High (SHORT)
- FVG + CHOCH + OB formation
- Entry: First candle close beyond structure

### 1.2 Feature Engineering (`/ml`)

| Component | Files | Purpose |
|-----------|-------|---------|
| **Features** | features_schema.json | 30+ features: price action, structure, regime, momentum |
| **Extraction** | feature_extractor.py | Compute features at entry bar |
| **Preprocessing** | preprocessor.py | Normalization, null handling |
| **Model** | xgboost_model.pkl | Trained XGBoost classifier (P(win) prediction) |
| **Inference** | ml_engine.py | Real-time prediction, confidence scoring |

**Feature Categories**:
- Price Action (5): ATR, RSI, EMA slope, momentum, volatility
- Structure (8): BOS strength, FVG size, CHOCH distance, OB intensity
- Regime (6): Session type, trend strength, regime shift intensity, volatility regime
- Confluence (7): Number of confluent signals, timing strength, entry quality
- Liquidity (4): Sweep depth, liquidity proximity, level stacking

**ML Filter Threshold**: Keep trades only if P(win) ≥ 0.60

### 1.3 Risk Management (`/risk`)

| Component | Files | Purpose |
|-----------|-------|---------|
| **Governor** | meta_risk_governor.py | 4-mode risk state machine (NORMAL/CAUTION/DEFENSIVE/LOCKDOWN) |
| **Position Sizing** | position_sizer.py | 0.5% risk/trade, 1:2.0 RR minimum |
| **Exposure Manager** | exposure_manager.py | Symbol exposure limits, correlation checks |
| **Drawdown Tracker** | drawdown_tracker.py | Monitor and respond to peak drawdown |

**Risk States**:
- **NORMAL**: Full trading (DD < 15%)
- **CAUTION**: Reduced lot size (15% < DD < 20%)
- **DEFENSIVE**: Entry on strong signals only (20% < DD < 25%)
- **LOCKDOWN**: Stop trading (DD > 25%)

### 1.4 Trading System (`/backtest`, `/paper_trading`, `/live_trading`)

| Component | Purpose | Config |
|-----------|---------|--------|
| **Backtester** | Simulate M15 trades with MFE/MAE | backtest/combined_backtest.py |
| **Paper Trading** | Risk-free validation | $25k capital, 0.5% risk |
| **Live Broker** | Interactive Brokers connection | oanda_connector.py |

### 1.5 Data Management (`/data`)

| Type | Format | Symbols | Timeframe | Retention |
|------|--------|---------|-----------|-----------|
| **Raw OHLC** | .parquet | EURUSD, GBPUSD, XAUUSD | H1 | 100k candles |
| **Cached Features** | .pkl | All symbols | H1 | Rolling 1000 bars |
| **Trade Results** | .csv | All experiments | - | All |
| **Metrics** | .json | All experiments | - | All |

---

## 2. SIGNALS & FEATURES TO EXPORT TO MT5

### 2.1 Core Signal Information

**At Entry Point**:
```
- symbol: string (EURUSD, GBPUSD, XAUUSD)
- direction: int (1=LONG, -1=SHORT)
- entry_price: float
- sl_price: float (structural origin swing + sweep)
- tp_price: float (entry + 2.0 × RR)
- risk_r: float (0.5% of capital)
- ml_score: float (P(win) from XGBoost, 0.6-1.0)
- session: string (Asian, European, American)
- regime: string (Trending, Ranging, Volatile)
- bos_score: float (break of structure strength)
- fvg_score: float (FVG distance and size)
- mitigation_score: float (liquidity sweep intensity)
- confluence_count: int (number of confluent signals)
- entry_bar_index: int (absolute bar number in MT5)
- timestamp: datetime (UTC)
```

### 2.2 Structural Elements

**BOS (Break of Structure)**:
```
- origin_swing_high/low: float
- break_price: float
- break_bar_index: int
- bos_distance_atr: float (measured from swing)
- bos_validity: bool (price actually broke with close)
```

**FVG (Fair Value Gap)**:
```
- fvg_top: float
- fvg_bottom: float
- fvg_size_pips: float
- fvg_age_bars: int
- fvg_mitigation: bool (price returned to fill)
```

**CHOCH (Change of Character)**:
```
- choch_bar_index: int
- character_shift: string (Trending→Ranging or vice versa)
- structural_severity: float (1.0-5.0, how severe the shift)
```

**Order Block (OB)**:
```
- ob_high/low: float
- ob_strength: float (confluence with price)
- ob_integrity: bool (price respecting block)
```

**Structural Stop Loss**:
```
- origin_swing_idx: int
- origin_swing_price: float
- sweep_bar_index: int
- sweep_intensity: float (how deep into OB)
- structural_stop_price: float
- stop_distance_atr: float
- stop_distance_pips: float
```

### 2.3 ML Features (Real-time)

```
- ml_confidence: float (P(win), model's win probability estimate)
- feature_importance_top3: list (which features drove prediction)
- feature_values: dict (all 30 features at entry time)
- model_version: string (for reproducibility)
- last_model_training_date: date (when model was trained)
```

### 2.4 Risk Management Features

```
- risk_per_trade_usd: float
- potential_reward_usd: float
- rr_ratio: float (always 2.0 or higher)
- current_account_risk_pct: float
- current_risk_state: string (NORMAL/CAUTION/DEFENSIVE/LOCKDOWN)
- current_drawdown_pct: float
- available_capital: float
- symbol_exposure_pct: float
```

### 2.5 Session & Regime Information

```
- session_start_utc: datetime
- session_volatility: float (current session ATR vs 20-day avg)
- session_trend: string (Up/Down/Neutral)
- session_liquidity: string (High/Medium/Low)
- market_regime: string (Trending/Ranging/Volatile/Consolidation)
- regime_strength: float (0.0-1.0)
- previous_4h_direction: int (1/-1/0)
```

---

## 3. EXPERIMENTAL OUTPUTS (Current)

### 3.1 Experiment E (ML Baseline)
- **1,776 trades** from 100k EURUSD/GBPUSD/XAUUSD candles
- Win rate: 60%+
- Profit factor: ~2.8
- Uses ML confidence filtering
- **Schema**: 40+ columns including confidence, features, MFE/MAE

### 3.2 Experiment F Fixed (Structural SL)
- **14,344 trades** (14,804 signals processed)
- Structural stop loss instead of ATR-based
- Win rate: ~40% (more entries, realistic SL placement)
- Structural stops placed at origin swing + liquidity sweep
- **Schema**: All signals + detailed structural SL metrics
- **Status**: All validation criteria passed (0 invalid stops, 0 exit logic violations)

### 3.3 Datasets Generated

| Dataset | Rows | Columns | Purpose |
|---------|------|---------|---------|
| combined_trades.csv | 1776 | 40+ | Experiment E baseline |
| experiment_F_structural_sl.csv | 14344 | 42 | Structural SL experiment |
| experiment_F_*_metrics.json | 1 | - | Win rate, PF, expectancy, etc. |
| forensic_f/ | - | - | Audit artifacts for broken F |

---

## 4. DATA PIPELINE STAGES

### 4.1 Stage 1: Data Ingestion
- **Source**: MT5 via MetaTrader5 Python package OR local .parquet cache
- **Symbols**: EURUSD, GBPUSD, XAUUSD (H1 timeframe)
- **Freshness Check**: 24h max staleness, auto-refresh if older
- **Storage**: /data/mt5/{SYMBOL}_H1.parquet (100k candles rolling)

### 4.2 Stage 2: Indicator Computation
- **Indicators**: ATR (14), RSI (14), EMA (9, 21, 50), Momentum
- **Computation**: On-demand during feature extraction
- **Caching**: Last 1000 bars cached in memory

### 4.3 Stage 3: Structure Detection
- **Detectors**: BOS, FVG, CHOCH, OB, Swing, Structural SL
- **Logic**: Applied in order of dependency
- **Output**: List of active structures with metadata

### 4.4 Stage 4: Signal Generation
- **Confluence**: Entry when 2+ signals align
- **Session Filter**: Optional (different sessions have different efficacy)
- **Trend Filter**: Only trade with trend (configurable)
- **Output**: List of entry opportunities with scores

### 4.5 Stage 5: ML Quality Filter
- **Model**: XGBoost trained on historical backtests
- **Threshold**: Keep only if P(win) ≥ 0.60
- **Features**: 30 engineered from price action + structures
- **Output**: Filtered signal list (typically 60% retained)

### 4.6 Stage 6: Risk Management
- **Position Size**: 0.5% account risk per trade
- **RR Ratio**: Minimum 1:2.0 (typically 1:2.0)
- **State Check**: LOCKDOWN blocks all entry (DD > 25%)
- **Output**: Sizing + state + capital check

### 4.7 Stage 7: Trade Simulation (Backtest)
- **Entry**: At signal generation bar
- **Exit**: TP hit, SL hit, or max 16-bar hold (whichever first)
- **Tracking**: MFE (max favorable excursion), MAE (max adverse)
- **Output**: Individual trade record + metrics

---

## 5. INTEGRATION REQUIREMENTS FOR MT5

### 5.1 What Python Must Provide
1. **Real-time signals** at every bar close (H1)
2. **Feature engineering** - 30+ features computed at entry time
3. **ML inference** - P(win) prediction at entry time
4. **Risk calculations** - SL/TP placement + sizing
5. **Validation** - Check for invalid stops, exit logic errors
6. **Audit trail** - Log all decisions with timestamps

### 5.2 What MT5 Must Execute
1. **Signal reception** - Read exported signal (CSV/JSON/socket)
2. **Order placement** - Open position with SL and TP
3. **Position tracking** - Monitor entry, exits, MFE/MAE
4. **Exit execution** - Close at TP or SL
5. **Result recording** - Store trade outcome for analysis
6. **Backtesting** - Replay signals in Strategy Tester

### 5.3 Critical Constraints
- **No modification of signals** in MT5 (must use exact SL/TP from Python)
- **Exact timestamp matching** between Python and MT5 (UTC)
- **Robustness to disconnection** (graceful handling of signal loss)
- **Audit trail** (all decisions timestamped and logged)
- **Separation of concerns** (Python = logic, MT5 = execution)

---

## 6. CURRENT VALIDATION STATUS

✅ **Experiment E**: Validated, production-ready  
✅ **Experiment F Fixed**: All criteria passed  
- 0 invalid stops
- 0 exit logic violations
- 0 ATR NaN values
- 100 unique holding bar values (realistic)
- 14,344 trades generated from 14,804 signals

---

## 7. INTEGRATION ARCHITECTURE PRINCIPLES

### 7.1 Separation of Concerns
```
Python Layer:
  ├─ Market Data
  ├─ Signal Generation (BOS, FVG, CHOCH, OB, Swing)
  ├─ ML Filtering
  ├─ Risk Management
  └─ Trade Simulation

MT5 Layer:
  ├─ Order Execution
  ├─ Position Tracking
  ├─ Real-time Market Updates
  └─ Result Logging

Bridge:
  ├─ Signal Export (formatted JSON/CSV)
  ├─ Signal Import (acknowledgment)
  └─ Result Synchronization
```

### 7.2 Redundancy & Validation
- **Schema validation** on both sides
- **Checksum verification** of critical fields
- **Fallback to CSV** if real-time connection lost
- **Audit logging** of every signal sent/received

### 7.3 Scalability
- Multi-symbol support (EURUSD, GBPUSD, XAUUSD)
- Multi-timeframe ready (current H1, extensible to M15/M30/D1)
- Stateless signal generation (no session state needed)
- Parallelizable feature extraction

---

## 8. NEXT STEPS FOR INTEGRATION

1. **FASE 2**: Research MT5 integration methods (MetaTrader5 package, CSV bridge, JSON, TCP, ZeroMQ, REST)
2. **FASE 3**: Design complete architecture with decision points
3. **FASE 4**: Define exact JSON schemas for signals and features
4. **FASE 5**: Implement Python bridge module (signal_exporter, signal_receiver, schema validation)
5. **FASE 6**: Create MQL5 EA template with order execution
6. **FASE 7**: Design backtest strategy in Strategy Tester
7. **FASE 8**: Create implementation roadmap with effort estimates

---

## 9. SUCCESS CRITERIA FOR MT5 INTEGRATION

- [ ] All signals properly exported with correct SL/TP
- [ ] 0 schema validation failures
- [ ] Order execution matches signal parameters (±1 pip tolerance)
- [ ] MFE/MAE tracking aligns with backtest
- [ ] Results synchronize between Python and MT5
- [ ] Audit trail complete and verifiable
- [ ] Backtesting reproduces Python simulation results
- [ ] Paper trading shows no slippage beyond +/-2 pips
- [ ] Live trading ready (EA passes Strategy Tester with 95%+ match to Python)
