# SMC_SUCCESSOR Trading Model Specification

> Architecture specification for how SMC_SUCCESSOR combines MT5 data, ICT concepts, Wyckoff context, signal confidence, risk governance, and execution into a unified trading pipeline.
> This is a **specification** — not an implementation. Each layer describes what should happen, not how.

---

## Pipeline Overview

```
MT5 Data (raw OHLCV)
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Layer 1: Market Structure                 │
│  Swing highs/lows, HH/HL/LH/LL, trend direction, ranges     │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Layer 2: ICT Concepts                     │
│  BOS, CHOCH, FVG, Order Blocks, Liquidity pools/sweeps,     │
│  Displacement, Premium/Discount zones                       │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                  Layer 3: Wyckoff Context                    │
│  Accumulation / Distribution / Markup / Markdown,            │
│  Springs, Upthrusts, SOS, SOW, LPS, LPSY,                   │
│  Volume analysis, Effort vs Result                           │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                  Layer 4: Signal Confidence                  │
│  Confluence scoring, feature engineering, ML quality filter  │
│  Dynamic threshold adjustment                                │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                  Layer 5: Risk Governor                      │
│  Per-symbol state, consecutive losses, drawdown tracking,    │
│  Mode-based risk multiplier, trade throttling                │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│               Layer 6: Execution (Backtest / Live)           │
│  Trade simulation, SL/TP management, MFE/MAE tracking,       │
│  Dataset collection for ML training                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Market Structure

### Input
- Cleaned OHLCV DataFrame (time, open, high, low, close, tick_volume, spread)
- One row per candle at the trading timeframe (M15 default)

### Processing
1. **Swing Point Detection**
   - Zigzag algorithm: compare each candle's high to neighbours.
   - A swing high is confirmed when both adjacent candles have lower highs.
   - A swing low is confirmed when both adjacent candles have higher lows.
   - Minimum swing distance parameter (in ATR units) to filter noise.
   - Alternative: rolling window peak/trough detection.

2. **Market Structure Labelling**
   - Compare each new swing point to the prior swing point.
   - Label: HH / HL / LH / LL.
   - Determine trend: Bullish (HH+HL), Bearish (LH+LL), Ranging (mixed).

3. **Range Identification**
   - After 3+ touches of both support and resistance, label as a range.
   - Range boundaries: highest high / lowest low within the identified period.
   - Track range duration and number of touches.

### Output
- Labelled swing points with type (HH/HL/LH/LL).
- Current trend direction with confidence level (number of consecutive swings aligned).
- Active ranges (support, resistance, mid-point, width).
- Trend-line slopes for additional structure.

### Future Integration Points
- `smc_successor/detectors/` — new detector for swing point classification.
- `smc_successor/features/engine.py` — add swing point features (distance to last swing, swing count, etc.).

---

## Layer 2: ICT Concepts

### Input
- Market structure from Layer 1.
- Raw OHLCV data.

### Processing

#### BOS Detection
- Input: current market structure trend, last swing high/low.
- Logic: close beyond the swing point in the trend direction.
- Output: BOS signal with direction (bullish/bearish) and strength (based on candle range relative to ATR).

#### CHOCH Detection
- Input: current market structure trend, last swing point.
- Logic: close beyond the swing point **against** the trend direction.
- Output: CHOCH signal with direction and strength.

#### FVG Detection
- Input: 3 consecutive candles.
- Logic: C1 high < C2 low (bearish FVG) or C1 low > C2 high (bullish FVG).
- Fields: FVG top, FVG bottom, gap size (in price and as % of ATR), whether already filled.
- Output: FVG zone with status (unfilled / partially filled / filled / inverted).

#### Order Block Detection
- Input: displacement candle detection + prior candle.
- Logic: last counter-trend candle before a displacement.
- Fields: OB high, OB low, candle direction, age (bars since detection).
- Output: OB zone with strength (based on displacement range).

#### Liquidity Pool Identification
- Input: swing highs and lows.
- Logic: cluster swing highs → buy-side liquidity levels; cluster swing lows → sell-side liquidity levels.
- Fields: level price, pool strength (number of swing points at this level).
- Output: liquidity levels with status (swept / active).

#### Liquidity Sweep Detection
- Input: liquidity pool level + price action.
- Logic: wick beyond the pool level, close back inside, reversal.
- Output: sweep signal with direction and strength.

#### Displacement Detection
- Input: N-bar lookback window.
- Logic: candle with body/range > 2x ATR, small wick proportion (< 30% of range).
- Output: displacement signal with direction and magnitude.

#### Premium / Discount Zones
- Input: a reference range (daily range, swing range, or session range).
- Logic: compute midpoint and Fibonacci levels (0.618, 0.70, 0.79 for discount; 0.382, 0.30, 0.21 for premium).
- Fields: zone type (premium/discount/OTE), distance from current price to OTE.
- Output: zone labels attached to each bar.

### Output
- ICT concept signals per bar (or per swing): one boolean column + strength column for each concept.
- Active zones: FVGs, OBs, liquidity levels with persistence (remain valid until filled / swept / aged out).

### Future Integration Points
- `smc_successor/detectors/` — all existing detectors map to ICT concepts (bos, choch, fvg, ob). The `_strength` and `_detected` columns already exist.
- `smc_successor/features/engine.py` — FVG fill status, OB age, sweep detection, displacement magnitude, premium/discount distance all as new features.
- `smc_successor/signals/pipeline.py` — MTF analysis, premium/discount filtering, OTE conformance.

---

## Layer 3: Wyckoff Context

### Input
- Market structure from Layer 1 (swing points, ranges).
- Volume data (tick_volume).
- ICT signals from Layer 2 (BOS, CHOCH, displacement).

### Processing

#### Phase Identification
1. Detect trading ranges (3+ touches of support/resistance).
2. Classify each range as accumulation or distribution based on:
   - Prior trend direction (accumulation follows markdown; distribution follows markup).
   - Volume behaviour: decreasing at boundaries → more confident.
   - Springs (within accumulation) or Upthrusts (within distribution).
3. Label current phase:
   - **Markup**: above accumulation range, making HH/HL with increasing volume on up-legs.
   - **Markdown**: below distribution range, making LH/LL with increasing volume on down-legs.
   - **Accumulation**: within range after markdown, volume drying up.
   - **Distribution**: within range after markup, volume drying up.
   - **Unknown / Transition**: no clear range or trend.

#### Volume Confirmation
- Compare current candle volume to rolling 20-bar average.
- Classify volume as high (>1.5x), normal (0.5-1.5x), or low (<0.5x).
- Track SOS (high vol up, wide range) and SOW (high vol down, wide range).
- Detect Effort vs Result divergences (2+ consecutive bars of high vol, narrow range).

#### Spring / Upthrust Detection
- Spring: close below range support → close back inside → recovery candle.
- Upthrust: close above range resistance → close back inside → decline candle.
- Validation: nearby LPS (higher low) or LPSY (lower high).

#### Phase Transition Prediction
- Accumulation → Markup: SOS above range + breakout.
- Distribution → Markdown: SOW below range + breakdown.
- Markup → Distribution: range forms + Upthrust + decreasing volume on rallies.
- Markdown → Accumulation: range forms + Spring + decreasing volume on sell-offs.

### Output
- Current Wyckoff phase label.
- Phase confidence (based on number of confirming signals).
- Event flags: Spring_detected, Upthrust_detected, SOS_detected, SOW_detected, LPS_detected, LPSY_detected.
- Volume regime (high / low / normal).
- Effort vs Result divergence flag.

### Future Integration Points
- New module: `smc_successor/wyckoff/detector.py` — phase classification, volume analysis.
- `smc_successor/features/engine.py` — add Wyckoff features (phase label, phase duration, SOS/SOW count, etc.).
- `smc_successor/signals/pipeline.py` — add Wyckoff-based filtering (e.g., only long in accumulation/markup).

---

## Layer 4: Signal Confidence

### Input
- Market structure labels (Layer 1).
- ICT concept signals and zones (Layer 2).
- Wyckoff phase and events (Layer 3).

### Processing

1. **Confluence Scoring**
   - Start with base score of 0.
   - Add points for each aligned ICT concept:
     - +3 for MTF alignment
     - +2 for displacement in trade direction
     - +2 for FVG in trade direction
     - +2 for OB in trade direction
     - +2 for liquidity sweep
     - +1 for BOS in HTF direction
     - +3 for CHOCH in HTF direction
     - +1 for OTE entry
   - Add Wyckoff context bonus:
     - +2 if Wyckoff phase supports the trade direction (accumulation/markup for long; distribution/markdown for short)
     - +1 if a Spring/Upthrust was recently detected
     - +1 for SOS/SOW confirmation

2. **Confidence Mapping**
   - Raw score (0-20) → confidence (0.0-1.0).
   - Sigmoid or linear mapping, configurable.

3. **ML Quality Filter** (optional, requires trained model)
   - Extract feature vector from context + signals.
   - Run model prediction → probability of being a winning trade.
   - Blend with confidence score: `final_confidence = 0.6 * ml_prob + 0.4 * confidence_score`.
   - Compare to dynamic threshold (from risk governor + regime).

### Output
- `confidence_score`: float 0.0-1.0.
- `ml_probability`: float 0.0-1.0 (or fallback to confidence score).
- `confluence_breakdown`: dict with per-concept contribution.
- `allow_trade`: boolean after threshold comparison.

### Future Integration Points
- `smc_successor/signals/pipeline.py` — the existing `signal_confidence` and `confluence_score` columns are the starting point. Extend with ICT-specific and Wyckoff-specific contributions.
- `smc_successor/ml/train.py` — the quality filter is already operational. Features can be extended with ICT/Wyckoff indicators.
- `smc_successor/features/engine.py` — existing `extract_features()` method. Add ICT/Wyckoff features.

---

## Layer 5: Risk Governor

### Input
- Trade signal (direction, confidence, entry, SL, TP).
- Current governor state for the symbol.
- Account balance.

### Processing

1. **State Retrieval**
   - `GovernorPool.get_state(symbol)` → current state (mode, consecutive losses, drawdowns).

2. **Threshold Adjustment**
   - `next_state(current, config)` → compute new mode based on:
     - Consecutive losses (loss streak)
     - Day drawdown % (since market open)
     - Total drawdown % (since session start)
   - Modes: NORMAL → CAUTION → DEFENSIVE → LOCKDOWN.
   - Each mode adds threshold adjustment: 0.00 / 0.03 / 0.08 / 1.00.
   - Mode also adjusts risk multiplier: 1.0 / 0.75 / 0.50 / 0.0.

3. **Trade Filtering**
   - LOCKDOWN mode: no trades allowed.
   - Otherwise, compare `final_confidence >= dynamic_threshold`.

4. **State Update** (after trade)
   - `GovernorPool.update_from_trade(symbol, pnl_r)`:
     - Update consecutive losses (reset to 0 on win, increment on loss).
     - Update day and total drawdown.
     - Recompute mode.

### Output
- `governor_mode`: str (NORMAL / CAUTION / DEFENSIVE / LOCKDOWN).
- `risk_multiplier`: float (1.0 / 0.75 / 0.50 / 0.0).
- `dynamic_threshold`: float (adjusted for current mode).
- `allow_trade`: boolean.

### Future Integration Points
- `smc_successor/risk/governor.py` — already implemented. Extend with:
  - Daily drawdown reset at market open.
  - Time-based decay of consecutive losses (reduce by 1 after N hours without a trade).
  - Per-session tracking (not just per-symbol).
  - Wyckoff phase-aware thresholds (e.g., tighter risk in distribution/markdown for longs).

---

## Layer 6: Execution

### Input
- Trade signal with all metadata (direction, confidence, entry, SL, TP, risk_multiplier).
- Current state (governor mode, account info).
- Market data (candle by candle for backtest, tick-by-tick for live).

### Processing (Backtest Mode)

1. **Trade Simulation**
   - For each signal that passes all filters:
     - Enter at signal price (close of entry candle, or limit if specified).
     - Exit conditions:
       - SL hit → exit at SL.
       - TP hit → exit at TP.
       - Max hold bars exceeded → exit at current close.
     - Record: entry_time, exit_time, direction, entry_price, exit_price, pnl_r, exit_reason.

2. **MFE / MAE Tracking**
   - During trade, track:
     - `max_favorable_excursion` (MFE): max distance price moved in favor of the trade.
     - `max_adverse_excursion` (MAE): max distance price moved against the trade.
   - Normalised by risk (R-multiple).

3. **Dataset Collection**
   - For every signal (accepted or rejected), record a complete feature vector:
     - Core features (price, indicators, ICT, Wyckoff, market structure).
     - Trade outcome (pnl_r, win, exit_reason, MFE, MAE).
     - Governor state (mode, risk_multiplier, threshold).
     - ML prediction (if available).
   - Save as CSV for ML training.

### Output
- `trades.csv`: all executed trades with full metadata.
- `ml_trade_dataset.csv`: all signals with features + outcomes (for training).
- `metrics.json`: aggregate performance metrics.
- `equity_curve.csv`: equity over time.

### Future Integration Points
- `smc_successor/backtest/engine.py` — trade simulation and dataset collection are already implemented.
- `smc_successor/backtest/real/__main__.py` — the real MT5 backtest entry point can be extended with:
  - Multi-symbol parallel execution.
  - Continuous (streaming) mode for paper/live trading.
  - Position tracking (not just one-shot trades).
  - Slippage and commission models.

---

## Data Flow Summary

```
MT5 Terminal
    │ mt5.copy_rates_from_pos()
    ▼
data/raw/{symbol}_{tf}.parquet
    │ pd.read_parquet()
    ▼
Layer 1: Market Structure (detectors)
    │ BOS, CHOCH, FVG, OB, swing points
    ▼
Layer 2: ICT Concepts (detectors + pipeline)
    │ ICT signals, zones, MTF bias
    ▼
Layer 3: Wyckoff Context (new module)
    │ Phase label, volume regime, events
    ▼
Layer 4: Signal Confidence (pipeline + ML)
    │ feature_engine.extract_features() → predict_quality()
    ▼
Layer 5: Risk Governor (governor pool)
    │ mode check → dynamic threshold → allow_trade
    ▼
Layer 6: Execution (backtest engine)
    │ simulate → record → save
    ▼
results/{trades,metrics,equity,dataset}.{csv,json}
```

---

## Implementation Status

| Layer | Component | Status | Location |
|-------|-----------|--------|----------|
| 1 | Swing point detection | ⚠️ Partial | BOS/CHOCH in detectors detect structure breaks; full swing labelling not implemented |
| 1 | Trend direction | ✅ Done | `build_scalping_context` → `macro_direction` column |
| 2 | BOS detection | ✅ Done | `smc_successor/detectors/bos.py` |
| 2 | CHOCH detection | ✅ Done | `smc_successor/detectors/choch.py` |
| 2 | FVG detection | ✅ Done | `smc_successor/detectors/fvg.py` |
| 2 | OB detection | ✅ Done | `smc_successor/detectors/ob.py` |
| 2 | Liquidity sweep | ⚠️ Partial | `sweep` column exists in FVG detector; not formalised |
| 2 | Displacement | ⚠️ Partial | `displacement_strength` in features, no standalone detector |
| 2 | Premium/Discount | ❌ Missing | Not implemented |
| 3 | Wyckoff phase | ❌ Missing | Not implemented |
| 3 | Volume analysis | ⚠️ Partial | `volume_ratio` in features, no Wyckoff logic |
| 3 | Spring/Upthrust | ❌ Missing | Not implemented |
| 4 | Confluence scoring | ✅ Done | `confluence_score` in pipeline |
| 4 | Confidence mapping | ✅ Done | `signal_confidence` = 0.40 + (score/5) * 0.55 |
| 4 | ML quality filter | ✅ Done | `ml/train.py` + `predict_quality` in engine |
| 5 | Governor pool | ✅ Done | `risk/governor.py` — per-symbol state |
| 5 | Threshold adjustment | ✅ Done | `mode_threshold_add` increases threshold per mode |
| 5 | Dynamic threshold | ✅ Done | `DynamicThresholdConfig` in engine |
| 6 | Trade simulation | ✅ Done | `_simulate_trade_with_stats` in engine |
| 6 | Dataset collection | ✅ Done | `dataset_rows` → `ml_trade_dataset.csv` |
| 6 | Metrics computation | ✅ Done | `_compute_metrics` with 9 KPIs |

### Legend
- ✅ Done — implemented and tested
- ⚠️ Partial — implemented but could be extended
- ❌ Missing — not implemented

---

## Architecture Integration Review

Specific integration points for ICT/Wyckoff concepts in the current codebase, based on code audit.

### 1. Detectors — Integration Points

**Location:** `smc_successor/detectors/` (6 files, no base class)

| File | Current Columns | ICT/Wyckoff Gap | Integration |
|------|----------------|------------------|-------------|
| `bos.py` | `bos_direction`, `swing_high`, `swing_low`, `liquidity_sweep_up/down` | Swing high/low labelling (HH/HL/LH/LL) not done | Add `swing_label` column: "HH"/"HL"/"LH"/"LL"/"NONE" |
| `choch.py` | `choch_signal` (string "NONE"/"CHOCH_BULLISH"/"CHOCH_BEARISH") | Uses EMA cross for context; should use structure labels | Refactor to use `swing_label` from bos.py instead of EMA |
| `fvg.py` | `fvg_bullish`, `fvg_bearish`, `fvg_mid` | No `fvg_size` column (used by feature engine but never set) | Add `fvg_size` = abs(gap) in points or ATR units |
| `ob.py` | `ob_bullish`, `ob_bearish`, `ob_top`, `ob_bottom` | No `ob_distance` column (used by feature engine but never set) | Add `ob_distance` = distance from close to nearest OB in ATR units |
| *New* `ict.py` | — | Displacement detector, premium/discount zones, MTF alignment score | Detects displacement candles (range > 2x ATR, wick < 30%), computes zone levels |
| *New* `wyckoff.py` | — | Phase classification, spring/upthrust, SOS/SOW, LPS/LPSY | Range detection, volume analysis, event classification |

**Protocol gap:** No `Detector` base class or Protocol. Each detector is a standalone function. Future detectors should follow the existing convention:
```python
def detect_*(frame: pd.DataFrame, config: SomeConfig | None = None) -> pd.DataFrame
```

---

### 2. Feature Engine — Integration Points

**Location:** `smc_successor/features/engine.py`

#### Features that exist but have broken columns (always 0.0):

| Feature | Column | Issue | Fix |
|---------|--------|-------|-----|
| `fvg_size` | `row["fvg_size"]` | `detect_fvg()` creates `fvg_mid`, not `fvg_size` | Either add `fvg_size` to `detect_fvg()` or remove feature |
| `ob_distance` | `row["ob_distance"]` | `detect_order_blocks()` never sets this column | Either add `ob_distance` to `detect_ob()` or remove feature |
| `choch_strength` | `row["choch_signal"]` | String("CHOCH_BULLISH") → `_safe_num()` → 0.0 | Use boolean detected or numeric strength instead |
| `volatility_regime` | `row["market_regime"]` | Duplicate of `market_regime` feature | Either remove or create a true volatility regime column |

#### ICT/Wyckoff features to add:

| Feature | Source | Type | Notes |
|---------|--------|------|-------|
| `swing_label` | bos.py | categorical | HH/HL/LH/LL — current market structure position |
| `swing_count` | bos.py | int | Number of consecutive HH (uptrend) or LL (downtrend) |
| `fvg_fill_status` | fvg.py | categorical | "unfilled" / "partial" / "filled" / "inverted" |
| `ob_age` | ob.py | int | Bars since the nearest OB was detected |
| `ob_migrated` | ob.py | bool | Price swept below/above OB and reversed |
| `displacement_magnitude` | detector | float | (body range) / (avg range of prior 10 bars) |
| `sweep_detected` | bos.py | bool | Liquidity sweep on this bar |
| `premium_discount_zone` | new | categorical | "premium" / "discount" / "OTE_long" / "OTE_short" |
| `wyckoff_phase` | new | categorical | "accumulation" / "markup" / "distribution" / "markdown" |
| `spring_detected` | new | bool | Spring event at range support |
| `upthrust_detected` | new | bool | Upthrust event at range resistance |
| `SOS_detected` | new | bool | Sign of Strength |
| `SOW_detected` | new | bool | Sign of Weakness |
| `volume_regime` | new | categorical | "high" / "normal" / "low" relative to 20-bar avg |

**One-hot encoding** (existing, extend with new categoricals):
```python
# Current (in build_training_dataset):
("session", "market_regime", "volatility_regime", "d1_bias", "h4_bias", "trend_alignment")
# Extend with:
("swing_label", "fvg_fill_status", "premium_discount_zone", "wyckoff_phase", "volume_regime")
```

---

### 3. Signal Pipeline — Integration Points

**Location:** `smc_successor/signals/pipeline.py`

#### Current filter → confluence mapping:

| Filter | Weight | Part of `confluence_score`? |
|--------|--------|---------------------------|
| `filter_trend` | 1 | ✅ Yes |
| `filter_bos` | 1 | ✅ Yes |
| `filter_ob_fvg` | 1 | ✅ Yes |
| `filter_choch` | 1 | ✅ Yes |
| `filter_swing` | 1 | ✅ Yes |
| `filter_session` | mandatory | ❌ No (required) |
| `filter_atr` | mandatory | ❌ No (required) |
| `filter_volume` | 0 | ❌ No (diagnostics only) |
| `filter_micro` | 0 | ❌ No (diagnostics only) |

#### ICT/Wyckoff filters to add:

| New Filter | Weight | Logic |
|-----------|--------|-------|
| `filter_mtf_alignment` | 3 | HTF and LTF trend direction agree |
| `filter_premium_discount` | 1 | Entry at OTE level → bonus |
| `filter_displacement` | 2 | Displacement present in trade direction |
| `filter_sweep` | 2 | Liquidity sweep detected in opposite direction |
| `filter_wyckoff_phase` | 2 | Wyckoff phase supports trade direction |
| `filter_spring_upthrust` | 1 | Spring (long) or Upthrust (short) recently |

#### Revised `confluence_score` (future):
```python
confluence_score = (
    data["filter_trend"].astype(int)
    + data["filter_bos"].astype(int)
    + data["filter_ob_fvg"].astype(int)
    + data["filter_choch"].astype(int)
    + data["filter_swing"].astype(int)
    + data["filter_mtf_alignment"].astype(int) * 3
    + data["filter_wyckoff_phase"].astype(int) * 2
    + data["filter_displacement"].astype(int) * 2
    + data["filter_sweep"].astype(int) * 2
)
# Total max: 5 + 3 + 2 + 2 + 2 = 14
```

#### Signal confidence formula (future):
```python
data["signal_confidence"] = (0.30 + (confluence_score / 14.0) * 0.65).clip(0.30, 0.95)
```

#### Unused config fields:
- `require_d1_h4_agreement` is declared in `ScalpingConfig` but never read in `build_scalping_context()` — fix or remove.
- `use_confluence_mode` is declared but never read — fix or remove.

---

### 4. ML Features — Integration Points

**Location:** `smc_successor/ml/train.py` (features tuple) + `smc_successor/backtest/engine.py` (feature_row construction)

#### Current `DEFAULT_FEATURES_ML` (28 features):
```
bos_detected, bos_strength, choch_detected, choch_strength,
fvg_detected, fvg_size, ob_detected, ob_distance, liquidity_sweep,
displacement_strength, trend_confidence, ema_distance, ema_slope,
atr, atr_ratio, candle_range_vs_atr, rsi, rsi_slope, volume_ratio,
momentum_strength, spread, sl_distance, tp_distance, rr_ratio,
expected_hold_bars, ml_probability, ml_threshold, risk_multiplier
```

#### Future ICT/Wyckoff features for ML (12 additions):
```
swing_label, swing_consecutive_count, fvg_fill_status, ob_age,
displacement_magnitude, sweep_detected, premium_discount_distance,
wyckoff_phase, wyckoff_phase_duration, spring_upthrust_detected,
volume_regime, effort_result_divergence
```

#### Feature construction in engine.py:
- `feature_row` dict is built in the signal loop (lines 398-409).
- `_build_dataset_row` (lines 417-474) writes to the ML dataset CSV.
- Both places need extension for new features.

---

### 5. Backtest Validation — Integration Points

**Location:** `smc_successor/backtest/engine.py`

#### Current validation:
- `_compute_metrics()` at line 274: 9 KPIs (total_trades, win_rate, profit_factor, drawdowns, sharpe, expectancy).
- `metrics_pass_thresholds()`: hardcoded checks against performance targets.
- Dataset quality log: win_rate_weighted, accepted/rejected counts.

#### ICT/Wyckoff-specific validation to add:

| Validation | Why | How |
|-----------|-----|-----|
| MTF alignment win rate | Does trading with MTF alignment improve win rate? | Compare trades with/without `filter_mtf_alignment` |
| Wyckoff phase win rate | Which phases produce best results? | Group trades by `wyckoff_phase` at entry |
| FVG fill rate | How often do FVGs get filled after entry? | Track status of FVG at entry vs. exit |
| OB age vs win rate | Do older OBs produce worse trades? | Bucket trades by `ob_age` at entry |
| Premium/Discount entry win rate | Does OTE entry outperform? | Compare trades in premium vs. discount vs. OTE |
| Spring/Upthrust accuracy | How often do these events lead to reversal? | Track trades after spring/upthrust |
| SOS/SOW follow-through | How often does SOS lead to markup continuation? | Track trades after SOS/SOW |

#### Dataset quality log enhancement:
```json
{
  "total_rows": 2119,
  "accepted_trades": 2119,
  "rejected_by_ml": 0,
  "win_rate_weighted": 0.346,
  "win_rate_by_wyckoff_phase": {
    "markup": 0.41,
    "accumulation": 0.38,
    "distribution": 0.29,
    "markdown": 0.27,
    "unknown": 0.31
  },
  "win_rate_by_mtf_alignment": {
    "aligned": 0.42,
    "conflicting": 0.28
  }
}
```

---

### 6. Known Codebase Gaps Found During Audit

| Gap | File | Impact | Fix Priority |
|-----|------|--------|-------------|
| `fvg_size` feature always 0.0 | `features/engine.py` + `detectors/fvg.py` | ML feature has zero variance, model ignores it | Medium |
| `ob_distance` feature always 0.0 | `features/engine.py` + `detectors/ob.py` | ML feature has zero variance, model ignores it | Medium |
| `choch_strength` always 0.0 | `features/engine.py` | String coerced to float → always 0 | Low (use `choch_detected` instead) |
| `volatility_regime` duplicates `market_regime` | `features/engine.py` | No separate volatility feature | Low |
| `day_drawdown_pct` never updated | `risk/governor.py` | Governor day-drawdown trigger never activates | High — governor doesn't respect daily DD |
| `require_d1_h4_agreement` never used | `signals/pipeline.py` | Config field declared but dead code | Low — clean up |
| `use_confluence_mode` never used | `signals/pipeline.py` | Config field declared but dead code | Low — clean up |
| `ScalpingConfig` trend params not exposed via CLI | `backtest/real/__main__.py` | Cannot configure trend threshold from CLI | Medium |
| No detector base class/Protocol | `detectors/*.py` | No interface enforcement | Low — convention-based is fine |

### 7. Integration Implementation Order (Suggested)

```
Phase A — Fix broken features (1-2 hours)
  ├── Add fvg_size to detect_fvg()
  ├── Add ob_distance to detect_order_blocks()
  └── Fix day_drawdown_pct in GovernorPool.update_from_trade()

Phase B — Add ICT enhancements (3-5 hours)
  ├── Add swing_label (HH/HL/LH/LL) column to bos.py
  ├── Add displacement detector (displacement_magnitude)
  ├── Add premium/discount zone computation
  └── Add fvg_fill_status tracking

Phase C — Add Wyckoff module (6-10 hours)
  ├── Create wyckoff/detector.py with phase classification
  ├── Add spring/upthrust detection
  ├── Add SOS/SOW detection
  ├── Add volume regime analysis
  └── Wire into build_scalping_context()

Phase D — Final integration (3-5 hours)
  ├── Extend feature engine with all new features
  ├── Extend ML feature set
  ├── Tune confluence scoring weights
  ├── Add new filter columns to pipeline
  └── Update diagnostics and metrics
```
