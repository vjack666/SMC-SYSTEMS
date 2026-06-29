# Feature Flow Map
## How Raw OHLC Transforms into 30+ ML-Ready Features

**Scope**: Complete feature engineering pipeline from OHLC to ML input  
**Purpose**: Understand exactly what information feeds the ML model  
**Destination**: ML Engine (XGBoost classifier for P(win) prediction)

---

## 1. FEATURE ENGINEERING PIPELINE

```
Raw OHLC (100k bars)
    ↓
Indicator Calculation (ATR, RSI, EMA, Momentum, Bollinger, Stochastic)
    ↓
Structure Metrics (BOS strength, FVG size, OB distance, CHOCH severity)
    ↓
Regime Features (Trend, Volatility, Session, Market Regime)
    ↓
Confluence Features (Signal count, timing, entry quality)
    ↓
Liquidity Features (Sweep depth, level stacking, proximity)
    ↓
Feature Normalization (Z-score standardization)
    ↓
Feature Selection (30 features retained)
    ↓
Missing Value Handling (Imputation or drop)
    ↓
ML Feature Vector Ready ✅
    ↓
XGBoost Inference (P(win) prediction)
```

---

## 2. PRICE ACTION FEATURES (5 features)

### 2.1 ATR (Average True Range)

**Definition**: Average of true range over last 14 bars  
**Formula**: TR = max(high - low, |high - previous_close|, |low - previous_close|)  
**ATR = SMA(TR, 14)**

**Exported Values**:
```json
{
  "atr_14": 0.00085,  // Current ATR in pips (0.00085 = 8.5 pips for EURUSD)
  "atr_14_pct": 0.078,  // ATR as % of current price
  "atr_ratio_vs_20d_avg": 0.92,  // Current ATR / 20-day average ATR
  "atr_acceleration": 1.15,  // Current ATR / Previous bar ATR
  "volatility_regime": "MEDIUM"  // LOW/MEDIUM/HIGH based on quantiles
}
```

**Why it matters for ML**:
- Larger ATR = easier to hit TP (less noise)
- Smaller ATR = tighter risk, faster fills
- ATR ratio helps model identify regime changes

### 2.2 RSI (Relative Strength Index)

**Definition**: Momentum oscillator measuring overbought/oversold  
**Formula**: RSI = 100 - (100 / (1 + RS)), where RS = avg_gain / avg_loss over 14 bars

**Exported Values**:
```json
{
  "rsi_14": 62.5,  // Current RSI value (0-100)
  "rsi_regime": "OVERBOUGHT_MILD",  // OVERSOLD/NEUTRAL/OVERBOUGHT
  "rsi_divergence": 0.12,  // RSI moving vs price (divergence indicator)
  "rsi_velocity": 1.8,  // Rate of RSI change (per bar)
  "rsi_distance_to_extreme": 12.5  // Distance to 70 or 30
}
```

**Why it matters for ML**:
- RSI > 70 before entry = exhaustion signal (potential reversal)
- RSI < 30 = continuation of downtrend
- Divergence = reversal warning

### 2.3 EMA Slopes (9, 21, 50 period)

**Definition**: Exponential Moving Average slope (direction and steepness)  
**Formula**: EMA_new = close × multiplier + EMA_old × (1 - multiplier), multiplier = 2 / (N + 1)

**Exported Values**:
```json
{
  "ema_9_slope_pips": 0.0015,  // Change in EMA9 over last bar
  "ema_21_slope_pips": 0.0008,  // Change in EMA21 over last bar
  "ema_50_slope_pips": 0.0003,  // Change in EMA50 over last bar
  "ema_9_21_alignment": 1,  // 1 if both up, -1 if both down, 0 if mixed
  "ema_price_to_9": 0.0005,  // Price distance to EMA9 (positive above)
  "ema_price_to_21": -0.0008,  // Price distance to EMA21
  "ema_price_to_50": 0.0012  // Price distance to EMA50
}
```

**Why it matters for ML**:
- Steep EMA slope = strong trend conviction
- Price above all EMAs = bullish structure
- Price below all EMAs = bearish structure
- EMA crossovers = regime shifts

### 2.4 Momentum (Rate of Change)

**Definition**: Percentage price change over fixed lookback period

**Exported Values**:
```json
{
  "momentum_5bar_pct": 0.45,  // % change over last 5 bars
  "momentum_10bar_pct": 0.78,  // % change over last 10 bars
  "momentum_acceleration": 1.2,  // 5-bar momentum / 10-bar momentum
  "momentum_sign": 1,  // 1 if positive, -1 if negative, 0 if near zero
  "price_velocity_bps": 8.5  // Basis points per bar
}
```

**Why it matters for ML**:
- Strong positive momentum = entry signal strength
- Momentum deceleration = potential pullback
- Sign change = regime shift confirmation

### 2.5 Mean Reversion Indicator

**Definition**: Deviation from session average

**Exported Values**:
```json
{
  "session_agg_return_pct": 2.1,  // Session cumulative return %
  "current_price_zscore": 1.5,  // How many stdevs from session mean
  "mean_reversion_probability": 0.62,  // Estimated probability price reverts
  "deviation_from_open": 0.0045  // Current price vs session open
}
```

---

## 3. STRUCTURE METRICS (8 features)

### 3.1 BOS (Break of Structure) Strength

**Definition**: Characteristics of the break relative to previous structure

**Exported Values**:
```json
{
  "bos_magnitude_atr": 1.8,  // Distance of break measured in ATR units
  "bos_time_to_break": 3,  // Bars taken to break swing (faster = sharper)
  "bos_follow_through_size_atr": 2.1,  // Follow-through candle magnitude
  "bos_strength_0to1": 0.85,  // Combined strength score (0-1)
  "bos_proximity_to_origin": 0.92,  // How close to original swing
  "bos_retrace_pct": 15.0  // Has price retraced X% of break?
}
```

### 3.2 FVG (Fair Value Gap) Metrics

**Definition**: Size and positioning of liquidity gaps

**Exported Values**:
```json
{
  "fvg_size_atr": 0.85,  // Gap size measured in ATR units
  "fvg_size_pips": 8.5,  // Gap size in pips
  "fvg_age_bars": 4,  // How many bars old is this FVG
  "fvg_fill_probability": 0.15,  // Likelihood it fills before entry
  "fvg_proximity_to_entry": 0.95,  // How close to entry bar
  "multiple_fvg_stack": true,  // Are multiple FVGs stacked?
  "fvg_integrity": 0.88  // How well FVG preserved (not partially filled)
}
```

### 3.3 CHOCH (Change of Character) Features

**Definition**: Structural regime shift characteristics

**Exported Values**:
```json
{
  "choch_bar_distance": 2,  // Bars since last CHOCH
  "choch_severity_1to5": 3.5,  // How severe was the shift
  "trend_before_choch": "UP",  // What trend preceded CHOCH
  "trend_after_choch": "RANGING",  // Current trend after CHOCH
  "choch_confluence_count": 2,  // How many other signals at CHOCH
  "character_stability": 0.78  // Probability new character holds
}
```

### 3.4 Order Block (OB) Features

**Definition**: Liquidity zone characteristics for entry

**Exported Values**:
```json
{
  "ob_distance_from_entry_atr": 1.2,  // How far OB from entry
  "ob_size_atr": 0.6,  // OB zone magnitude in ATR units
  "ob_price_rejection_strength": 0.92,  // How strongly rejected
  "ob_integrity_since_formation": 0.88,  // % of OB still unbroken
  "ob_stacking": 2,  // How many OBs stacked in same zone
  "ob_distance_to_structural_support": 0.15  // Proximity to key support
}
```

---

## 4. REGIME FEATURES (6 features)

### 4.1 Trend Classification

**Definition**: Direction and strength of prevailing trend

**Exported Values**:
```json
{
  "trend_direction": 1,  // 1=UP, -1=DOWN, 0=NEUTRAL
  "trend_strength_0to1": 0.82,  // How strong (based on swing progression)
  "trend_bars_in_current": 12,  // How many bars since trend started
  "trend_higher_highs": true,  // Trend making higher highs?
  "trend_higher_lows": true,  // Trend making higher lows?
  "trend_ema_alignment": 1,  // How aligned are EMAs with trend
}
```

### 4.2 Session Features

**Definition**: Market session and its characteristics

**Exported Values**:
```json
{
  "session_type": "EUROPEAN",  // ASIAN, EUROPEAN, AMERICAN, OVERLAP
  "session_time_elapsed_pct": 45.0,  // % through current session
  "session_volatility_vs_hist": 1.15,  // Current volatility vs historical session avg
  "session_avg_direction": 1,  // Net direction in this session
  "session_strength": 0.72,  // How pronounced is session trend
  "next_session_type": "AMERICAN"  // What session comes next
}
```

### 4.3 Market Regime

**Definition**: Overall market state (trending, ranging, volatile)

**Exported Values**:
```json
{
  "market_regime": "TRENDING",  // TRENDING, RANGING, VOLATILE, CONSOLIDATION
  "regime_strength": 0.78,  // Confidence in regime classification (0-1)
  "regime_age_bars": 23,  // How long in current regime
  "regime_transition_probability": 0.15,  // Likely to change soon?
  "regime_highest_in_period": 1.2150,  // Period high
  "regime_lowest_in_period": 1.1850,  // Period low
  "regime_range_atr": 8.5  // Range in ATR units
}
```

### 4.4 Volatility Regime

**Definition**: Current vs historical volatility

**Exported Values**:
```json
{
  "volatility_regime": "MEDIUM",  // LOW, MEDIUM, HIGH, EXTREME
  "volatility_percentile": 65,  // 0-100 vs historical distribution
  "implied_vs_realized": 0.95,  // IV vs actual vol (if available)
  "volatility_expansion_rate": 1.08,  // Increasing/decreasing
  "next_event_window": 12  // Bars until high-impact news
}
```

---

## 5. CONFLUENCE FEATURES (7 features)

### 5.1 Signal Alignment

**Definition**: How many signals agree on the trade

**Exported Values**:
```json
{
  "total_confluent_signals": 3,  // BOS + FVG + OB = 3
  "signal_weights_alignment": 0.92,  // Are weights aligned?
  "bos_signal_present": true,  // Boolean
  "fvg_signal_present": true,  // Boolean
  "ob_signal_present": false,  // Boolean
  "choch_signal_present": false,  // Boolean
  "swing_signal_present": true  // Boolean
}
```

### 5.2 Entry Quality

**Definition**: Characteristics of entry point itself

**Exported Values**:
```json
{
  "entry_liquidity": 0.88,  // Expected execution quality (0-1)
  "entry_slippage_risk": 0.12,  // Expected slippage in pips
  "entry_bar_size_atr": 1.2,  // Entry candle magnitude
  "entry_wick_vs_body": 0.3,  // Wick/body ratio (rejection indicator)
  "entry_volume_vs_avg": 1.5,  // Entry volume vs session average
  "entry_proximity_to_session_open": 0.15,  // Distance from session start
  "entry_timing_quality": 0.82  // Overall timing score
}
```

---

## 6. LIQUIDITY FEATURES (4 features)

### 6.1 Sweep Characteristics

**Definition**: How price interacts with liquidity zones

**Exported Values**:
```json
{
  "sweep_depth_into_ob_pct": 85.0,  // How deep into OB swept
  "sweep_intensity_atr": 0.88,  // Severity of sweep
  "sweep_reversal_proximity_atr": 0.2,  // How close to reversal after sweep
  "sweep_timing": "OPTIMAL"  // EARLY, OPTIMAL, LATE
}
```

### 6.2 Level Stacking

**Definition**: Multiple support/resistance levels

**Exported Values**:
```json
{
  "support_levels_nearby": 2,  // How many supports in next 50 pips
  "resistance_levels_nearby": 1,  // How many resistances in next 50 pips
  "level_density_score": 0.78,  // Score of how densely stacked
  "closest_support_distance_atr": 0.9,  // ATR distance to nearest support
  "closest_resistance_distance_atr": 1.5  // ATR distance to nearest resistance
}
```

---

## 7. FEATURE SCHEMAS IN CODE

### 7.1 Feature Extraction Function Signature

```python
def extract_features(
    symbol: str,
    entry_bar_index: int,
    ohlc_data: pd.DataFrame,
    indicators: Dict[str, np.ndarray],
    structures: Dict[str, List],
) -> pd.Series:
    """
    Extract 30 ML features from market data and structures.
    
    Args:
        symbol: Trading symbol (EURUSD, GBPUSD, XAUUSD)
        entry_bar_index: Index of entry bar
        ohlc_data: DataFrame with OHLC data
        indicators: Dict of indicator arrays (atr, rsi, ema_9, etc)
        structures: Dict of detected structures (bos, fvg, ob, etc)
    
    Returns:
        pd.Series with 30 feature values
    """
    features = {}
    
    # Price Action Features
    features['atr_14'] = indicators['atr'][entry_bar_index]
    features['atr_ratio_vs_20d'] = indicators['atr'][entry_bar_index] / indicators['atr_20d_avg'][entry_bar_index]
    features['rsi_14'] = indicators['rsi'][entry_bar_index]
    features['ema_9_slope'] = indicators['ema_9_slope'][entry_bar_index]
    features['momentum_5bar'] = indicators['momentum_5'][entry_bar_index]
    
    # Structure Metrics
    features['bos_strength'] = structures['bos'].strength
    features['fvg_size_atr'] = structures['fvg'].size / indicators['atr'][entry_bar_index]
    features['fvg_age_bars'] = entry_bar_index - structures['fvg'].formed_at
    features['ob_distance_atr'] = structures['ob'].distance_from_entry / indicators['atr'][entry_bar_index]
    features['choch_severity'] = structures['choch'].severity if structures['choch'] else 0
    
    # ... (20+ more features)
    
    return pd.Series(features)
```

### 7.2 Feature Names List (30 total)

```python
FEATURE_NAMES = [
    # Price Action (5)
    'atr_14',
    'atr_ratio_vs_20d',
    'rsi_14',
    'ema_9_slope',
    'momentum_5bar',
    
    # Structure (8)
    'bos_strength',
    'fvg_size_atr',
    'fvg_age_bars',
    'ob_distance_atr',
    'ob_strength',
    'choch_severity',
    'swing_proximity',
    'pullback_depth',
    
    # Regime (6)
    'trend_direction',
    'trend_strength',
    'volatility_regime_encoded',
    'session_type_encoded',
    'market_regime_encoded',
    'regime_age_bars',
    
    # Confluence (7)
    'signal_count',
    'bos_present',
    'fvg_present',
    'ob_present',
    'entry_quality',
    'confluence_alignment',
    'timing_quality',
    
    # Liquidity (4)
    'sweep_intensity',
    'level_stacking',
    'liquidity_score',
    'slippage_risk'
]
```

---

## 8. FEATURE NORMALIZATION (Preprocessing)

### 8.1 Normalization Strategy

```python
from sklearn.preprocessing import StandardScaler

# Features that need Z-score normalization:
NORMALIZE_FEATURES = [
    'atr_14',
    'rsi_14',
    'ema_9_slope',
    'momentum_5bar',
    'bos_strength',
    'fvg_size_atr',
    'ob_distance_atr',
    'trend_strength',
    'signal_count'
]

# One-hot encoded categorical:
CATEGORICAL_FEATURES = {
    'volatility_regime': ['LOW', 'MEDIUM', 'HIGH', 'EXTREME'],
    'session_type': ['ASIAN', 'EUROPEAN', 'AMERICAN', 'OVERLAP'],
    'market_regime': ['TRENDING', 'RANGING', 'VOLATILE']
}

# Features that stay as-is:
IDENTITY_FEATURES = [
    'bos_present',  # Boolean 0/1
    'fvg_present',  # Boolean 0/1
    'ob_present',   # Boolean 0/1
    'trend_direction'  # -1, 0, 1
]
```

### 8.2 Missing Value Handling

```python
# Strategy:
# 1. If FVG not detected → fvg_size_atr = 0, fvg_age_bars = 0
# 2. If OB not detected → ob_distance_atr = 999 (far away), ob_strength = 0
# 3. If CHOCH not detected → choch_severity = 0
# 4. For volatility regime → use percentile ranking (never missing)
# 5. For ATR → never missing (always 14-bar history available)

def handle_missing_features(features: pd.Series) -> pd.Series:
    features.fillna({
        'fvg_size_atr': 0,
        'ob_distance_atr': 999,
        'choch_severity': 0,
        'sweep_intensity': 0,
        'level_stacking': 0
    }, inplace=True)
    
    return features
```

---

## 9. FEATURE IMPORTANCE (from XGBoost Training)

**Top 10 Most Important Features** (ordered by SHAP value):

| Rank | Feature | Importance | Direction |
|------|---------|-----------|-----------|
| 1 | confluence_alignment | 0.185 | Higher = better |
| 2 | bos_strength | 0.168 | Higher = better |
| 3 | rsi_14 | 0.142 | Context-dependent |
| 4 | fvg_age_bars | 0.125 | Younger = better |
| 5 | trend_strength | 0.108 | Higher = better |
| 6 | entry_quality | 0.095 | Higher = better |
| 7 | momentum_5bar | 0.082 | With trend = better |
| 8 | atr_ratio_vs_20d | 0.071 | Lower = cleaner |
| 9 | ob_strength | 0.068 | Higher = better |
| 10 | ema_9_slope | 0.061 | With trend = better |

**Insight**: ML model values **signal confluency** most (confluence + BOS + quality account for 45% of prediction power)

---

## 10. FEATURE EXPORT FOR MT5

When signal is exported, include all 30 features in JSON:

```json
{
  "signal_id": "EURUSD_20260601_153000",
  "features": {
    "atr_14": 0.00085,
    "atr_ratio_vs_20d": 0.92,
    "rsi_14": 62.5,
    "ema_9_slope": 0.00015,
    "momentum_5bar": 0.0045,
    "bos_strength": 0.85,
    "fvg_size_atr": 0.85,
    "fvg_age_bars": 4,
    "ob_distance_atr": 1.2,
    "ob_strength": 0.78,
    "choch_severity": 0.0,
    "swing_proximity": 0.92,
    "pullback_depth": 15.0,
    "trend_direction": 1,
    "trend_strength": 0.82,
    "volatility_regime": "MEDIUM",
    "session_type": "EUROPEAN",
    "market_regime": "TRENDING",
    "regime_age_bars": 23,
    "signal_count": 3,
    "bos_present": true,
    "fvg_present": true,
    "ob_present": false,
    "entry_quality": 0.82,
    "confluence_alignment": 0.92,
    "timing_quality": 0.88,
    "sweep_intensity": 0.88,
    "level_stacking": 2,
    "liquidity_score": 0.85,
    "slippage_risk": 0.12
  },
  "feature_version": "1.0",
  "model_version": "xgboost_v2.0.0"
}
```

---

## 11. VALIDATION CHECKLIST FOR FEATURES

Before ML inference, verify:

- [ ] All 30 features present in feature vector
- [ ] All numeric values are finite (not NaN, not inf)
- [ ] ATR-normalized features use current ATR (not stale)
- [ ] RSI between 0-100
- [ ] Slopes in reasonable range (-0.005 to +0.005)
- [ ] Regime and session enumerations valid
- [ ] Boolean features are exactly 0 or 1
- [ ] Feature vector matches training schema
- [ ] Normalization applied consistently
- [ ] Feature timestamps aligned with entry bar

---

## 12. NEXT STEPS

1. **FASE 3**: Features flow becomes part of architecture diagram
2. **FASE 4**: Feature schema finalized in JSON
3. **FASE 5**: feature_extractor.py wrapped in bridge module
4. **FASE 6**: Features passed to MQL5 EA for logging
5. **FASE 7**: Feature reproducibility validated in backtest
