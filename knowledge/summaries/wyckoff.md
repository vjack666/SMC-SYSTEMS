# Wyckoff — Summary for SMC Pipeline

> **Actionable reference** for integrating Wyckoff phase detection into signals.

---

## Core Concept

The market moves in cycles: **Accumulation → Markup → Distribution → Markdown**.

Trade **with** the phase (bullish in Accumulation/Markup, bearish in Distribution/Markdown).

---

## Phase Detection in Code

| Phase | Module | Key Columns | Direction |
|-------|--------|-------------|-----------|
| Accumulation | `modules/wyckoff/` | `wyckoff_phase` = ACCUMULATION_E | Favor longs |
| Markup | Trend context | HH+HL structure | Longs only |
| Distribution | `modules/wyckoff/` | `wyckoff_phase` = DISTRIBUTION_E | Favor shorts |
| Markdown | Trend context | LH+LL structure | Shorts only |

---

## Integration Points

### Filter
```python
# Phase-aware filter (current is too weak)
phase = data["wyckoff_phase"]
bullish_ok = phase.isin(["ACCUMULATION_E", "MARKUP"])
bearish_ok = phase.isin(["DISTRIBUTION_E", "MARKDOWN"])
```

### Confluence Boost
- Aligned phase + direction: +0.15 confidence
- Conflicting phase + direction: −0.20 confidence
- Spring detected in accumulation: +0.20 bonus
- Upthrust detected in distribution: +0.20 bonus

---

## Quick Reference

| Scenario | Wyckoff Phase | Action |
|----------|---------------|--------|
| Bullish BOS | Accumulation/Markup | ✅ High confidence |
| Bullish BOS | Distribution/Markdown | ❌ Likely fakeout |
| Bearish CHOCH | Distribution/Markdown | ✅ High confidence |
| Bearish CHOCH | Accumulation/Markup | ❌ Likely shakeout |
| FVG + Spring | Accumulation | ✅ High quality setup |
| FVG + Upthrust | Distribution | ✅ High quality setup |
