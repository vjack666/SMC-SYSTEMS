# Signal Flow Map
## How BOS, FVG, CHOCH, OB, and Structural SL Create Trading Signals

**Scope**: Complete signal generation pipeline from raw OHLC to trade-ready entry  
**Destination**: MT5 Integration - Signal Export Layer  
**Current Status**: Production-tested on Experiment F (14,344 trades validated)

---

## 1. SIGNAL GENERATION PIPELINE (High-level)

```
Raw OHLC (100k bars)
    ↓
Indicators (ATR, RSI, EMA, Momentum)
    ↓
Structure Detection (Swing High/Low)
    ↓
BOS Detection (Break of Structure)
    ↓
FVG Detection (Fair Value Gap)
    ↓
CHOCH Detection (Change of Character)
    ↓
OB Detection (Order Block)
    ↓
CONFLUENCE CHECK (2+ signals align?)
    ↓
Structural SL Calculation (Origin Swing + Sweep)
    ↓
Signal Generated ✅
    ↓
ML Quality Filter (P(win) ≥ 0.60?)
    ↓
Risk Management (Position sizing, state check)
    ↓
EXPORT TO MT5 ✅
```

---

## 2. DETAILED SIGNAL COMPONENTS

### 2.1 SWING DETECTION

**Purpose**: Identify local price extrema for structure formation  
**Module**: `modules/swing/detector.py`  
**Output**: Swing High (SH), Swing Low (SL) list with bar indices

**Algorithm**:
```
For each bar:
  Swing High = bar where high > (previous N bars) AND (next N bars)
  Swing Low = bar where low < (previous N bars) AND (next N bars)
  Lookback window = 5 bars typical
```

**Example**:
```
Bar 100: High 1.2050 - SWING HIGH (1.2020, 1.2045, 1.2050, 1.2040, 1.2035)
Bar 105: Low 1.1980 - SWING LOW (1.2010, 1.1995, 1.1980, 1.1985, 1.1990)
```

**Exported Data**:
```json
{
  "swing_type": "HIGH",
  "swing_price": 1.2050,
  "swing_bar_index": 100,
  "swing_age_bars": 5,
  "is_broken": false
}
```

---

### 2.2 BOS DETECTION (Break of Structure)

**Purpose**: Entry signal when price breaks a swing structure  
**Module**: `modules/bos/detector.py`  
**Prerequisite**: Valid Swing High or Swing Low

**Algorithm** (LONG):
```
1. Identify Swing High
2. Monitor for price close BELOW the swing low
3. If closes below: BOS confirmed (structural break)
4. Entry trigger: Next candle open > swing low OR close > swing low
```

**Algorithm** (SHORT):
```
1. Identify Swing Low
2. Monitor for price close ABOVE the swing high
3. If closes above: BOS confirmed (structural break)
4. Entry trigger: Next candle open < swing high OR close < swing high
```

**Exported Data**:
```json
{
  "signal_type": "BOS",
  "direction": 1,  // 1=LONG, -1=SHORT
  "origin_swing_price": 1.2050,
  "origin_swing_bar": 100,
  "break_price": 1.1980,
  "break_bar": 105,
  "bos_distance_atr": 2.5,
  "bos_strength": 0.75,  // 0-1 scale
  "entry_price": 1.1985,
  "entry_bar": 106
}
```

**Signal Quality Factors**:
- Distance from swing: Greater = stronger (more conviction)
- Number of candles to break: Faster = stronger
- Volume during break: More = stronger (if available)
- Follow-through candle size: Larger = stronger

---

### 2.3 FVG DETECTION (Fair Value Gap)

**Purpose**: Identify liquidity gaps for entry refinement  
**Module**: `modules/fvg/detector.py`  
**Prerequisite**: None (independent detector)

**Algorithm**:
```
For each 3-candle sequence:
  If (candle1_high < candle3_low) OR (candle3_high < candle1_low):
    → FVG detected (gap between candles 1 and 3)
    → FVG boundaries = [min(candle1_high, candle3_high), max(candle1_low, candle3_low)]
    → FVG size in pips = absolute difference
    → Age = current_bar - candle3_bar
```

**Example** (LONG setup):
```
Candle 1: High 1.2100, Low 1.2050
Candle 2: High 1.2090, Low 1.2040  (doji)
Candle 3: High 1.1990, Low 1.1950  (big down move)

FVG formed: Gap between 1.2050 (C1 low) and 1.1990 (C3 high)
FVG boundaries: 1.1990 - 1.2050 (gap region)
FVG size: 60 pips
```

**Exported Data**:
```json
{
  "signal_type": "FVG",
  "direction": 1,  // gap context
  "fvg_top": 1.2050,
  "fvg_bottom": 1.1990,
  "fvg_size_pips": 60,
  "fvg_age_bars": 3,
  "fvg_filled": false,
  "fvg_strength": 0.85,  // size relative to ATR
  "confluence_with_bos": true
}
```

**Signal Quality Factors**:
- Larger FVG = stronger (more liquidity to sweep)
- Younger FVG = stronger (not yet mitigation)
- FVG near BOS = strong confluence
- Multiple FVGs stacking = very strong

---

### 2.4 CHOCH DETECTION (Change of Character)

**Purpose**: Identify structural regime shifts  
**Module**: `modules/choch/detector.py`  
**Prerequisite**: Trend classification

**Algorithm**:
```
1. Classify current trend: Trending UP, Trending DOWN, Ranging
2. Look for character shift:
   - Lower Highs becoming Equal/Higher Highs → character shift
   - Higher Lows becoming Equal/Lower Lows → character shift
3. If shift detected: CHOCH event recorded
```

**Example** (Trending UP → Ranging):
```
Previous swings: SH 1.2050, SH 1.2070, SH 1.2090 (higher highs - trending up)
New swings: SH 1.2085, SH 1.2080, SH 1.2082 (equal highs - character shift)
CHOCH detected at bar where first equal SH appears
```

**Exported Data**:
```json
{
  "signal_type": "CHOCH",
  "previous_character": "Trending UP",
  "new_character": "Ranging",
  "choch_bar": 120,
  "structural_severity": 3.5,  // 1-5 scale
  "confluence_count": 2,  // How many other signals align
  "entry_side_preference": "SHORT"  // Implied from character shift
}
```

**Signal Quality Factors**:
- Clear previous trend before shift = strong
- Multiple confluent signals at shift = strong
- Volume expansion on shift = strong
- Follow-through candles confirming new character = strong

---

### 2.5 OB DETECTION (Order Block)

**Purpose**: Identify liquidity concentration zones for entry positioning  
**Module**: `modules/ob/detector.py`  
**Prerequisite**: BOS or trend detection

**Algorithm**:
```
1. Identify candle BEFORE structural break (OB candle)
2. OB boundaries = high and low of that candle
3. Strength = how strongly price was rejected from OB
4. Integrity = has price returned to respect OB since formation
```

**Example** (LONG OB):
```
Pre-BOS market context: Candle consolidates at 1.2020-1.2040
Next candle: Breaks down to 1.1950 (BOS)
OB zone: 1.2020 (high) - 1.2010 (low)
Strength: Candle closed at 1.1950 (far from OB) = strong OB
Later: Price returns to test 1.2015 (respects OB high) = OB integrity maintained
```

**Exported Data**:
```json
{
  "signal_type": "OB",
  "ob_high": 1.2040,
  "ob_low": 1.2010,
  "ob_size_pips": 30,
  "ob_strength": 0.90,  // how strong rejection
  "ob_integrity": true,  // still respected
  "formed_bar": 104,
  "confluence_type": "FVG + OB stacking",
  "liquidity_premium": 0.88  // strength indicator
}
```

**Signal Quality Factors**:
- Larger OB zone = more liquidity to sweep
- Stronger rejection (larger candle) = stronger OB
- OB still intact (not filled) = stronger
- Multiple OBs stacking = extremely strong

---

### 2.6 STRUCTURAL SL CALCULATION

**Purpose**: Place stop loss at origin swing + liquidity sweep  
**Module**: `modules/structural_sl/detector.py`  
**Prerequisite**: Identified entry signal (BOS + one more confirmation)

**Algorithm** (FIXED - Phase 0):

```
LONG Setup:
1. Find signal entry bar
2. Look back N bars (default 20, extended to 40 if needed)
3. Find MINIMUM LOW in lookback (origin swing for LONG)
4. Check if minimum was swept (price went lower, then returned)
5. Structural SL = origin_low - buffer (1-2 pips)

SHORT Setup:
1. Find signal entry bar
2. Look back N bars (default 20, extended to 40 if needed)
3. Find MAXIMUM HIGH in lookback (origin swing for SHORT)
4. Check if maximum was swept (price went higher, then returned)
5. Structural SL = origin_high + buffer (1-2 pips)
```

**Validation Logic** (from Experiment F fix):
```python
# Must satisfy:
for LONG: sl_price < entry_price (stop BELOW entry)
for SHORT: sl_price > entry_price (stop ABOVE entry)

# If not satisfied, try extended lookback (2x window)
# If still not satisfied, mark trade invalid (skip)

# Validate stop_distance_atr is finite (not NaN)
```

**Exported Data**:
```json
{
  "structural_sl": {
    "origin_swing_type": "SWING_LOW",
    "origin_swing_price": 1.1950,
    "origin_swing_bar": 95,
    "sweep_bar": 102,
    "sweep_intensity": 0.92,  // how deep past origin
    "lookback_bars_used": 20,
    "sl_price": 1.1945,
    "sl_distance_pips": 40,
    "sl_distance_atr": 2.3,  // normalized to ATR
    "validity_check": "VALID",
    "is_extended_lookback": false
  }
}
```

**Critical Implementation Notes** (from Phase 0 forensic audit):
- ✅ LONG uses MIN LOW (was broken: used MAX HIGH)
- ✅ SHORT uses MAX HIGH (was broken: used MIN LOW)
- ✅ Extended lookback for edge cases (prices retrace in FVG)
- ✅ Final validation: stop on correct side of entry
- ✅ Result: 0 invalid stops in Experiment F Fixed

---

## 3. CONFLUENCE SCORING

**Purpose**: Generate entry only when 2+ signals align  
**Module**: Signal confluence logic in main orchestrator

**Scoring Weights**:
```
Base signal: 100 points
+ BOS detected: +30 points
+ FVG detected: +25 points
+ OB detected: +20 points
+ CHOCH detected: +15 points
+ Structural SL valid: +10 points
+ ML score > 0.70: +15 points

Min confluence score: 120 points (at least 2 signals)
```

**Confluence Examples**:

**Example 1** (HIGH confidence - 3 signals):
```
✅ BOS detected: 130 points
✅ FVG detected: 155 points
✅ OB detected: 175 points
✅ Structural SL valid: 185 points
✅ ML score 0.75: 200 points
→ Entry signal strength = 200/200 = 1.0 (maximum confidence)
```

**Example 2** (MEDIUM confidence - 2 signals):
```
✅ BOS detected: 130 points
✅ FVG detected: 155 points
❌ OB not detected: 155 points
✅ Structural SL valid: 165 points
⚠️ ML score 0.62: 180 points
→ Entry signal strength = 0.9 (good, accept)
```

**Example 3** (LOW - rejected):
```
✅ BOS detected: 130 points
❌ FVG not detected: 130 points
❌ OB not detected: 130 points
✅ Structural SL valid: 140 points
❌ ML score 0.55: 140 points
→ Confluence score = 140 < 120 threshold (REJECTED)
```

---

## 4. SIGNAL EXPORT FORMAT (to MT5)

### 4.1 Single Signal JSON Schema

```json
{
  "signal_id": "EURUSD_20260601_153000",
  "timestamp_utc": "2026-06-01T15:30:00Z",
  "symbol": "EURUSD",
  
  "entry": {
    "direction": 1,
    "entry_price": 1.09850,
    "entry_bar_index": 12847,
    "session": "European",
    "market_regime": "Trending UP"
  },
  
  "risk_management": {
    "sl_price": 1.09750,
    "tp_price": 1.10050,
    "risk_r": 0.005,
    "potential_reward_r": 0.010,
    "rr_ratio": 2.0,
    "position_size_usd": 125.0,
    "risk_per_trade_usd": 125.0
  },
  
  "structural_components": {
    "bos": {
      "detected": true,
      "origin_swing_price": 1.09900,
      "bos_strength": 0.85,
      "distance_atr": 1.2
    },
    "fvg": {
      "detected": true,
      "fvg_top": 1.09900,
      "fvg_bottom": 1.09800,
      "age_bars": 3,
      "filled": false
    },
    "ob": {
      "detected": true,
      "ob_high": 1.09880,
      "ob_low": 1.09840,
      "strength": 0.78
    },
    "choch": {
      "detected": false
    },
    "structural_sl": {
      "origin_swing_price": 1.09750,
      "sweep_intensity": 0.88,
      "validity": "VALID"
    }
  },
  
  "ml_filter": {
    "confidence_score": 0.72,
    "keep_trade": true,
    "top_features": ["bos_strength", "fvg_age", "ml_momentum"]
  },
  
  "quality_metrics": {
    "confluence_score": 0.94,
    "overall_signal_strength": 0.88,
    "backtest_historical_winrate": 0.62
  }
}
```

### 4.2 Batch Export (Multiple Signals)

```json
{
  "export_timestamp": "2026-06-01T15:30:00Z",
  "export_version": "1.0",
  "system_version": "SMC_SYSTEMS_v2.5",
  "signals": [
    { /* signal object 1 */ },
    { /* signal object 2 */ },
    { /* signal object 3 */ }
  ],
  "summary": {
    "total_signals": 3,
    "total_buys": 2,
    "total_sells": 1,
    "average_confidence": 0.78,
    "export_status": "SUCCESS"
  }
}
```

---

## 5. ENTRY TIMING RULES

### 5.1 Entry Bar Definition

**Entry happens on**: First bar AFTER structure completion  
**Specific Rules**:

**LONG Entry**:
```
Bar N-1: Structure forms (BOS below swing low)
Bar N: Entry bar
  - Must have valid FVG and/or OB
  - Structural SL calculated
  - Entry price = any price > order block low
  - Typical entry = bar N open or close
```

**SHORT Entry**:
```
Bar N-1: Structure forms (BOS above swing high)
Bar N: Entry bar
  - Must have valid FVG and/or OB
  - Structural SL calculated
  - Entry price = any price < order block high
  - Typical entry = bar N open or close
```

**MT5 Implementation**:
```mql5
// In EA: on each H1 bar close
if (current_bar_time == signal.entry_bar_time) {
  if (signal.direction == BUY) {
    open_buy_order(signal.entry_price, signal.sl_price, signal.tp_price);
  }
}
```

---

## 6. SIGNAL FLOW STATISTICS (Experiment F Fixed)

| Stage | Input Signals | Output Signals | Retention % |
|-------|--------------|----------------|------------|
| Raw entries generated | 14,804 | 14,804 | 100% |
| BOS+FVG+OB filtered | 14,804 | 14,804 | 100% (already in signal) |
| Structural SL valid | 14,804 | 14,804 | 100% ✅ |
| ML confidence ≥ 0.60 | 14,804 | ~8,900 | 60% |
| Risk state allows | 8,900 | 8,900 | 100% (state agnostic) |
| **Final trades** | 14,804 | 14,344 | 96.9% |

**Note**: Experiment F shows 14,344 final trades (96.9% of 14,804 signals) means ~460 filtered by ML + position overlaps.

---

## 7. VALIDATION CHECKLIST FOR SIGNAL EXPORT

Before exporting signal to MT5, verify:

- [ ] Signal ID unique (timestamp + symbol)
- [ ] Direction is ±1 (not 0 or other)
- [ ] Entry price is finite (not NaN, not inf)
- [ ] SL price on correct side of entry:
  - [ ] LONG: sl_price < entry_price
  - [ ] SHORT: sl_price > entry_price
- [ ] TP price on correct side of entry:
  - [ ] LONG: tp_price > entry_price
  - [ ] SHORT: tp_price < entry_price
- [ ] RR ratio ≥ 2.0
- [ ] ML confidence ≥ 0.60
- [ ] Confluence score ≥ 0.80
- [ ] All timestamps in UTC
- [ ] Symbol in [EURUSD, GBPUSD, XAUUSD]
- [ ] JSON schema validates without errors

---

## 8. NEXT STEPS

This signal flow will be:
1. ✅ Documented here (FASE 1)
2. 🔄 Integrated into FASE 5 bridge module (signal_exporter.py)
3. 🔄 Exposed via JSON schema (FASE 4)
4. 🔄 Consumed by MQL5 EA (FASE 6)
5. 🔄 Validated in backtest (FASE 7)
