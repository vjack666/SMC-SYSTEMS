# FASE 3: Target Architecture Design
## Complete System Architecture for SMC SYSTEMS ↔ MetaTrader5 Integration

**Scope**: End-to-end architecture showing all layers, components, and data flows  
**Purpose**: Blueprint for Phase implementation (all phases after this)  
**Format**: Text diagrams + component descriptions

---

## 1. COMPLETE SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          SMC SYSTEMS COMPLETE STACK                              │
└─────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ PYTHON LAYER (Signal Generation & Analytics)                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 1. DATA INGESTION                                                   │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │  ┌─────────────────────────────────────────────────────────────┐   │    │
│  │  │ Raw OHLC Input (3 symbols: EURUSD, GBPUSD, XAUUSD)          │   │    │
│  │  │ ├─ Method 1: MT5 API (Python package)                       │   │    │
│  │  │ ├─ Method 2: Parquet files (local cache)                    │   │    │
│  │  │ └─ Method 3: Broker API (if available)                      │   │    │
│  │  │ Source: 100k bars H1 timeframe                              │   │    │
│  │  └─────────────────────────────────────────────────────────────┘   │    │
│  │                                   ↓                                  │    │
│  │  ┌─────────────────────────────────────────────────────────────┐   │    │
│  │  │ Indicator Calculation (on-demand)                           │   │    │
│  │  │ ├─ ATR (14 period)                                          │   │    │
│  │  │ ├─ RSI (14 period)                                          │   │    │
│  │  │ ├─ EMA (9, 21, 50 period)                                   │   │    │
│  │  │ ├─ Momentum                                                 │   │    │
│  │  │ └─ [Other indicators as needed]                             │   │    │
│  │  └─────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 2. STRUCTURE DETECTION (Parallel processing)                        │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐        │    │
│  │  │  Swing    │  │   BOS     │  │   FVG     │  │  CHOCH    │  ┌─────┴──┐ │
│  │  │  Detector │  │  Detector │  │  Detector │  │ Detector  │  │   OB    │ │
│  │  │           │  │           │  │           │  │           │  │ Detector│ │
│  │  │ (+ Price  │  │ (+ Sweep  │  │ (+ Gap    │  │ (+ Char   │  │ (+ Liq  │ │
│  │  │  extrema) │  │  Valid)   │  │  Logic)   │  │   Shift)  │  │  Zones) │ │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘  └─────────┘ │
│  │        ↓               ↓              ↓              ↓              ↓      │
│  │  All structures detected with timestamps & validity checks               │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 3. STRUCTURAL STOP LOSS CALCULATION                                 │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │  ├─ Find origin swing (min low for LONG, max high for SHORT)        │    │
│  │  ├─ Validate sweep occurred (liquidity taken)                       │    │
│  │  ├─ Extended lookback if needed (edge case handling)                │    │
│  │  ├─ Final validation: SL on correct side of entry                  │    │
│  │  └─ Output: Precise SL_price + distance_atr                         │    │
│  │  Status: ✅ FIXED (Phase 0) - 0 invalid stops                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 4. SIGNAL GENERATION (Confluence Scoring)                           │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │  Confluence Checks:                                                 │    │
│  │  ├─ 2+ signals must align (BOS + FVG/OB + Session filter)          │    │
│  │  ├─ Calculate confluence score (weighted sum)                       │    │
│  │  ├─ Only proceed if score ≥ threshold                              │    │
│  │  └─ Output: Clean signal list ready for ML filtering               │    │
│  │                                                                     │    │
│  │  Volume: 14,804 signals per 100k bars (daily signal rate)           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 5. FEATURE EXTRACTION (30 ML Features)                              │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │  ├─ Price Action (5): ATR, RSI, EMA slopes, momentum               │    │
│  │  ├─ Structure (8): BOS/FVG/OB/CHOCH metrics                        │    │
│  │  ├─ Regime (6): Trend, volatility, session, market regime          │    │
│  │  ├─ Confluence (7): Signal alignment, entry quality                │    │
│  │  └─ Liquidity (4): Sweep, stacking, slippage                       │    │
│  │                                                                     │    │
│  │  Output: Feature vector [1×30] for each signal                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 6. ML FILTERING (XGBoost Classifier)                                │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │  Input: 30 features (normalized)                                   │    │
│  │  Model: XGBoost trained on historical backtests                    │    │
│  │  Output: P(win) probability (0.0 - 1.0)                            │    │
│  │  Threshold: ≥ 0.60 to keep trade                                   │    │
│  │  Retention: ~60% of signals pass filter                            │    │
│  │  Status: ✅ Production model v2.0 in use                           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 7. RISK MANAGEMENT LAYER                                            │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │  ┌───────────────────────────────────────────────────────────┐     │    │
│  │  │ Risk State Machine (4 states)                             │     │    │
│  │  ├─ NORMAL (DD < 15%): 100% position sizing                 │     │    │
│  │  ├─ CAUTION (15-20% DD): 50% position sizing                │     │    │
│  │  ├─ DEFENSIVE (20-25% DD): High-conf only (P>0.75)          │     │    │
│  │  └─ LOCKDOWN (DD ≥ 25%): NO new entries                      │     │    │
│  │  └───────────────────────────────────────────────────────────┘     │    │
│  │                                                                     │    │
│  │  ┌───────────────────────────────────────────────────────────┐     │    │
│  │  │ Position Sizing                                           │     │    │
│  │  ├─ Risk per trade = 0.5% of capital                         │     │    │
│  │  ├─ Position size = Risk / (Entry - SL)                      │     │    │
│  │  ├─ TP = Entry + (2.0 × Risk) [RR 1:2.0]                     │     │    │
│  │  └─ Max symbol exposure = 30% of capital                     │     │    │
│  │  └───────────────────────────────────────────────────────────┘     │    │
│  │                                                                     │    │
│  │  ┌───────────────────────────────────────────────────────────┐     │    │
│  │  │ Validation Checklist                                      │     │    │
│  │  ├─ Entry, SL, TP on correct sides                           │     │    │
│  │  ├─ RR ratio ≥ 2.0                                           │     │    │
│  │  ├─ Position size > 0                                        │     │    │
│  │  ├─ Risk ≤ max allowed                                       │     │    │
│  │  ├─ Symbol exposure valid                                    │     │    │
│  │  └─ Final approval before export                             │     │    │
│  │  └───────────────────────────────────────────────────────────┘     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 8. SIGNAL EXPORT / BRIDGE LAYER                                     │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │  ┌───────────────────────────────────────────────────────────┐     │    │
│  │  │ Method A: MT5 Package (Primary)                           │     │    │
│  │  ├─ Direct API calls to mt5.order_send()                     │     │    │
│  │  ├─ Real-time order placement                                │     │    │
│  │  ├─ Latency: <10ms (same machine)                            │     │    │
│  │  └─ Best for: Live trading + paper trading                  │     │    │
│  │  └───────────────────────────────────────────────────────────┘     │    │
│  │                                                                     │    │
│  │  ┌───────────────────────────────────────────────────────────┐     │    │
│  │  │ Method B: CSV Bridge (Fallback + Backtest)               │     │    │
│  │  ├─ Write signals.csv (atomic write)                         │     │    │
│  │  ├─ Read trade_results.csv (EA writes back)                  │     │    │
│  │  ├─ Latency: 50-200ms per bar                                │     │    │
│  │  └─ Best for: Backtest + failover                            │     │    │
│  │  └───────────────────────────────────────────────────────────┘     │    │
│  │                                                                     │    │
│  │  Output: Signal export in standard format                         │    │
│  │  ├─ All 30 features included                                      │    │
│  │  ├─ Full audit trail (timestamps, validation)                     │    │
│  │  ├─ Trade parameters (entry, SL, TP, sizing)                      │    │
│  │  └─ Ready for MT5 EA consumption                                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ METATRA DER5 LAYER (Order Execution & Monitoring)                            │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ MT5 EA: SMC_SYSTEMS_BRIDGE.mq5                                      │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │  On each H1 bar close:                                              │    │
│  │  ┌───────────────────────────────────────────────────────────┐     │    │
│  │  │ 1. Check for signals (Method A: API OR Method B: CSV)     │     │    │
│  │  │    ├─ MT5 API: Listen to Python via API                  │     │    │
│  │  │    └─ CSV: Read signals.csv from disk                    │     │    │
│  │  └───────────────────────────────────────────────────────────┘     │    │
│  │                                                                     │    │
│  │  ┌───────────────────────────────────────────────────────────┐     │    │
│  │  │ 2. Validate signal schema                                 │     │    │
│  │  │    ├─ Check all fields present                            │     │    │
│  │  │    ├─ Check types and ranges                              │     │    │
│  │  │    ├─ Verify SL/TP on correct sides                       │     │    │
│  │  │    └─ REJECT if invalid (safety mechanism)                │     │    │
│  │  └───────────────────────────────────────────────────────────┘     │    │
│  │                                                                     │    │
│  │  ┌───────────────────────────────────────────────────────────┐     │    │
│  │  │ 3. Place order with exact parameters                      │     │    │
│  │  │    ├─ Symbol: From signal                                 │     │    │
│  │  │    ├─ Type: BUY (direction=1) OR SELL (direction=-1)     │     │    │
│  │  │    ├─ Volume: position_size_lots (from Python)            │     │    │
│  │  │    ├─ Entry: entry_price (market order)                   │     │    │
│  │  │    ├─ SL: sl_price (never modified)                       │     │    │
│  │  │    ├─ TP: tp_price (never modified)                       │     │    │
│  │  │    └─ Comment: signal_id (for tracking)                   │     │    │
│  │  └───────────────────────────────────────────────────────────┘     │    │
│  │                                                                     │    │
│  │  ┌───────────────────────────────────────────────────────────┐     │    │
│  │  │ 4. Monitor active positions                               │     │    │
│  │  │    ├─ Track entry price, current price                    │     │    │
│  │  │    ├─ Calculate current P&L in $                          │     │    │
│  │  │    ├─ Calculate MFE (Max Favorable Excursion)             │     │    │
│  │  │    ├─ Calculate MAE (Max Adverse Excursion)               │     │    │
│  │  │    └─ Log every bar for analysis                          │     │    │
│  │  └───────────────────────────────────────────────────────────┘     │    │
│  │                                                                     │    │
│  │  ┌───────────────────────────────────────────────────────────┐     │    │
│  │  │ 5. Execute exits (automatic)                              │     │    │
│  │  │    ├─ IF price ≥ TP_price (LONG): Close at TP             │     │    │
│  │  │    ├─ IF price ≤ SL_price (LONG): Close at SL             │     │    │
│  │  │    ├─ Max hold: 16 bars (configurable)                    │     │    │
│  │  │    └─ Record exit reason + P&L                            │     │    │
│  │  └───────────────────────────────────────────────────────────┘     │    │
│  │                                                                     │    │
│  │  ┌───────────────────────────────────────────────────────────┐     │    │
│  │  │ 6. Write results (for Python logging)                     │     │    │
│  │  │    ├─ Method A: Return via API to Python                  │     │    │
│  │  │    └─ Method B: Write trade_results.csv                   │     │    │
│  │  │    Data: Entry price, exit price, exit reason, P&L, time  │     │    │
│  │  └───────────────────────────────────────────────────────────┘     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ MT5 Modes                                                           │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │  ✅ Backtesting: Strategy Tester (ea runs, replayable)             │    │
│  │  ✅ Paper Trading: Demo account (real live simulation)             │    │
│  │  ✅ Live Trading: Real account (money at risk)                     │    │
│  │  ✅ Automated: Sets SL/TP, exits automatically                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ MONITORING & ANALYTICS LAYER                                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Python Post-Analysis                                               │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │  ├─ Read trade results from MT5                                    │    │
│  │  ├─ Calculate metrics:                                             │    │
│  │  │  ├─ Win rate                                                   │    │
│  │  │  ├─ Profit factor                                              │    │
│  │  │  ├─ Expectancy                                                 │    │
│  │  │  ├─ Drawdown tracking                                          │    │
│  │  │  ├─ MFE/MAE analysis                                           │    │
│  │  │  └─ Monthly/symbol breakdowns                                  │    │
│  │  ├─ Compare vs backtest expectations                              │    │
│  │  ├─ Alert if significant deviation                                │    │
│  │  └─ Store for continuous improvement                              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Audit Trail & Compliance                                           │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │  ├─ Every signal logged with timestamp                             │    │
│  │  ├─ Every order logged with execution details                      │    │
│  │  ├─ Every exit logged with reasoning                               │    │
│  │  ├─ All validation checks recorded                                 │    │
│  │  ├─ Risk state at entry recorded                                   │    │
│  │  └─ Monthly compliance report generated                            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. THREE EXECUTION MODES

### MODE 1: BACKTESTING (Strategy Tester)

```
┌────────────────────────────────────────────────────────────────────┐
│ BACKTEST FLOW                                                      │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  1. Python (offline, before backtest)                             │
│     ├─ Load 100k historical OHLC bars                             │
│     ├─ Generate signals from bar 1 to N                           │
│     ├─ Calculate all metrics (features, ML scores, etc)           │
│     └─ Export signals.csv (timeseries of signals)                 │
│                                                                    │
│  2. MT5 Strategy Tester (automated)                               │
│     ├─ Load EA: SMC_SYSTEMS_BRIDGE.mq5                            │
│     ├─ Set parameters: Signal file, broker type, etc              │
│     ├─ EA reads signals.csv                                       │
│     ├─ On each bar: Check if signal for this bar                  │
│     ├─ If YES: Place order exactly as specified                   │
│     ├─ Auto-exit at TP or SL                                      │
│     ├─ Record exit price, time, P&L                               │
│     └─ Generate backtest report                                   │
│                                                                    │
│  3. Validation (Python, after backtest)                           │
│     ├─ Read backtest results (Strategy Tester output)             │
│     ├─ Compare trade count vs expected                            │
│     ├─ Verify SL/TP execution                                     │
│     ├─ Check P&L alignment                                        │
│     ├─ Validate no order rejections                               │
│     └─ PASS/FAIL validation report                                │
│                                                                    │
│  Output: results/backtest_report.json                             │
│  Contains: All trades, metrics, validation status                 │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

Expected Backtest Statistics (Experiment F):
├─ Total signals: 14,804
├─ Signals executed: 14,344 (96.9% after ML filter)
├─ Win trades: 5,729 (40%)
├─ Loss trades: 8,615 (60%)
├─ Total P&L: +204.3R
├─ Profit Factor: 1.026
├─ Max Drawdown: -158.1R
├─ Avg Holding: 49.7 bars (per trade)
└─ Status: ✅ READY FOR DEPLOYMENT
```

### MODE 2: PAPER TRADING (Demo Account)

```
┌────────────────────────────────────────────────────────────────────┐
│ PAPER TRADING FLOW (Real-time, Live Market Data)                  │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  1. Python (Real-time, continuous)                                │
│     ├─ Every bar close (H1):                                      │
│     │  ├─ Download latest OHLC                                    │
│     │  ├─ Calculate indicators                                    │
│     │  ├─ Detect structures                                       │
│     │  ├─ Generate signals                                        │
│     │  ├─ Extract features                                        │
│     │  ├─ Run ML filter                                           │
│     │  ├─ Calculate position sizing                               │
│     │  ├─ Export signal (Method A: API OR Method B: CSV)          │
│     │  └─ Log everything with timestamp                           │
│     │                                                             │
│     └─ Update risk state:                                         │
│        ├─ Calculate current account balance                       │
│        ├─ Calculate peak balance                                  │
│        ├─ Calculate drawdown                                      │
│        ├─ Update risk state (NORMAL/CAUTION/DEFENSIVE/LOCKDOWN)  │
│        └─ Adjust next trade sizing if needed                      │
│                                                                    │
│  2. MT5 EA (Real-time, on each tick/bar)                          │
│     ├─ Method A (if using MT5 API):                               │
│     │  ├─ Receive signal from Python (via API)                    │
│     │  ├─ Place order immediately                                 │
│     │  └─ Execution on next available price                       │
│     │                                                             │
│     └─ Method B (if using CSV):                                   │
│        ├─ Check signals.csv every bar                             │
│        ├─ Parse new signals                                       │
│        ├─ Place orders as they appear                             │
│        └─ Write results.csv                                       │
│                                                                    │
│  3. Python (Continuous Monitoring)                                │
│     ├─ Every few seconds:                                         │
│     │  ├─ Query open positions from MT5                           │
│     │  ├─ Calculate current P&L                                   │
│     │  ├─ Track MFE/MAE                                           │
│     │  ├─ Monitor for TP/SL hits                                  │
│     │  └─ Log position state                                      │
│     │                                                             │
│     └─ Every bar close:                                           │
│        ├─ Read closed trades from MT5                             │
│        ├─ Verify P&L matches expectations                         │
│        ├─ Update account metrics                                  │
│        ├─ Send alerts if issues detected                          │
│        └─ Store for analysis                                      │
│                                                                    │
│  Monitoring Dashboard:                                            │
│  ├─ Current account balance                                       │
│  ├─ Drawdown (current vs max)                                     │
│  ├─ Open positions (symbol, entry, current P&L)                   │
│  ├─ Today's trades (count, win rate, P&L)                         │
│  ├─ Signal generation status (on time, no errors)                 │
│  └─ Risk state (NORMAL / CAUTION / DEFENSIVE / LOCKDOWN)          │
│                                                                    │
│  Duration: Continuous (days/weeks/months)                         │
│  Account: Demo account (no real money)                            │
│  Goal: Validate live system before going live                     │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

Success Criteria:
✅ All orders execute within 2 seconds
✅ No slippage > 2 pips
✅ All SL/TP hit correctly
✅ Results align with backtesting (±5%)
✅ No errors for 7+ days continuous
✅ Risk management rules enforced
```

### MODE 3: LIVE TRADING (Real Account)

```
┌────────────────────────────────────────────────────────────────────┐
│ LIVE TRADING FLOW (Real Money)                                    │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ⚠️ PREREQUISITES (All must be satisfied):                         │
│  ├─ Backtest completed and validated                              │
│  ├─ Paper trading completed (7+ days successful)                  │
│  ├─ Risk management rules tested and working                      │
│  ├─ Monitoring and alerts configured                              │
│  ├─ Funding account with minimum capital ($25k+)                  │
│  ├─ MT5 live account configured                                   │
│  └─ All team members trained                                      │
│                                                                    │
│  1. Python (Same as Paper Trading, but with real money)           │
│     └─ All logic identical to paper trading                       │
│        └─ Only difference: Orders affect real account              │
│                                                                    │
│  2. MT5 EA (Same as Paper Trading)                                │
│     └─ No code changes needed                                     │
│        └─ Uses live account connection                            │
│                                                                    │
│  3. Enhanced Monitoring (Risk critical)                           │
│     ├─ Real-time alerts:                                          │
│     │  ├─ If any signal rejected (investigate immediately)        │
│     │  ├─ If order execution price > 2 pips slippage              │
│     │  ├─ If P&L deviation > 5% from expected                     │
│     │  ├─ If drawdown > 15% (CAUTION state)                       │
│     │  ├─ If drawdown > 25% (LOCKDOWN state)                      │
│     │  └─ If any error occurs (contact immediately)               │
│     │                                                             │
│     ├─ Daily compliance review:                                   │
│     │  ├─ All trades executed with correct SL/TP                  │
│     │  ├─ All exits by rule (not emotion)                         │
│     │  ├─ Risk management enforced (no exceptions)                │
│     │  ├─ Capital usage within limits                             │
│     │  └─ Generate daily report                                   │
│     │                                                             │
│     └─ Weekly performance review:                                 │
│        ├─ Compare live results vs backtest                        │
│        ├─ Analyze any large deviations                            │
│        ├─ Review risk events (if any)                             │
│        └─ Determine if system adjustments needed                  │
│                                                                    │
│  4. Kill Switches (Safety mechanisms)                             │
│     ├─ Manual kill switch (trader can stop trading anytime)       │
│     ├─ Automatic DD stop (no trading if DD > 25%)                 │
│     ├─ Time-based stop (no trading outside market hours)          │
│     ├─ Error-based stop (if 3 consecutive errors, stop)           │
│     └─ All switches logged and audited                            │
│                                                                    │
│  Duration: Continuous, indefinite                                 │
│  Account: Live real money account                                 │
│  Capital: Starts at $25k, grows/shrinks based on P&L              │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

Live Trading Checklist:
✅ Python signal generation error-free for 30+ days
✅ Paper trading results within ±5% of backtest
✅ All alerts configured and tested
✅ Kill switches ready and tested
✅ Team trained on manual intervention
✅ Broker account verified and funded
✅ First week: reduced capital (max 10 trades/day)
✅ Second week: normal operation (no trade limits)
✅ Daily compliance reports generated
```

---

## 3. DATA FLOW DIAGRAM

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        UNIFIED DATA FLOW                                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  External Data Sources                                                   │
│  ├─ MT5 Live Feed (H1 OHLC)                                              │
│  ├─ Historical OHLC (100k bars)                                          │
│  └─ Broker Account Data                                                  │
│          ↓                                                               │
│  ┌──────────────────────────────────────────────────────────────┐        │
│  │ Python Signal Engine                                         │        │
│  ├──────────────────────────────────────────────────────────────┤        │
│  │                                                              │        │
│  │  Data Ingestion → Indicators → Structures → Signals          │        │
│  │  ↓               ↓             ↓           ↓                 │        │
│  │  Load OHLC   Calc ATR,    Detect BOS    Confluence           │        │
│  │  100k bars   RSI, EMA     FVG, CHOCH    check                │        │
│  │              Momentum     OB, Swings    (2+ signals)         │        │
│  │                                                              │        │
│  │  Features → ML Filter → Risk Check → Export                  │        │
│  │  ↓          ↓           ↓            ↓                       │        │
│  │  30 feat    P(win)      Sizing,      Signal JSON/CSV         │        │
│  │  vectors    ≥ 0.60?     State?       + all metadata          │        │
│  │                                                              │        │
│  └──────────────────────────────────────────────────────────────┘        │
│          ↓                                                               │
│  Bridge Layer (Choose one or both)                                       │
│  ├─ Method A: MT5 API (Primary)                                          │
│  │  └─→ Direct mt5.order_send() calls                                    │
│  │      (Latency: <10ms)                                                 │
│  │                                                                       │
│  └─ Method B: CSV Files (Fallback + Backtest)                            │
│     ├─ Write: signals.csv (Python → MT5)                                 │
│     └─ Read: trade_results.csv (MT5 → Python)                            │
│        (Latency: 50-200ms)                                               │
│          ↓                                                               │
│  ┌──────────────────────────────────────────────────────────────┐        │
│  │ MT5 EA: SMC_SYSTEMS_BRIDGE.mq5                               │        │
│  ├──────────────────────────────────────────────────────────────┤        │
│  │                                                              │        │
│  │  Receive Signal                                              │        │
│  │  ├─ Parse (JSON or CSV)                                     │        │
│  │  ├─ Validate schema                                         │        │
│  │  └─ Verify SL/TP placement                                  │        │
│  │          ↓                                                  │        │
│  │  Place Order                                                │        │
│  │  ├─ BUY/SELL at market                                      │        │
│  │  ├─ SL at sl_price                                          │        │
│  │  ├─ TP at tp_price                                          │        │
│  │  └─ Comment = signal_id                                     │        │
│  │          ↓                                                  │        │
│  │  Monitor Position                                           │        │
│  │  ├─ Every bar: track price                                  │        │
│  │  ├─ Calculate MFE/MAE                                       │        │
│  │  └─ Check for exits (TP hit or SL hit)                      │        │
│  │          ↓                                                  │        │
│  │  Exit Trade                                                 │        │
│  │  ├─ Close at exit_price                                     │        │
│  │  ├─ Record exit_reason                                      │        │
│  │  ├─ Calculate P&L                                           │        │
│  │  └─ Log result                                              │        │
│  │          ↓                                                  │        │
│  │  Export Result (to Python)                                  │        │
│  │  ├─ Method A: Via API return                                │        │
│  │  └─ Method B: Write trade_results.csv                       │        │
│  │                                                              │        │
│  └──────────────────────────────────────────────────────────────┘        │
│          ↓                                                               │
│  ┌──────────────────────────────────────────────────────────────┐        │
│  │ Python Analysis & Storage                                    │        │
│  ├──────────────────────────────────────────────────────────────┤        │
│  │                                                              │        │
│  │  Read Results (from MT5)                                     │        │
│  │  ├─ Parse trade_results.csv OR API return                   │        │
│  │  ├─ Validate data integrity                                 │        │
│  │  └─ Store in database                                       │        │
│  │          ↓                                                  │        │
│  │  Calculate Metrics                                          │        │
│  │  ├─ Win rate, Profit factor, Expectancy                     │        │
│  │  ├─ Drawdown, MFE/MAE analysis                              │        │
│  │  ├─ Monthly/symbol breakdowns                               │        │
│  │  └─ Compare vs backtest expectations                        │        │
│  │          ↓                                                  │        │
│  │  Generate Reports                                           │        │
│  │  ├─ Daily summary                                           │        │
│  │  ├─ Weekly performance                                      │        │
│  │  ├─ Monthly compliance                                      │        │
│  │  └─ Alerts if issues detected                               │        │
│  │          ↓                                                  │        │
│  │  Storage / Logging                                          │        │
│  │  ├─ SQL database (trades, results)                          │        │
│  │  ├─ JSON files (metrics, reports)                           │        │
│  │  ├─ CSV exports (for external analysis)                     │        │
│  │  └─ Audit trail (all decisions logged)                      │        │
│  │                                                              │        │
│  └──────────────────────────────────────────────────────────────┘        │
│          ↓                                                               │
│  Dashboard / Alerts                                                      │
│  ├─ Real-time status                                                     │
│  ├─ P&L tracking                                                         │
│  ├─ Risk state                                                           │
│  └─ Error/warning alerts                                                 │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 4. SYSTEM COMPONENTS & RESPONSIBILITIES

| Component | Location | Responsible For | Input | Output |
|-----------|----------|-----------------|-------|--------|
| **Data Loader** | Python | OHLC ingestion | MT5 API / Parquet | DataFrame[OHLC] |
| **Indicators** | Python | ATR, RSI, EMA calc | OHLC | numpy arrays |
| **BOS Detector** | Python | Swing break detection | OHLC + Swings | BOS list |
| **FVG Detector** | Python | Gap detection | OHLC | FVG list |
| **Structural SL** | Python | Origin swing + sweep | OHLC + BOS | SL price ✅ Fixed |
| **Signal Generator** | Python | Confluence check | All structures | Signal list |
| **Feature Extractor** | Python | 30 ML features | All signals | Feature matrix[30] |
| **ML Engine** | Python | P(win) prediction | Features | Scores[0-1] |
| **Risk Governor** | Python | Sizing + state | Signals + Account | Position params |
| **Signal Exporter** | Python | Export to MT5 | Signals + Sizing | JSON/CSV |
| **MT5 EA** | MQL5 | Order execution | JSON/CSV signals | Trade results |
| **Position Monitor** | MQL5 | Track positions | Live prices | MFE/MAE + exits |
| **Result Logger** | Python | Result storage | Trade results | Metrics |
| **Dashboard** | Python | Monitoring | All data | Real-time UI |

---

## 5. DEPLOYMENT ARCHITECTURE

```
┌─────────────────────────────────────────────────┐
│ PRODUCTION DEPLOYMENT TOPOLOGY                  │
├─────────────────────────────────────────────────┤
│                                                 │
│  Option 1: Single Machine (Recommended)         │
│  ┌───────────────────────────────────────┐     │
│  │ Windows/Linux Machine                 │     │
│  ├─ Python (SMC SYSTEMS)                 │     │
│  │  ├─ Signal generation                 │     │
│  │  ├─ Feature extraction                │     │
│  │  ├─ ML inference                      │     │
│  │  ├─ Risk management                   │     │
│  │  ├─ Bridge module                     │     │
│  │  └─ Monitoring dashboard              │     │
│  │                                       │     │
│  ├─ MetaTrader 5                         │     │
│  │  ├─ EA: SMC_SYSTEMS_BRIDGE.mq5       │     │
│  │  ├─ Real account connection           │     │
│  │  ├─ Order execution                   │     │
│  │  └─ Position tracking                 │     │
│  │                                       │     │
│  └─ Shared Filesystem                    │     │
│     ├─ signals.csv (exchange data)       │     │
│     ├─ results.csv (trade results)       │     │
│     └─ logs/ (audit trail)               │     │
│  └───────────────────────────────────────┘     │
│                                                 │
│  Option 2: Two Machines (Advanced)              │
│  ┌───────────────────────────┐                 │
│  │ Machine A: Python Server  │                 │
│  ├─ Python (SMC SYSTEMS)     │                 │
│  ├─ Signal generation        │                 │
│  ├─ Bridge module            │                 │
│  └─ Network socket server    │                 │
│     └───────────────────────────────────┐      │
│                                         │      │
│  ┌───────────────────────────────────────┐    │
│  │ Machine B: MT5 Terminal               │    │
│  ├─ MetaTrader 5                         │    │
│  ├─ EA: SMC_SYSTEMS_BRIDGE.mq5          │    │
│  ├─ Network socket client                │    │
│  └─ Order execution                      │    │
│     └───────────────────────────────────┘    │
│                                                 │
└─────────────────────────────────────────────────┘

Recommended: Option 1 (Single Machine)
├─ Simplest implementation
├─ Lowest latency
├─ No network issues
└─ Easiest troubleshooting
```

---

## 6. SUCCESS METRICS

| Metric | Target | Acceptable | Critical |
|--------|--------|-----------|----------|
| Signal latency | <10ms | <100ms | >500ms 🚨 |
| Order placement success rate | 100% | 99.5% | <99% 🚨 |
| SL/TP execution accuracy | 100% | ±1 pip | >2 pips 🚨 |
| Risk management enforcement | 100% | 99.9% | <99% 🚨 |
| Audit trail completion | 100% | 100% | <100% 🚨 |
| System uptime | 99.9% | 99.5% | <99% 🚨 |
| Error alerts response | <5 min | <15 min | >1 hour 🚨 |
| Backtest vs Live match | ±5% | ±10% | >15% 🚨 |

---

## NEXT STEPS

This architecture serves as the foundation for:
1. ✅ FASE 3 (completed - this document)
2. 🔄 FASE 4: Data contract schemas (signal_schema.json, feature_schema.json)
3. 🔄 FASE 5: Bridge module implementation (integration/mt5_bridge/)
4. 🔄 FASE 6: MQL5 EA development (SMC_SYSTEMS_BRIDGE.mq5)
5. 🔄 FASE 7: Backtest validation
6. 🔄 FASE 8: Implementation roadmap
