# Wyckoff Theory — Structured Reference

> **Source**: Wyckoff Method (Richard D. Wyckoff)  
> **Applied in**: SMC_SUCCESSOR Wyckoff Agent + `modules/wyckoff/detector.py`  
> **Last updated**: 2026-06-30  

---

## Market Cycle

```
Accumulation → Markup → Distribution → Markdown
      ↑                                      │
      └──────────────────────────────────────┘
```

| Phase | Character | Institutional Activity |
|-------|-----------|----------------------|
| Accumulation | Sideways/ranging | Buying while public sells |
| Markup | Rising price | Price up, pullbacks low volume |
| Distribution | Sideways/ranging | Selling while public buys |
| Markdown | Falling price | Price down, bounces low volume |

---

## Accumulation Phases A–E

### Phase A — Selling Climax (SC)
- High volume, wide spread, closes upper half
- Prior downtrend exhausted, panic selling absorbed
- **Detection**: `_selling_climax()` — vol ≥ 1.5x MA, range ≥ 0.8 ATR, close ≥ 60% of range

### Phase A — Automatic Rally (AR)
- Bounce after SC, higher high than SC
- **Detection**: `_automatic_rally()` — within 10 bars of SC, breaks SC high

### Phase B — Secondary Test (ST)
- Retest of SC area on lower volume
- **Detection**: `_secondary_test()` — within 25 bars of SC, low within 0.3 ATR of SC low, vol ≤ 1.5x MA

### Phase C — Spring
- Brief break below SC low with immediate reversal
- Final shakeout before markup
- **Detection**: `_spring()` — within 15 bars of SC, low < SC low - 0.3 ATR, close > open

### Phase D — Sign of Strength (SOS)
- Strong up move above SC high with volume
- **Detection**: `_sign_of_strength()` — within 20 bars of SC, close > SC high, vol ≥ 1.5x MA, range ≥ 1.0 ATR

### Phase D/E — Last Point of Support (LPS)
- Pullback to support after SOS on low volume
- **Detection**: `_last_point_support()` — within 15 bars of SOS, low > SC high, range ≤ 0.7 ATR, vol ≤ 1.5x MA

### Phase E — Markup Begins
- All A–D events confirmed → breakout above accumulation range

---

## Key Events

| Event | Code | Volume | Price Action | Lookback |
|-------|------|--------|-------------|----------|
| Selling Climax | SC | ≥ 1.5x MA | Wide range, closes upper | — |
| Automatic Rally | AR | Any | Higher high than SC | ≤ 10 bars after SC |
| Secondary Test | ST | ≤ 1.5x MA | Retest near SC low | ≤ 25 bars after SC |
| Spring | SP | Any | Break below SC low, reverse | ≤ 15 bars after SC |
| Sign of Strength | SOS | ≥ 1.5x MA | Wide range, above SC high | ≤ 20 bars after SC |
| Last Point Support | LPS | ≤ 1.5x MA | Narrow range, above SC high | ≤ 15 bars after SOS |

---

## Phase Detection Logic

```python
# Accumulation phase determined by completed events within lookback:
ACCUMULATION_A = SC detected
ACCUMULATION_B = SC + Spring
ACCUMULATION_C = SC + Spring + SOS
ACCUMULATION_D = SC + Spring + SOS + LPS
ACCUMULATION_E = All A–E events confirmed → confluence high
```

**Lookback window**: 30 bars (`config.phase_lookback`)

---

## Volume/Price Relationships

| Price | Volume | Interpretation |
|-------|--------|---------------|
| Up | Up | Strong buying (markup, SOS, breakout) |
| Up | Down | Weak buying (potential distribution) |
| Down | Up | Strong selling (markdown, SOW, breakdown) |
| Down | Down | Weak selling (accumulation, drying up) |
| Narrow | Low | Indecision/consolidation |
| Narrow | High | Potential climax/turning point |

**Volume spike**: > 2x 20-bar MA significant  
**Volume drought**: < 0.5x 20-bar MA indicates disinterest

---

## Effort vs Result

| Effort (Volume) | Result (Range) | Interpretation |
|----------------|----------------|----------------|
| High | Small | Absorption → potential reversal |
| High | Large (trend) | Healthy trend continuation |
| Low | Large | Low-conviction move |
| Low | Small | Low activity, consolidation |

**Detection**: 2+ consecutive bars of divergence → absorption likely.

---

## Implementation Details

**Module**: `modules/wyckoff/detector.py`  
**Config**: `modules/wyckoff/config.py`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `swing_lookback` | 5 | Bars for swing detection |
| `volume_threshold` | 1.5 | Multiplier for volume MA |
| `phase_lookback` | 30 | Window for phase classification |
| `spring_depth_atr` | 0.3 | Spring break depth in ATR |
| `sos_min_atr` | 1.0 | Min SOS candle range in ATR |
| `lps_max_atr` | 0.7 | Max LPS candle range in ATR |

**Integration**: Called from `build_scalping_context()` in pipeline. Wyckoff detection runs per-symbol per-bar with a 30-bar phase lookback.

**Wyckoff Agent** (`smc_successor/agents/wyckoff_agent.py`): Reads detector output columns and returns `AnalysisResult` with bias, confidence, detected events.

---

## Constraints

- **Accumulation only**: Current implementation detects accumulation events. Distribution detection (Upthrust, SOW, LPSY) is not implemented.
- **Lookback dependency**: Events within lookback window are counted. If no SC found, no accumulation phases are detected.
- **No volume data fallback**: `tick_volume` column must be present. Falls back to `1.0` if missing.
- **Swing prerequisite**: Requires swing detection (`modules/swing/`) for structure context.
