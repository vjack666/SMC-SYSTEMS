# Wyckoff Implementation Guide for SMC

> **Last updated**: 2026-06-30  
> **Status**: Ready for code implementation  

---

## Implementation Layers

```
┌─────────────────────────────────────────────┐
│ Layer 1: Wyckoff Detector                    │
│ modules/wyckoff/detector.py                  │
│ → Raw event detection (SC, AR, ST, Spring,  │
│   SOS, LPS, Upthrust, SOW, LPSY)            │
│ → Phase classification (Accumulation A-E,    │
│   Distribution A-E, Markup, Markdown)         │
├─────────────────────────────────────────────┤
│ Layer 2: Trend Context Engine                │
│ modules/trend/context_engine.py              │
│ → Merge Wyckoff phase into macro context     │
│ → Phase-trend alignment check                │
├─────────────────────────────────────────────┤
│ Layer 3: Signal Pipeline                     │
│ strategy/scalping_setup.py                   │
│ → Wyckoff filter for confluence scoring      │
│ → Phase-aware signal confidence              │
├─────────────────────────────────────────────┤
│ Layer 4: ML Feature Engineering              │
│ ml/feature_pipeline.py                       │
│ → Wyckoff phase as categorical feature       │
│ → Event counts as numerical features         │
├─────────────────────────────────────────────┤
│ Layer 5: SMC_SUCCESSOR Agents                │
│ smc_successor/agents/wyckoff_agent.py        │
│ → High-level phase analysis + events         │
│ → Integration with Decision Agent            │
└─────────────────────────────────────────────┘
```

---

## Layer 1: Detector Changes

### Fix Bugs

1. **Dead code in `_detect_accumulation_phase()`**:
   - Current: `ACCUMULATION_A` is unreachable (duplicate `if has_sc` blocks)
   - Fix: Change second `if has_sc` to `else` or merge properly

2. **Add distribution detection functions**:
   - `_upthrust()` — break above resistance with reversal
   - `_sign_of_weakness()` — strong bearish candle
   - `_last_point_supply()` — low-volume bounce
   - `_detect_distribution_phase()` — classify distribution A-E

3. **Add output columns**:
   - `wyckoff_upthrust`, `wyckoff_sow`, `wyckoff_lpsy`
   - `wyckoff_distribution_phase` (DISTRIBUTION_A through E)
   - `wyckoff_markup`, `wyckoff_markdown`

### Detection Logic Reference

```python
def _upthrust(data, i, last_dist_high_idx, config):
    """Brief break above resistance, immediate reversal."""
    if last_dist_high_idx < 0 or i <= last_dist_high_idx:
        return False
    if i - last_dist_high_idx > 15:
        return False
    resistance = data.iloc[last_dist_high_idx]["high"]
    break_above = data.iloc[i]["high"] > resistance + config.spring_depth_atr * data.iloc[i]["atr"]
    close_below = data.iloc[i]["close"] < data.iloc[i]["open"]
    return break_above and close_below
```

---

## Layer 2: Context Engine Changes

In `modules/trend/context_engine.py`, after building trend score:

```python
# Add Wyckoff phase info to trend context
if "wyckoff_phase" in data.columns:
    wyckoff_phase = data["wyckoff_phase"].iloc[-1]
    is_accumulation = "ACCUMULATION" in str(wyckoff_phase)
    is_distribution = "DISTRIBUTION" in str(wyckoff_phase)
    is_markup = wyckoff_phase == "MARKUP"
    is_markdown = wyckoff_phase == "MARKDOWN"
    # Adjust trend score based on phase
    if is_markup:
        data["trend_score"] = data["trend_score"].clip(lower=10.0)
    elif is_markdown:
        data["trend_score"] = data["trend_score"].clip(upper=-10.0)
```

---

## Layer 3: Signal Pipeline Changes

### Wyckoff Filter Enhancement

Current:
```python
wyckoff_ok = pd.Series(True, index=data.index)
if config.use_wyckoff and "wyckoff_accumulation" in data.columns:
    wyckoff_ok = wyckoff_ok & data["wyckoff_accumulation"]
data["filter_wyckoff"] = wyckoff_ok
```

Enhanced:
```python
wyckoff_ok = pd.Series(True, index=data.index)
if config.use_wyckoff and "wyckoff_phase" in data.columns:
    # Allow signals aligned with Wyckoff phase
    bullish_phase = data["wyckoff_phase"].isin(["ACCUMULATION_E", "MARKUP"])
    bearish_phase = data["wyckoff_phase"].isin(["DISTRIBUTION_E", "MARKDOWN"])
    wyckoff_ok = (
        (data["macro_direction"] == "BULLISH" & bullish_phase) |
        (data["macro_direction"] == "BEARISH" & bearish_phase)
    )
data["filter_wyckoff"] = wyckoff_ok
```

---

## Layer 4: ML Features

Add to `ml/feature_pipeline.py`:

| Feature | Type | Description |
|---------|------|-------------|
| `wyckoff_phase_code` | int (0-7) | Encoded phase: NONE=0, ACCUMULATION=1, MARKUP=2, DISTRIBUTION=3, MARKDOWN=4 |
| `wyckoff_event_count` | int (0-6) | Number of Wyckoff events in lookback |
| `wyckoff_spring_flag` | bool | Spring detected in last 15 bars |
| `wyckoff_upthrust_flag` | bool | Upthrust detected in last 15 bars |
| `wyckoff_sos_flag` | bool | SOS detected in last 20 bars |
| `wyckoff_accumulation_confidence` | float | 0-1 based on how many phases confirmed |

---

## Layer 5: Agent Integration

### Wyckoff Agent → Decision Agent

The `WyckoffAgent` in `smc_successor/agents/wyckoff_agent.py` already implements:
- Phase classification (Accumulation/Markup/Distribution/Markdown)
- Spring, Upthrust, SOS, SOW, LPS, LPSY detection
- Effort vs Result analysis
- Volume regime detection

**Integration points**:
1. Wire Wyckoff Agent into `DecisionAgent.decide()` with weight 0.30
2. Add Wyckoff phase to agent confidence in `ConfluenceScorer`
3. Use Wyckoff phase to adjust signal confidence (boost if aligned, reduce if conflicting)
