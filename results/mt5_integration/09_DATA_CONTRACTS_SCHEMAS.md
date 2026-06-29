# FASE 4: Data Contracts & Schemas
## Exact Format Specifications for Python ↔ MT5 Communication

**Scope**: Complete schema definitions for signal exchange and result logging  
**Purpose**: Ensure Python and MT5 EA can communicate with zero ambiguity  
**Format**: JSON Schema + CSV Schema + API Specifications

---

## 1. SIGNAL SCHEMA (Python → MT5)

### 1.1 JSON Signal Format (Method A - MT5 Package)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SMC Trading Signal",
  "type": "object",
  "required": [
    "signal_id",
    "timestamp_utc",
    "symbol",
    "direction",
    "entry_price",
    "sl_price",
    "tp_price",
    "position_size_lots",
    "risk_usd",
    "ml_score"
  ],
  "properties": {
    "signal_id": {
      "type": "string",
      "description": "Unique identifier for signal",
      "pattern": "^[A-Z]{6}_[0-9]{8}_[0-9]{6}$",
      "example": "EURUSD_20260601_153000"
    },
    "timestamp_utc": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 UTC timestamp when signal was generated",
      "example": "2026-06-01T15:30:00Z"
    },
    "symbol": {
      "type": "string",
      "enum": ["EURUSD", "GBPUSD", "XAUUSD"],
      "description": "Trading symbol"
    },
    "direction": {
      "type": "integer",
      "enum": [1, -1],
      "description": "Trade direction (1=LONG/BUY, -1=SHORT/SELL)"
    },
    "entry_price": {
      "type": "number",
      "description": "Entry price (market order price)",
      "minimum": 0.00001,
      "maximum": 999999,
      "example": 1.09850
    },
    "sl_price": {
      "type": "number",
      "description": "Stop loss price (must be on correct side of entry)",
      "minimum": 0.00001,
      "maximum": 999999,
      "example": 1.09750
    },
    "tp_price": {
      "type": "number",
      "description": "Take profit price (1:2.0 RR ratio from entry)",
      "minimum": 0.00001,
      "maximum": 999999,
      "example": 1.10050
    },
    "position_size_lots": {
      "type": "number",
      "description": "Position size in lots (typically 0.01 - 5.0 range)",
      "minimum": 0.01,
      "maximum": 100,
      "example": 1.25
    },
    "risk_usd": {
      "type": "number",
      "description": "Risk amount in USD (fixed at 0.5% of capital typically)",
      "minimum": 10,
      "maximum": 1000,
      "example": 125.0
    },
    "reward_usd": {
      "type": "number",
      "description": "Potential reward in USD (always 2x risk for RR 1:2.0)",
      "minimum": 20,
      "maximum": 2000,
      "example": 250.0
    },
    "rr_ratio": {
      "type": "number",
      "description": "Risk-Reward ratio (minimum 2.0)",
      "minimum": 2.0,
      "example": 2.0
    },
    "ml_score": {
      "type": "number",
      "description": "ML confidence score (P(win) probability)",
      "minimum": 0.60,
      "maximum": 1.0,
      "example": 0.72
    },
    "ml_confidence": {
      "type": "number",
      "description": "Confidence in prediction (0-1 scale)",
      "minimum": 0,
      "maximum": 1,
      "example": 0.88
    },
    "confluence_alignment": {
      "type": "number",
      "description": "How well signals align (0-1 scale)",
      "minimum": 0,
      "maximum": 1,
      "example": 0.92
    },
    "signal_strength": {
      "type": "number",
      "description": "Overall signal strength (0-1 scale)",
      "minimum": 0,
      "maximum": 1,
      "example": 0.85
    },
    "session": {
      "type": "string",
      "enum": ["ASIAN", "EUROPEAN", "AMERICAN", "OVERLAP"],
      "description": "Market session",
      "example": "EUROPEAN"
    },
    "market_regime": {
      "type": "string",
      "enum": ["TRENDING", "RANGING", "VOLATILE", "CONSOLIDATION"],
      "description": "Current market regime",
      "example": "TRENDING"
    },
    "structural_components": {
      "type": "object",
      "description": "Details of all structural signals",
      "properties": {
        "bos": {
          "type": "object",
          "properties": {
            "detected": {"type": "boolean"},
            "strength": {"type": "number", "minimum": 0, "maximum": 1},
            "distance_atr": {"type": "number"},
            "origin_swing_price": {"type": "number"}
          },
          "required": ["detected"]
        },
        "fvg": {
          "type": "object",
          "properties": {
            "detected": {"type": "boolean"},
            "fvg_top": {"type": "number"},
            "fvg_bottom": {"type": "number"},
            "size_atr": {"type": "number"},
            "age_bars": {"type": "integer"}
          },
          "required": ["detected"]
        },
        "ob": {
          "type": "object",
          "properties": {
            "detected": {"type": "boolean"},
            "strength": {"type": "number", "minimum": 0, "maximum": 1}
          },
          "required": ["detected"]
        },
        "choch": {
          "type": "object",
          "properties": {
            "detected": {"type": "boolean"},
            "severity": {"type": "number"}
          },
          "required": ["detected"]
        },
        "structural_sl": {
          "type": "object",
          "properties": {
            "origin_swing_price": {"type": "number"},
            "origin_swing_bar": {"type": "integer"},
            "sweep_intensity": {"type": "number", "minimum": 0, "maximum": 1},
            "stop_distance_atr": {"type": "number"}
          },
          "required": ["origin_swing_price", "sweep_intensity"]
        }
      }
    },
    "entry_bar_index": {
      "type": "integer",
      "description": "Bar number in MT5 (for backtesting reference)",
      "example": 12847
    },
    "risk_state": {
      "type": "string",
      "enum": ["NORMAL", "CAUTION", "DEFENSIVE", "LOCKDOWN"],
      "description": "Account risk state at time of signal",
      "example": "NORMAL"
    },
    "account_balance_at_signal": {
      "type": "number",
      "description": "Account balance when signal was generated",
      "example": 25000.0
    },
    "drawdown_pct_at_signal": {
      "type": "number",
      "description": "Current drawdown % when signal generated",
      "example": 8.5
    }
  },
  "additionalProperties": false
}
```

### 1.2 Example Signal JSON

```json
{
  "signal_id": "EURUSD_20260601_153000",
  "timestamp_utc": "2026-06-01T15:30:00Z",
  "symbol": "EURUSD",
  "direction": 1,
  "entry_price": 1.09850,
  "sl_price": 1.09750,
  "tp_price": 1.10050,
  "position_size_lots": 1.25,
  "risk_usd": 125.0,
  "reward_usd": 250.0,
  "rr_ratio": 2.0,
  "ml_score": 0.72,
  "ml_confidence": 0.88,
  "confluence_alignment": 0.92,
  "signal_strength": 0.85,
  "session": "EUROPEAN",
  "market_regime": "TRENDING",
  "structural_components": {
    "bos": {
      "detected": true,
      "strength": 0.85,
      "distance_atr": 1.2,
      "origin_swing_price": 1.09900
    },
    "fvg": {
      "detected": true,
      "fvg_top": 1.09900,
      "fvg_bottom": 1.09800,
      "size_atr": 0.85,
      "age_bars": 3
    },
    "ob": {
      "detected": true,
      "strength": 0.78
    },
    "choch": {
      "detected": false
    },
    "structural_sl": {
      "origin_swing_price": 1.09750,
      "origin_swing_bar": 95,
      "sweep_intensity": 0.88,
      "stop_distance_atr": 2.3
    }
  },
  "entry_bar_index": 12847,
  "risk_state": "NORMAL",
  "account_balance_at_signal": 25000.0,
  "drawdown_pct_at_signal": 8.5
}
```

### 1.3 CSV Signal Format (Method B - CSV Bridge)

**File**: signals.csv

```
signal_id,timestamp_utc,symbol,direction,entry_price,sl_price,tp_price,position_size_lots,risk_usd,reward_usd,rr_ratio,ml_score,ml_confidence,confluence_alignment,signal_strength,session,market_regime,bos_detected,bos_strength,fvg_detected,fvg_size_atr,ob_detected,ob_strength,choch_detected,structural_sl_price,sweep_intensity,stop_distance_atr,entry_bar_index,risk_state,account_balance,drawdown_pct

EURUSD_20260601_153000,2026-06-01T15:30:00Z,EURUSD,1,1.09850,1.09750,1.10050,1.25,125.00,250.00,2.0,0.72,0.88,0.92,0.85,EUROPEAN,TRENDING,1,0.85,1,0.85,1,0.78,0,1.09750,0.88,2.3,12847,NORMAL,25000.0,8.5

GBPUSD_20260601_154500,2026-06-01T15:45:00Z,GBPUSD,-1,1.55200,1.55400,1.54800,1.00,125.00,250.00,2.0,0.68,0.82,0.88,0.78,EUROPEAN,TRENDING,1,0.80,1,0.92,0,0.0,0,1.55400,0.91,2.1,12848,NORMAL,24875.0,8.6
```

**Column Specifications**:

| Column | Type | Range | Description |
|--------|------|-------|-------------|
| signal_id | string | - | SYMBOL_YYYYMMDD_HHMMSS |
| timestamp_utc | datetime | - | ISO 8601 format |
| symbol | string | EURUSD/GBPUSD/XAUUSD | Trading pair |
| direction | int | 1 or -1 | Trade direction |
| entry_price | float | 0.00001-999999 | Entry level |
| sl_price | float | 0.00001-999999 | Stop loss level |
| tp_price | float | 0.00001-999999 | Take profit level |
| position_size_lots | float | 0.01-100 | Lot size |
| risk_usd | float | 10-1000 | Risk amount |
| reward_usd | float | 20-2000 | Potential reward |
| rr_ratio | float | ≥2.0 | Risk-reward ratio |
| ml_score | float | 0.60-1.0 | ML confidence |
| ml_confidence | float | 0-1 | Prediction confidence |
| confluence_alignment | float | 0-1 | Signal alignment |
| signal_strength | float | 0-1 | Overall strength |
| session | string | ASIAN/EUR/US/OVERLAP | Market session |
| market_regime | string | TREND/RANGE/VOLAT | Market state |
| bos_detected | bool | 0/1 | BOS present? |
| bos_strength | float | 0-1 | BOS quality |
| fvg_detected | bool | 0/1 | FVG present? |
| fvg_size_atr | float | ≥0 | Gap magnitude |
| ob_detected | bool | 0/1 | OB present? |
| ob_strength | float | 0-1 | OB quality |
| choch_detected | bool | 0/1 | CHOCH present? |
| structural_sl_price | float | 0.00001-999999 | SL placement |
| sweep_intensity | float | 0-1 | Sweep depth |
| stop_distance_atr | float | ≥0 | SL distance in ATR |
| entry_bar_index | int | ≥0 | Bar number |
| risk_state | string | NORMAL/CAUT/DEF/LOCK | Risk mode |
| account_balance | float | ≥0 | Account capital |
| drawdown_pct | float | 0-100 | Current DD% |

---

## 2. TRADE RESULT SCHEMA (MT5 → Python)

### 2.1 JSON Trade Result Format

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SMC Trade Result",
  "type": "object",
  "required": [
    "signal_id",
    "symbol",
    "direction",
    "entry_price",
    "entry_time_utc",
    "exit_price",
    "exit_time_utc",
    "exit_reason",
    "pnl_usd",
    "pnl_r"
  ],
  "properties": {
    "signal_id": {
      "type": "string",
      "description": "Reference to original signal",
      "example": "EURUSD_20260601_153000"
    },
    "order_id": {
      "type": "integer",
      "description": "MT5 order ticket number",
      "example": 123456789
    },
    "symbol": {
      "type": "string",
      "enum": ["EURUSD", "GBPUSD", "XAUUSD"],
      "description": "Trading symbol"
    },
    "direction": {
      "type": "integer",
      "enum": [1, -1],
      "description": "Trade direction"
    },
    "entry_price": {
      "type": "number",
      "description": "Actual entry price (may differ from planned due to slippage)",
      "example": 1.09851
    },
    "entry_time_utc": {
      "type": "string",
      "format": "date-time",
      "description": "When order was filled",
      "example": "2026-06-01T15:30:05Z"
    },
    "entry_volume_lots": {
      "type": "number",
      "description": "Actual volume executed",
      "example": 1.25
    },
    "exit_price": {
      "type": "number",
      "description": "Exit price (TP hit or SL hit)",
      "example": 1.10051
    },
    "exit_time_utc": {
      "type": "string",
      "format": "date-time",
      "description": "When position closed",
      "example": "2026-06-01T16:45:12Z"
    },
    "exit_reason": {
      "type": "string",
      "enum": ["TP_HIT", "SL_HIT", "MANUAL_CLOSE", "TIMEOUT", "ERROR"],
      "description": "How the trade exited",
      "example": "TP_HIT"
    },
    "holding_bars": {
      "type": "integer",
      "description": "Number of bars held",
      "minimum": 1,
      "maximum": 100,
      "example": 12
    },
    "mfe": {
      "type": "number",
      "description": "Max Favorable Excursion (as % of risk)",
      "example": 2.15
    },
    "mae": {
      "type": "number",
      "description": "Max Adverse Excursion (as % of risk)",
      "example": 0.45
    },
    "pnl_usd": {
      "type": "number",
      "description": "Profit/Loss in USD",
      "example": 250.0
    },
    "pnl_r": {
      "type": "number",
      "description": "Profit/Loss in R (risk units)",
      "example": 2.0
    },
    "slippage_pips": {
      "type": "number",
      "description": "Entry slippage in pips",
      "minimum": -10,
      "maximum": 10,
      "example": 0.1
    },
    "commission_usd": {
      "type": "number",
      "description": "Commission paid",
      "minimum": 0,
      "example": 2.5
    },
    "status": {
      "type": "string",
      "enum": ["CLOSED", "FAILED", "PARTIAL"],
      "description": "Trade completion status",
      "example": "CLOSED"
    }
  },
  "additionalProperties": false
}
```

### 2.2 Example Trade Result

```json
{
  "signal_id": "EURUSD_20260601_153000",
  "order_id": 987654321,
  "symbol": "EURUSD",
  "direction": 1,
  "entry_price": 1.09851,
  "entry_time_utc": "2026-06-01T15:30:05Z",
  "entry_volume_lots": 1.25,
  "exit_price": 1.10051,
  "exit_time_utc": "2026-06-01T16:45:12Z",
  "exit_reason": "TP_HIT",
  "holding_bars": 12,
  "mfe": 2.15,
  "mae": 0.45,
  "pnl_usd": 250.0,
  "pnl_r": 2.0,
  "slippage_pips": 0.1,
  "commission_usd": 2.5,
  "status": "CLOSED"
}
```

### 2.3 CSV Trade Result Format

**File**: trade_results.csv

```
signal_id,order_id,symbol,direction,entry_price,entry_time_utc,entry_volume_lots,exit_price,exit_time_utc,exit_reason,holding_bars,mfe,mae,pnl_usd,pnl_r,slippage_pips,commission_usd,status

EURUSD_20260601_153000,987654321,EURUSD,1,1.09851,2026-06-01T15:30:05Z,1.25,1.10051,2026-06-01T16:45:12Z,TP_HIT,12,2.15,0.45,250.0,2.0,0.1,2.5,CLOSED

GBPUSD_20260601_154500,987654322,GBPUSD,-1,1.55201,2026-06-01T15:45:08Z,1.00,1.55101,2026-06-01T16:52:45Z,SL_HIT,9,-0.85,0.95,-125.0,-1.0,0.08,2.5,CLOSED
```

---

## 3. FEATURE SCHEMA (for ML logging & debugging)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SMC Feature Vector",
  "description": "30 ML features extracted at entry time",
  "type": "object",
  "required": [
    "signal_id",
    "features",
    "timestamp_utc"
  ],
  "properties": {
    "signal_id": {
      "type": "string",
      "description": "Reference to signal"
    },
    "timestamp_utc": {
      "type": "string",
      "format": "date-time"
    },
    "features": {
      "type": "object",
      "properties": {
        "atr_14": {"type": "number"},
        "atr_ratio_vs_20d": {"type": "number"},
        "rsi_14": {"type": "number", "minimum": 0, "maximum": 100},
        "ema_9_slope": {"type": "number"},
        "momentum_5bar": {"type": "number"},
        "bos_strength": {"type": "number", "minimum": 0, "maximum": 1},
        "fvg_size_atr": {"type": "number"},
        "fvg_age_bars": {"type": "integer"},
        "ob_distance_atr": {"type": "number"},
        "ob_strength": {"type": "number", "minimum": 0, "maximum": 1},
        "choch_severity": {"type": "number"},
        "swing_proximity": {"type": "number", "minimum": 0, "maximum": 1},
        "pullback_depth": {"type": "number"},
        "trend_direction": {"type": "integer", "enum": [-1, 0, 1]},
        "trend_strength": {"type": "number", "minimum": 0, "maximum": 1},
        "volatility_regime": {"type": "integer", "minimum": 0, "maximum": 3},
        "session_type": {"type": "integer", "minimum": 0, "maximum": 3},
        "market_regime": {"type": "integer", "minimum": 0, "maximum": 2},
        "regime_age_bars": {"type": "integer"},
        "signal_count": {"type": "integer"},
        "bos_present": {"type": "boolean"},
        "fvg_present": {"type": "boolean"},
        "ob_present": {"type": "boolean"},
        "entry_quality": {"type": "number", "minimum": 0, "maximum": 1},
        "confluence_alignment": {"type": "number", "minimum": 0, "maximum": 1},
        "timing_quality": {"type": "number", "minimum": 0, "maximum": 1},
        "sweep_intensity": {"type": "number", "minimum": 0, "maximum": 1},
        "level_stacking": {"type": "integer"},
        "liquidity_score": {"type": "number", "minimum": 0, "maximum": 1},
        "slippage_risk": {"type": "number", "minimum": 0, "maximum": 1}
      },
      "additionalProperties": false,
      "minProperties": 30,
      "maxProperties": 30
    },
    "ml_version": {
      "type": "string",
      "description": "ML model version used",
      "example": "2.0.0"
    }
  }
}
```

---

## 4. API SPECIFICATION (Method A - MT5 Package)

### 4.1 Python → MT5 (Order Placement)

```python
# Method: mt5.order_send()
# Input: MqlTradeRequest dictionary
# Output: MqlTradeResult dictionary

order_request = {
    'action': mt5.TRADE_ACTION_DEAL,
    'symbol': signal['symbol'],                    # 'EURUSD'
    'volume': signal['position_size_lots'],        # 1.25
    'type': mt5.ORDER_TYPE_BUY if signal['direction'] == 1 else mt5.ORDER_TYPE_SELL,
    'price': signal['entry_price'],                # Market order price
    'tp': signal['tp_price'],                       # Take profit
    'sl': signal['sl_price'],                       # Stop loss
    'comment': signal['signal_id'],                 # For tracking
    'magic': 20260601,                              # EA magic number
}

result = mt5.order_send(order_request)

# Response:
# result.order       → int (order ticket if successful, 0 if failed)
# result.retcode     → int (return code: 10009=success, others=error)
# result.deal        → int (deal ticket)
# result.volume      → float (volume executed)
# result.price       → float (execution price)
```

### 4.2 MT5 → Python (Position Monitoring)

```python
# Method: mt5.positions_get()
# Input: None (gets all positions) or symbol
# Output: List of Position objects

positions = mt5.positions_get(symbol='EURUSD')

for pos in positions:
    print(f"Symbol: {pos.symbol}")
    print(f"Volume: {pos.volume}")
    print(f"Entry Price: {pos.price_open}")
    print(f"Current Price: {pos.price_current}")
    print(f"Current Profit USD: {pos.profit}")
    print(f"Entry Time: {pos.time}")
    print(f"Type: {pos.type}")  # 0=BUY, 1=SELL
```

### 4.3 MT5 → Python (Order History)

```python
# Method: mt5.history_deals_get()
# Input: Start time, End time
# Output: List of completed deals

from datetime import datetime, timedelta

end = datetime.now()
start = end - timedelta(days=1)

deals = mt5.history_deals_get(start, end)

for deal in deals:
    print(f"Deal ID: {deal.ticket}")
    print(f"Symbol: {deal.symbol}")
    print(f"Volume: {deal.volume}")
    print(f"Entry Price: {deal.price}")
    print(f"P&L: {deal.profit}")
    print(f"Time: {deal.time}")
    print(f"Comment: {deal.comment}")
```

---

## 5. VALIDATION RULES

### 5.1 Signal Validation (Before Export)

```python
def validate_signal(signal: Dict) -> tuple[bool, str]:
    """
    Validate signal before sending to MT5.
    Returns: (is_valid, error_message)
    """
    
    errors = []
    
    # Check required fields
    required = ['signal_id', 'symbol', 'direction', 'entry_price', 
                'sl_price', 'tp_price', 'position_size_lots', 'risk_usd', 'ml_score']
    for field in required:
        if field not in signal:
            errors.append(f"Missing required field: {field}")
    
    # Check types and ranges
    if not isinstance(signal.get('direction'), int) or signal['direction'] not in [1, -1]:
        errors.append("direction must be 1 or -1")
    
    if signal.get('symbol') not in ['EURUSD', 'GBPUSD', 'XAUUSD']:
        errors.append(f"Invalid symbol: {signal.get('symbol')}")
    
    # Check prices
    try:
        entry = float(signal['entry_price'])
        sl = float(signal['sl_price'])
        tp = float(signal['tp_price'])
        
        if not (0.00001 < entry < 999999):
            errors.append(f"entry_price out of range: {entry}")
        
        # Check SL on correct side of entry
        if signal['direction'] == 1:  # LONG
            if sl >= entry:
                errors.append(f"LONG: SL ({sl}) must be below entry ({entry})")
            if tp <= entry:
                errors.append(f"LONG: TP ({tp}) must be above entry ({entry})")
        else:  # SHORT
            if sl <= entry:
                errors.append(f"SHORT: SL ({sl}) must be above entry ({entry})")
            if tp >= entry:
                errors.append(f"SHORT: TP ({tp}) must be below entry ({entry})")
        
        # Check RR ratio
        if signal['direction'] == 1:
            risk_dist = entry - sl
            reward_dist = tp - entry
        else:
            risk_dist = sl - entry
            reward_dist = entry - tp
        
        if risk_dist <= 0:
            errors.append(f"Invalid risk distance: {risk_dist}")
        
        rr = reward_dist / risk_dist
        if rr < 2.0:
            errors.append(f"RR ratio too low: {rr} (minimum 2.0)")
    
    except (ValueError, TypeError) as e:
        errors.append(f"Price parsing error: {e}")
    
    # Check position size
    if signal.get('position_size_lots', 0) <= 0 or signal.get('position_size_lots', 0) > 100:
        errors.append(f"Invalid position size: {signal.get('position_size_lots')}")
    
    # Check ML score
    if not (0.60 <= signal.get('ml_score', 0) <= 1.0):
        errors.append(f"ML score outside range [0.60, 1.0]: {signal.get('ml_score')}")
    
    is_valid = len(errors) == 0
    error_msg = "; ".join(errors) if errors else "Valid"
    
    return is_valid, error_msg
```

### 5.2 Result Validation (After Import)

```python
def validate_trade_result(result: Dict, original_signal: Dict) -> tuple[bool, str]:
    """
    Validate trade result matches expectations.
    """
    
    errors = []
    
    # Check exit_reason is valid
    if result.get('exit_reason') not in ['TP_HIT', 'SL_HIT', 'MANUAL_CLOSE', 'TIMEOUT']:
        errors.append(f"Invalid exit_reason: {result.get('exit_reason')}")
    
    # Validate P&L logic
    signal_dir = original_signal['direction']
    entry = result['entry_price']
    exit = result['exit_price']
    pnl_r = result['pnl_r']
    
    if result['exit_reason'] == 'TP_HIT':
        if pnl_r < 1.9:  # Should be ~2.0
            errors.append(f"TP_HIT but pnl_r={pnl_r} (expected ~2.0)")
        if signal_dir == 1 and exit <= entry:
            errors.append(f"LONG TP_HIT but exit ({exit}) <= entry ({entry})")
        if signal_dir == -1 and exit >= entry:
            errors.append(f"SHORT TP_HIT but exit ({exit}) >= entry ({entry})")
    
    elif result['exit_reason'] == 'SL_HIT':
        if pnl_r > -0.9:  # Should be ~-1.0
            errors.append(f"SL_HIT but pnl_r={pnl_r} (expected ~-1.0)")
        if signal_dir == 1 and exit >= entry:
            errors.append(f"LONG SL_HIT but exit ({exit}) >= entry ({entry})")
        if signal_dir == -1 and exit <= entry:
            errors.append(f"SHORT SL_HIT but exit ({exit}) <= entry ({entry})")
    
    # Check holding_bars is reasonable
    if result['holding_bars'] < 1 or result['holding_bars'] > 100:
        errors.append(f"Unreasonable holding_bars: {result['holding_bars']}")
    
    return len(errors) == 0, "; ".join(errors) if errors else "Valid"
```

---

## 6. ERROR CODES & HANDLING

### MT5 Return Codes

| Code | Meaning | Action |
|------|---------|--------|
| 10009 | SUCCESS | Process normally |
| 10004 | TRADE_RETCODE_REQUOTE | Retry with new price |
| 10006 | TRADE_RETCODE_REJECT | Log, investigate |
| 10007 | TRADE_RETCODE_CANCEL | Order cancelled, log |
| 10008 | TRADE_RETCODE_PLACED | Pending order (shouldn't happen for market orders) |
| 10010 | TRADE_RETCODE_DONE | Order completed |
| 10011 | TRADE_RETCODE_DONE_PARTIAL | Partial fill |
| 10012 | TRADE_RETCODE_ERROR | Generic error |
| 10013 | TRADE_RETCODE_TIMEOUT | Timeout, retry |
| 10014 | TRADE_RETCODE_INVALID_VOLUME | Check position sizing |
| 10015 | TRADE_RETCODE_INVALID_PRICE | Check entry price |

**Error Handling Strategy**:
```python
if result.retcode == 10009:  # Success
    logger.info(f"Order placed: {result.order}")
elif result.retcode in [10004, 10013]:  # Requote/Timeout - Retry
    logger.warning(f"Retryable error {result.retcode}, will retry")
    retry_signal(signal)
elif result.retcode in [10006, 10007]:  # Reject/Cancel - Skip
    logger.error(f"Order rejected/cancelled: {result.retcode}")
    skip_signal(signal)
else:  # Unknown error
    logger.error(f"Unknown error {result.retcode}")
    alert_admin()
```

---

## SUMMARY: All Schemas Created

✅ Signal Export Schema (JSON + CSV)  
✅ Trade Result Schema (JSON + CSV)  
✅ Feature Vector Schema (JSON)  
✅ API Specification (MT5 Package)  
✅ Validation Rules (Python functions)  
✅ Error Codes & Handling

**Next**: FASE 5 will implement bridge module using these schemas.
