# Wyckoff Theory — Adapted for SMC Trading Systems

> **Version**: 1.0  
> **Last updated**: 2026-06-30  
> **Domain**: Algorithmic trading, ICT/SMC confluence  

---

## Market Cycle

The Wyckoff cycle has four phases that repeat:

```
Accumulation → Markup → Distribution → Markdown → (repeat)
```

| Phase | Price Action | Institutional Activity | SMC Relevance |
|-------|-------------|----------------------|----------------|
| **Accumulation** | Sideways/ranging after downtrend | Smart money accumulates while public sells | Best environment for bullish BOS, FVG, OB |
| **Markup** | Rising HH+HL structure | Price marks up, pullbacks on low volume | Trend context = BULLISH, favor long signals |
| **Distribution** | Sideways/ranging after uptrend | Smart money distributes to public | Best environment for bearish CHOCH, liquidity sweeps |
| **Markdown** | Falling LH+LL structure | Price marks down, bounces on low volume | Trend context = BEARISH, favor short signals |

### SMC Mapping

| Wyckoff Phase | SMC Correlate | Typical ICT Setup |
|---------------|---------------|-------------------|
| Accumulation | Demand zone formation | FVG + OB accumulation → bullish BOS |
| Markup | Trend channel | BOS continuation, FVG mitigation longs |
| Distribution | Supply zone formation | FVG + OB distribution → bearish CHOCH |
| Markdown | Trend channel | BOS continuation, FVG mitigation shorts |

---

## Accumulation Phases A–E

### Phase A — Selling Climax (SC)
- High volume, wide spread panic selling
- Prior downtrend exhausted
- **Detection**: Volume ≥ 1.5x MA, range ≥ 0.8 ATR, close in upper 60% of range

### Phase A — Automatic Rally (AR)
- Sharp bounce after SC
- **Detection**: Within 10 bars of SC, breaks SC high

### Phase B — Secondary Test (ST)
- Retest of SC area on lower volume
- **Detection**: Within 25 bars of SC, near SC low, vol ≤ 1.5x MA

### Phase C — Spring
- Brief break below SC low, immediate reversal
- Final shakeout before markup
- **Detection**: Within 15 bars of SC, low < SC low - 0.3 ATR, close > open

### Phase D — Sign of Strength (SOS)
- Strong wide-range candle above SC high
- **Detection**: Within 20 bars of SC, close > SC high, vol ≥ 1.5x MA, range ≥ 1.0 ATR

### Phase D/E — Last Point of Support (LPS)
- Low-volume pullback after SOS
- **Detection**: Within 15 bars of SOS, low > SC high, narrow range ≤ 0.7 ATR, vol ≤ 1.5x MA

### Phase E — Markup Breakout
- Price breaks above accumulation range resistance on volume

---

## Distribution Phases A–E

### Phase A — Upthrust (UT)
- Brief break above distribution range resistance, immediate reversal
- **Detection**: Within 15 bars of last supply test, high > resistance + 0.3 ATR, close < open

### Phase B — Sign of Weakness (SOW)
- Strong wide-range bearish candle below distribution low
- **Detection**: Within 20 bars of UT, close < reaction low, vol ≥ 1.5x MA, range ≥ 1.0 ATR

### Phase C — Last Point of Supply (LPSY)
- Low-volume bounce after SOW
- **Detection**: Within 15 bars of SOW, high < distribution high, narrow range, vol ≤ 1.5x MA

### Phase D — Markdown Breakdown
- Price breaks below distribution range support on volume

---

## Volume/Price Analysis

| Price | Volume | Interpretation | SMC Action |
|-------|--------|---------------|------------|
| Up | High (↑) | Strong buying, trend healthy | Allow bullish BOS/FVG |
| Up | Low (↓) | Weak buying, divergence | Caution on longs |
| Down | High (↑) | Strong selling, trend healthy | Allow bearish CHOCH |
| Down | Low (↓) | Weak selling, drying up | Watch for accumulation |
| Narrow | Low | Consolidation/indecision | Skip trade |
| Narrow | High | Absorption/climax | Anticipate reversal |

### Effort vs Result

| Effort (Volume) | Result (Range) | Meaning |
|----------------|----------------|---------|
| High | Small | Absorption → reversal imminent |
| High | Large (directional) | Trend continuation |
| Low | Large | Low conviction — suspect move |
| Low | Small | Normal low activity |

---

## Integration with SMC Detectors

### BOS + Wyckoff
- **Bullish BOS in Accumulation/Markup**: High confidence continuation
- **Bullish BOS in Distribution/Markdown**: Low confidence — likely fakeout
- **Bearish BOS in Distribution/Markdown**: High confidence continuation
- **Bearish BOS in Accumulation/Markup**: Low confidence — likely shakeout

### FVG + Wyckoff
- **Bullish FVG in Accumulation**: High quality — smart money positioning
- **Bullish FVG in Distribution**: Low quality — liquidity grab before markdown
- **Bearish FVG in Distribution**: High quality
- **Bearish FVG in Accumulation**: Low quality

### CHOCH + Wyckoff
- **Bullish CHOCH in Accumulation**: Potential transition to Markup (high value)
- **Bearish CHOCH in Distribution**: Potential transition to Markdown (high value)

### OB + Wyckoff
- **OB in Accumulation**: Institutional buying zone (high quality)
- **OB in Distribution**: Institutional selling zone (high quality)

---

## Confluence Weight Suggestions

| Factor | Weight | Notes |
|--------|--------|-------|
| Wyckoff Phase | 0.20–0.35 | Primary market context filter |
| Phase + BOS alignment | +0.15 bonus | Both agree on direction |
| Phase + FVG alignment | +0.10 bonus | FVG in correct phase |
| Spring/Upthrust | +0.20 | High-probability reversal signal |
| SOS/SOW | +0.15 | Confirms phase transition |
| LPS/LPSY | +0.10 | Last pullback before move |
| Phase conflict with MTF | −0.20 | Reduce confidence |
