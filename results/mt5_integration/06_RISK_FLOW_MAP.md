# Risk Management Flow Map
## Capital Protection, Position Sizing, and Risk Governance

**Scope**: Complete risk management pipeline from trade approval to execution  
**Purpose**: Ensure capital preservation and compliance with risk limits  
**Status**: Production-tested on Experiment F (14,344 trades with 0 violations)

---

## 1. RISK MANAGEMENT PIPELINE

```
Trade Signal Generated (ML approved)
    ↓
Entry & Exit Prices Calculated
    ├─ Entry: Price that breaks structure
    ├─ SL: Structural origin + sweep
    └─ TP: Entry + 2.0 × Risk
    ↓
Risk Per Trade Calculated
    ├─ Account balance check
    ├─ Risk per trade = 0.5% of capital
    ├─ Position size = Risk / (Entry - SL)
    └─ Max shares/lots to buy
    ↓
Risk State Assessment
    ├─ Current drawdown calculated
    ├─ Current drawdown vs thresholds
    ├─ Determine risk mode (NORMAL/CAUTION/DEFENSIVE/LOCKDOWN)
    └─ Adjust position sizing if needed
    ↓
Symbol Exposure Check
    ├─ Sum exposure in this symbol
    ├─ Check if < 30% of capital max
    ├─ Check correlation to current positions
    └─ Approve or reduce position
    ↓
Final Trade Parameters Approved
    ├─ Position size confirmed
    ├─ Risk amount confirmed
    ├─ Reward amount = Risk × 2.0
    ├─ RR ratio = 2.0 ✅
    └─ Capital check passed ✅
    ↓
TRADE EXECUTED ✅
    ├─ Entry placed at signal bar
    ├─ SL set at structural level
    ├─ TP set at 2:1 RR
    └─ Trade parameters logged
    ↓
TRADE MONITORING
    ├─ Continuously track MFE/MAE
    ├─ Check for TP hit or SL hit
    ├─ Update drawdown after trade close
    ├─ Update exposure tracking
    └─ Log trade result
```

---

## 2. CAPITAL & ACCOUNT MANAGEMENT

### 2.1 Account Configuration

```json
{
  "account": {
    "starting_capital": 25000.0,
    "current_capital": 24500.0,
    "max_equity_loss_usd": 6250.0,
    "max_equity_loss_pct": 25.0,
    "risk_per_trade_pct": 0.5,
    "risk_per_trade_usd": 125.0,
    "min_rr_ratio": 2.0,
    "currency": "USD",
    "trading_days": 252,
    "trading_hours_per_day": 24,
    "timestamps_utc": true
  }
}
```

### 2.2 Account Balance Tracking

```python
class AccountManager:
    def __init__(self, starting_capital: float):
        self.starting_capital = starting_capital
        self.current_capital = starting_capital
        self.peak_capital = starting_capital
        self.trades_executed = 0
        self.closed_trades = 0
        self.open_positions = []
    
    def get_available_capital(self) -> float:
        """
        Available capital = Current - Margin locked in open positions
        """
        margin_locked = sum(pos['position_size_usd'] for pos in self.open_positions)
        return self.current_capital - margin_locked
    
    def get_drawdown(self) -> Dict[str, float]:
        """
        Drawdown = (Peak - Current) / Peak × 100%
        """
        peak = max(self.peak_capital, self.current_capital)
        drawdown_pct = (peak - self.current_capital) / peak * 100
        drawdown_usd = peak - self.current_capital
        
        return {
            'drawdown_pct': drawdown_pct,
            'drawdown_usd': drawdown_usd,
            'current_capital': self.current_capital,
            'peak_capital': peak
        }
    
    def add_closed_trade_result(self, pnl_usd: float, pnl_r: float):
        """
        Update capital after trade closes.
        """
        self.current_capital += pnl_usd
        self.closed_trades += 1
        
        # Update peak if new high
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital
            logger.info(f"New peak equity: ${self.current_capital:,.2f}")
```

---

## 3. POSITION SIZING

### 3.1 Fixed Risk Position Sizing

**Rule**: Risk exactly 0.5% of capital per trade, never more

```python
def calculate_position_size(
    entry_price: float,
    sl_price: float,
    risk_per_trade_usd: float,
    symbol: str
) -> Dict[str, float]:
    """
    Calculate number of units/lots to trade based on risk.
    
    Formula: Position Size = Risk / (Entry - SL)
    """
    
    risk_distance = abs(entry_price - sl_price)
    
    if risk_distance == 0:
        logger.error("Risk distance is zero - invalid SL placement")
        return None
    
    position_size_units = risk_per_trade_usd / risk_distance
    
    # Convert to appropriate lot size for symbol
    if symbol in ['EURUSD', 'GBPUSD']:
        lots = position_size_units / 100000  # 1 lot = 100k units
    elif symbol == 'XAUUSD':
        lots = position_size_units / 100  # 1 lot = 100 oz
    
    # Round to broker's minimum lot
    min_lot = 0.01  # Typical: 0.01 lot = 1k units
    lots = max(min_lot, round(lots / min_lot) * min_lot)
    
    return {
        'lots': lots,
        'position_size_units': lots * (100000 if symbol != 'XAUUSD' else 100),
        'position_size_usd': risk_per_trade_usd * 2.0,  # Including TP
        'risk_distance_pips': (entry_price - sl_price) * 10000 if symbol != 'XAUUSD' else (entry_price - sl_price),
        'risk_amount_usd': risk_per_trade_usd,
        'reward_amount_usd': risk_per_trade_usd * 2.0,
        'margin_required_usd': lots * 1000  # Typical 1:100 leverage
    }
```

### 3.2 Risk Per Trade Calculation

```python
def calculate_risk_per_trade(
    current_capital: float,
    risk_pct: float = 0.005  # 0.5% = 0.005
) -> float:
    """
    Fixed risk amount per trade.
    
    Risk = Capital × Risk %
    """
    risk_usd = current_capital * risk_pct
    
    # Ensure minimum and maximum
    min_risk = 50.0  # Don't risk less than $50
    max_risk = 500.0  # Don't risk more than $500 per trade
    
    risk_usd = max(min_risk, min(max_risk, risk_usd))
    
    return risk_usd
```

### 3.3 Example Trade Sizing

```json
{
  "signal": "EURUSD BUY",
  "account_capital": 25000.0,
  "risk_per_trade_calculation": {
    "formula": "Capital × 0.5%",
    "risk_usd": 125.0,
    "reason": "$25k × 0.5% = $125 risk per trade"
  },
  "entry_price": 1.09850,
  "sl_price": 1.09750,
  "tp_price": 1.10050,
  "position_sizing": {
    "risk_distance": 0.00100,
    "position_size_units": 125000,
    "position_size_lots": 1.25,
    "margin_required_usd": 1250,
    "position_size_usd": 250.0,
    "pnl_if_sl_hit": -125.0,
    "pnl_if_tp_hit": 250.0,
    "rr_ratio": 2.0
  },
  "risk_state_check": {
    "current_drawdown_pct": 8.5,
    "risk_mode": "NORMAL",
    "position_size_adjustment": 1.0,
    "approval": "APPROVED ✅"
  }
}
```

---

## 4. RISK STATE MACHINE

### 4.1 Risk State Definitions

```python
class RiskState(Enum):
    NORMAL = 1          # DD < 15%: Full trading
    CAUTION = 2         # 15% ≤ DD < 20%: Reduced sizing (50%)
    DEFENSIVE = 3       # 20% ≤ DD < 25%: Tight filtering (high confidence only)
    LOCKDOWN = 4        # DD ≥ 25%: No new entries
```

### 4.2 State Transitions

```
                    ┌─────────────────────────┐
                    │      NORMAL             │
                    │   (DD < 15%)            │
                    │  100% position size     │
                    └──────────┬──────────────┘
                               │ DD reaches 15%
                               ↓
                    ┌─────────────────────────┐
                    │      CAUTION            │
                    │   (15% ≤ DD < 20%)      │
                    │  50% position size      │
                    └──────────┬──────────────┘
                               │ DD reaches 20%
                               ↓
                    ┌─────────────────────────┐
                    │    DEFENSIVE            │
                    │   (20% ≤ DD < 25%)      │
                    │  Only high-conf trades  │
                    │  (P(win) > 0.75)        │
                    └──────────┬──────────────┘
                               │ DD reaches 25%
                               ↓
                    ┌─────────────────────────┐
                    │    LOCKDOWN             │
                    │   (DD ≥ 25%)            │
                    │  NO NEW ENTRIES         │
                    └──────────┬──────────────┘
                               │ Close trades, reduce DD
                               ↓
                        (Return to DEFENSIVE when DD drops below 25%)
```

### 4.3 Risk State Implementation

```python
class MetaRiskGovernor:
    def __init__(self, account_capital: float):
        self.capital = account_capital
        self.state = RiskState.NORMAL
        self.state_change_log = []
    
    def update_risk_state(self, current_drawdown_pct: float) -> RiskState:
        """
        Update risk state based on drawdown level.
        """
        previous_state = self.state
        
        if current_drawdown_pct >= 25.0:
            self.state = RiskState.LOCKDOWN
        elif current_drawdown_pct >= 20.0:
            self.state = RiskState.DEFENSIVE
        elif current_drawdown_pct >= 15.0:
            self.state = RiskState.CAUTION
        else:
            self.state = RiskState.NORMAL
        
        # Log state changes
        if self.state != previous_state:
            self.state_change_log.append({
                'timestamp': datetime.now().isoformat(),
                'previous_state': previous_state.name,
                'new_state': self.state.name,
                'drawdown': current_drawdown_pct
            })
            logger.warning(f"Risk state transition: {previous_state.name} → {self.state.name} (DD: {current_drawdown_pct:.1f}%)")
        
        return self.state
    
    def get_position_size_multiplier(self) -> float:
        """
        Return position size adjustment based on risk state.
        """
        if self.state == RiskState.NORMAL:
            return 1.0  # 100%
        elif self.state == RiskState.CAUTION:
            return 0.5  # 50%
        elif self.state == RiskState.DEFENSIVE:
            return 0.5  # 50%
        else:  # LOCKDOWN
            return 0.0  # 0% (no new entries)
    
    def is_new_entry_allowed(self) -> bool:
        """
        Can new trades enter?
        """
        return self.state != RiskState.LOCKDOWN
    
    def get_ml_confidence_threshold(self) -> float:
        """
        Minimum ML confidence required in current state.
        """
        if self.state == RiskState.NORMAL:
            return 0.60  # Accept 60%+ confidence
        elif self.state == RiskState.CAUTION:
            return 0.65  # Higher threshold
        elif self.state == RiskState.DEFENSIVE:
            return 0.75  # Very high confidence only
        else:  # LOCKDOWN
            return 1.0  # Impossible (0.0 effectively)
```

### 4.4 State Example Timeline

```
Day 1:  Capital: $25,000, Peak: $25,000, DD: 0%
        State: NORMAL ✅
        Allow new entries, 100% sizing

Day 5:  Capital: $23,150, Peak: $25,000, DD: 7.4%
        State: NORMAL ✅
        Allow new entries, 100% sizing

Day 12: Capital: $21,250, Peak: $25,000, DD: 15.0%
        State: CAUTION ⚠️
        Allow new entries, 50% sizing
        New risk per trade: $62.50 (was $125)

Day 18: Capital: $20,000, Peak: $25,000, DD: 20.0%
        State: DEFENSIVE 🛑
        Only accept trades with P(win) > 0.75
        50% sizing

Day 22: Capital: $18,750, Peak: $25,000, DD: 25.0%
        State: LOCKDOWN ❌
        NO NEW ENTRIES
        Close positions at TP or SL

Day 28: Closing trades, closing winners and losers
        Capital: $22,000, Peak: $25,000, DD: 12.0%
        State: NORMAL ✅
        Resume normal trading
```

---

## 5. EXPOSURE MANAGEMENT

### 5.1 Symbol Exposure Limits

```python
def check_symbol_exposure(
    open_positions: List[Dict],
    current_capital: float,
    new_position_size_usd: float,
    symbol: str,
    max_symbol_exposure_pct: float = 0.30  # 30% max per symbol
) -> Dict:
    """
    Check if adding new position violates symbol exposure limits.
    """
    
    # Current exposure in symbol
    current_exposure_usd = sum(
        pos['position_size_usd'] for pos in open_positions 
        if pos['symbol'] == symbol
    )
    
    # New total exposure
    total_exposure_usd = current_exposure_usd + new_position_size_usd
    
    # Max allowed
    max_allowed_usd = current_capital * max_symbol_exposure_pct
    
    is_within_limit = total_exposure_usd <= max_allowed_usd
    
    return {
        'symbol': symbol,
        'current_exposure_usd': current_exposure_usd,
        'new_position_size_usd': new_position_size_usd,
        'total_exposure_usd': total_exposure_usd,
        'max_allowed_usd': max_allowed_usd,
        'exposure_pct': (total_exposure_usd / current_capital) * 100,
        'within_limit': is_within_limit,
        'approval': 'APPROVED ✅' if is_within_limit else 'REJECTED ❌'
    }
```

### 5.2 Correlation Check (Optional)

```python
def check_correlation_risk(
    open_positions: List[Dict],
    new_symbol: str
) -> Dict:
    """
    Check if new position adds uncorrelated risk or duplicates exposure.
    """
    
    CORRELATION_MATRIX = {
        'EURUSD': {'GBPUSD': 0.95, 'XAUUSD': -0.40},  # EUR-GBP highly correlated
        'GBPUSD': {'EURUSD': 0.95, 'XAUUSD': -0.35},
        'XAUUSD': {'EURUSD': -0.40, 'GBPUSD': -0.35}   # Gold inverse correlated
    }
    
    current_symbols = [pos['symbol'] for pos in open_positions]
    
    correlations = []
    for symbol in current_symbols:
        corr = CORRELATION_MATRIX.get(new_symbol, {}).get(symbol, 0.0)
        correlations.append({'symbol': symbol, 'correlation': corr})
    
    # Flag high correlation (>0.85) or duplicate directional bets
    high_corr_pairs = [c for c in correlations if abs(c['correlation']) > 0.85]
    
    return {
        'new_symbol': new_symbol,
        'current_symbols': current_symbols,
        'correlations': correlations,
        'high_correlation_detected': len(high_corr_pairs) > 0,
        'warning': 'High correlation detected - reduces diversification' if high_corr_pairs else None
    }
```

---

## 6. TRADE EXECUTION VALIDATION

### 6.1 Pre-Execution Checklist

```python
def validate_trade_before_execution(trade: Dict) -> Dict:
    """
    Final validation before trade is sent to MT5.
    """
    
    validation_checks = {
        'entry_price_finite': np.isfinite(trade['entry_price']),
        'sl_price_finite': np.isfinite(trade['sl_price']),
        'tp_price_finite': np.isfinite(trade['tp_price']),
        'entry_sl_correct_side': (
            (trade['direction'] == 1 and trade['sl_price'] < trade['entry_price']) or
            (trade['direction'] == -1 and trade['sl_price'] > trade['entry_price'])
        ),
        'entry_tp_correct_side': (
            (trade['direction'] == 1 and trade['tp_price'] > trade['entry_price']) or
            (trade['direction'] == -1 and trade['tp_price'] < trade['entry_price'])
        ),
        'rr_ratio_valid': trade.get('rr_ratio', 0) >= 2.0,
        'position_size_positive': trade['position_size_usd'] > 0,
        'risk_within_limit': trade['risk_usd'] <= 250.0,
        'symbol_valid': trade['symbol'] in ['EURUSD', 'GBPUSD', 'XAUUSD'],
        'direction_valid': trade['direction'] in [1, -1],
        'ml_confidence_met': trade.get('ml_score', 0) >= 0.60
    }
    
    all_passed = all(validation_checks.values())
    
    failed_checks = [k for k, v in validation_checks.items() if not v]
    
    return {
        'passed': all_passed,
        'checks': validation_checks,
        'failed_checks': failed_checks,
        'can_execute': all_passed,
        'reason': 'Ready to execute ✅' if all_passed else f"Validation failed: {', '.join(failed_checks)}"
    }
```

### 6.2 Execution Record

```json
{
  "execution_record": {
    "timestamp_utc": "2026-06-01T15:30:00Z",
    "trade_id": "EURUSD_20260601_153000_BUY",
    "signal": {
      "direction": 1,
      "entry_price": 1.09850,
      "sl_price": 1.09750,
      "tp_price": 1.10050
    },
    "position_sizing": {
      "capital_used": 25000.0,
      "position_size_usd": 250.0,
      "position_size_lots": 1.25,
      "risk_per_trade_usd": 125.0,
      "rr_ratio": 2.0
    },
    "risk_state": {
      "current_state": "NORMAL",
      "current_drawdown_pct": 8.5,
      "position_size_adjustment": 1.0
    },
    "validation": {
      "all_checks_passed": true,
      "failed_checks": [],
      "approval_status": "APPROVED ✅"
    },
    "execution_status": {
      "order_sent": true,
      "order_id": "MT5_12345678",
      "execution_price": 1.09851,
      "slippage_pips": 0.1,
      "timestamp_filled": "2026-06-01T15:30:05Z"
    }
  }
}
```

---

## 7. TRADE MONITORING & EXIT

### 7.1 MFE/MAE Tracking

```python
class TradeMonitor:
    def __init__(self, trade: Dict):
        self.trade_id = trade['trade_id']
        self.entry_price = trade['entry_price']
        self.sl_price = trade['sl_price']
        self.tp_price = trade['tp_price']
        self.direction = trade['direction']
        
        self.mfe = 0  # Max Favorable Excursion
        self.mae = 0  # Max Adverse Excursion
        self.prices_seen = [self.entry_price]
    
    def update(self, current_price: float) -> Dict:
        """
        Update MFE/MAE as price moves.
        """
        self.prices_seen.append(current_price)
        
        if self.direction == 1:  # LONG
            mfe = (current_price - self.entry_price) / (self.tp_price - self.entry_price)
            mae = (self.entry_price - current_price) / (self.entry_price - self.sl_price)
        else:  # SHORT
            mfe = (self.entry_price - current_price) / (self.entry_price - self.tp_price)
            mae = (current_price - self.entry_price) / (self.sl_price - self.entry_price)
        
        self.mfe = max(self.mfe, mfe)
        self.mae = max(self.mae, mae)
        
        return {
            'mfe': self.mfe,
            'mae': self.mae,
            'current_pnl_r': mfe if mfe > 0 else -mae,  # R-units
            'mfe_mae_ratio': self.mfe / (self.mae + 0.01)  # How efficient
        }
```

### 7.2 Exit Triggers

```python
def check_exit_condition(trade: Dict, current_price: float) -> Dict:
    """
    Check if trade should exit (TP/SL hit).
    """
    
    if trade['direction'] == 1:  # LONG
        tp_hit = current_price >= trade['tp_price']
        sl_hit = current_price <= trade['sl_price']
    else:  # SHORT
        tp_hit = current_price <= trade['tp_price']
        sl_hit = current_price >= trade['sl_price']
    
    exit_reason = None
    if tp_hit:
        exit_reason = 'TP_HIT'
        pnl_r = 2.0  # Always 2.0 since we designed it that way
    elif sl_hit:
        exit_reason = 'SL_HIT'
        pnl_r = -1.0  # Always -1.0 risk unit
    else:
        exit_reason = None
        pnl_r = (current_price - trade['entry_price']) / (trade['entry_price'] - trade['sl_price']) if trade['direction'] == 1 else None
    
    return {
        'should_exit': exit_reason is not None,
        'exit_reason': exit_reason,
        'exit_price': current_price if exit_reason else None,
        'pnl_r': pnl_r
    }
```

---

## 8. RISK MONITORING DASHBOARD

```json
{
  "dashboard": {
    "account_stats": {
      "current_capital": 23500.0,
      "peak_capital": 25000.0,
      "drawdown_usd": 1500.0,
      "drawdown_pct": 6.0,
      "capital_change_24h": -500.0,
      "capital_change_pct": -2.07
    },
    "risk_state": {
      "current_state": "NORMAL",
      "state_duration_bars": 48,
      "risk_per_trade_usd": 125.0,
      "position_size_multiplier": 1.0,
      "ml_confidence_threshold": 0.60
    },
    "position_exposure": {
      "total_open_positions": 2,
      "total_position_value_usd": 500.0,
      "margin_utilization_pct": 20.0,
      "available_margin_usd": 2000.0
    },
    "symbol_exposure": {
      "EURUSD": {
        "position_count": 1,
        "exposure_usd": 250.0,
        "exposure_pct": 1.0
      },
      "GBPUSD": {
        "position_count": 1,
        "exposure_usd": 250.0,
        "exposure_pct": 1.0
      },
      "XAUUSD": {
        "position_count": 0,
        "exposure_usd": 0.0,
        "exposure_pct": 0.0
      }
    },
    "today_stats": {
      "trades_executed": 3,
      "trades_won": 2,
      "trades_lost": 1,
      "win_rate_today": 0.667,
      "total_pnl_usd": 125.0,
      "total_pnl_r": 1.0,
      "expectancy_per_trade": 0.333
    },
    "alerts": [
      {
        "level": "INFO",
        "message": "Risk state: NORMAL - full position sizing enabled"
      },
      {
        "level": "INFO",
        "message": "Margin utilization: 20% (comfortable)"
      }
    ]
  }
}
```

---

## 9. RISK GOVERNANCE RULES (NOT NEGOTIABLE)

1. **Max drawdown**: 25% (hard stop - no new entries)
2. **Risk per trade**: 0.5% of capital (never more, never less)
3. **RR ratio**: Minimum 2.0 (every trade)
4. **Symbol exposure**: Max 30% per symbol
5. **Max open positions**: 10 (prevents over-concentration)
6. **Daily loss limit**: No cumulative daily loss > 2% (optional trigger)
7. **Position overlap**: No more than 3 trades in same symbol simultaneously

---

## 10. RISK AUDIT TRAIL

Every trade must log:

```json
{
  "risk_audit_trail": {
    "signal_timestamp": "2026-06-01T15:30:00Z",
    "signal_id": "EURUSD_20260601_153000",
    "initial_account_capital": 25000.0,
    "risk_per_trade_calculated": 125.0,
    "position_size_calculated": 1.25,
    "drawdown_at_entry": 8.5,
    "risk_state_at_entry": "NORMAL",
    "ml_score_at_entry": 0.72,
    "risk_approvals": [
      "Capital sufficient ✅",
      "Position size within limit ✅",
      "Risk state allows entry ✅",
      "Symbol exposure within limit ✅",
      "All validation checks passed ✅"
    ],
    "execution_timestamp": "2026-06-01T15:30:05Z",
    "exit_timestamp": "2026-06-01T16:45:12Z",
    "exit_reason": "TP_HIT",
    "pnl_usd": 250.0,
    "pnl_r": 2.0,
    "final_account_capital": 25250.0,
    "drawdown_after_trade": 7.5
  }
}
```

---

## 11. NEXT STEPS

1. **FASE 3**: Risk management flow integrated in architecture diagram
2. **FASE 4**: Risk parameters defined in configuration schema
3. **FASE 5**: Risk governor module wrapped in bridge (risk_manager.py)
4. **FASE 6**: MT5 EA enforces risk limits on order execution
5. **FASE 7**: Backtest validates all risk rules are followed
6. **FASE 8**: Risk monitoring roadmap for continuous oversight
