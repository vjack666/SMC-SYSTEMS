# Research: Wyckoff-SMC Integration

> **Date**: 2026-06-30  
> **Status**: Completed  
> **Author**: SMC_SUCCESSOR Agent  

---

## Objective

Integrate Wyckoff Method concepts into the existing SMC trading pipeline as a confluence layer. The goal is to use market phase (Accumulation/Markup/Distribution/Markdown) as a contextual filter for SMC detectors (BOS, FVG, CHOCH, OB).

---

## Methodology

1. **Audit existing Wyckoff implementation** (`modules/wyckoff/detector.py`)
2. **Audit existing signal pipeline** (`strategy/scalping_setup.py`)
3. **Audit SMC_SUCCESSOR Wyckoff Agent** (`smc_successor/agents/wyckoff_agent.py`)
4. **Design integration points** across all 5 layers
5. **Document findings and implementation plan**

---

## Findings

### Finding 1: Existing Detector Has Bugs

- `ACCUMULATION_A` is unreachable due to duplicate `if has_sc:` blocks
- Distribution detection (Upthrust, SOW, LPSY) is entirely missing
- Phase classification only covers accumulation (no markup/markdown)

### Finding 2: Signal Pipeline Uses Wyckoff Weakly

Current filter only checks `wyckoff_accumulation` boolean — ignores distribution, markup, and markdown phases. This means:
- Bearish Wyckoff phases (Distribution, Markdown) provide no signal benefit
- Wyckoff contributes to filter_wyckoff even when phase is neutral

### Finding 3: SMC_SUCCESSOR Wyckoff Agent Is Complete

The `WyckoffAgent` in `smc_successor/agents/wyckoff_agent.py` is well-implemented with:
- Full phase classification (Accumulation/Markup/Distribution/Markdown)
- Spring, Upthrust, SOS, SOW, LPS, LPSY detection
- Effort vs Result analysis
- Volume regime detection

However, this agent is in SMC_SUCCESSOR which is not yet wired into the main pipeline.

### Finding 4: No ML Features from Wyckoff

The ML quality filter (`ml/train_quality_model.py`) does not use any Wyckoff-derived features. Given that Wyckoff phase predicts market direction, this is a missed opportunity.

---

## Integration Design

### Layer 1: Detector (HIGH priority)
- Fix dead code in phase detection
- Add distribution detection (mirrors accumulation logic)
- Add Markup/Markdown phase detection based on swing structure

### Layer 2: Context Engine (MEDIUM priority)
- Pass Wyckoff phase through trend context
- No structural changes needed — Wyckoff columns already merged via `detect_wyckoff()`

### Layer 3: Signal Pipeline (HIGH priority)
- Replace boolean `wyckoff_accumulation` filter with phase-aware filter
- Boost signal confidence when phase aligns with direction
- Reduce/cap confidence when phase conflicts

### Layer 4: ML Features (LOW priority)
- Add Wyckoff phase encoding to feature pipeline
- Requires retraining of quality filter model

### Layer 5: Agent Wire-up (MEDIUM priority)
- Wire SMC_SUCCESSOR agents into main pipeline (Fase 4 scope)

---

## Recommended Implementation Order

1. ✅ Wyckoff theory documented in KOS (`knowledge/theories/wyckoff/`)
2. ✅ Implementation guide documented (`knowledge/theories/wyckoff/implementation.md`)
3. 🔲 Fix detector bugs + add distribution detection
4. 🔲 Enhance signal pipeline Wyckoff filter
5. 🔲 Add Wyckoff features to ML pipeline
6. 🔲 Wire into backtest and validate with Harness

---

## Success Criteria

- Backtest PF improves by ≥ 0.10 when Wyckoff is active vs inactive
- Signals in wrong-phase are filtered out (e.g., bullish signals during Markdown)
- Wyckoff phase agrees with macro direction ≥ 60% of the time
- No regressions in existing detector tests
