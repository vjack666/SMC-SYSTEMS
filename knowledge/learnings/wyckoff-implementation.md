# Wyckoff Implementation Learnings

> **Date**: 2026-06-30  
> **Source**: Audit of `modules/wyckoff/detector.py` + backtest results  
> **Status**: Verified against source code  

---

## Finding 1: Accumulation-Only Implementation

The Wyckoff detector only implements accumulation phase detection (SC, AR, ST, Spring, SOS, LPS). Distribution phases (Upthrust, SOW, LPSY) are defined in `WYCKOFF_RULEBOOK.md` but not coded.

**Impact**: Wyckoff Agent can only detect bullish accumulation setups. Bearish distribution signals are always `"NONE"`.

**File**: `modules/wyckoff/detector.py` — no `_upthrust()`, `_sign_of_weakness()`, or `_last_point_supply()` functions exist.

---

## Finding 2: NONE Phase Bug

`_detect_accumulation_phase()` has dead code:
```python
if has_sc:
    return "ACCUMULATION_B"  # line 95 — never reached
if has_sc:
    return "ACCUMULATION_A"  # line 97 — unreachable
```
Both branches check `has_sc` — the second is dead. ACCUMULATION_A is never returned.

**Impact**: If only SC is detected (no Spring), the phase returns `"NONE"` instead of `"ACCUMULATION_A"`.

---

## Finding 3: Event Independence

Wyckoff events (SC, AR, ST, Spring, SOS, LPS) are detected independently per bar using `elif` chain:
```python
if _selling_climax(...):     → wyckoff_sc = True
elif _automatic_rally(...):  → wyckoff_ar = True
elif _secondary_test(...):   → wyckoff_st = True
elif _spring(...):           → wyckoff_spring = True
elif _sign_of_strength(...): → wyckoff_sos = True
elif _last_point_support():  → wyckoff_lps = True
```

**Impact**: Only one event can be flagged per bar. If SC and SOS conditions both trigger on the same bar, only SC is recorded. This is likely intentional (events are sequential in theory) but may miss concurrent signals.

---

## Finding 4: Phase Determination Uses Full Window

`_detect_accumulation_phase()` scans a 30-bar window for any occurrence of each event. This means:
- An SC from 25 bars ago still counts toward current phase
- Events are cumulative — once detected, they persist in the window until it slides past

**Impact**: Phase transitions are slow. A bar may be classified as ACCUMULATION_D for many bars after events occurred, even if price has moved on.

---

## Finding 5: No Distribution Detection

Distribution functions (Upthrust, SOW, LPSY) are documented in `WYCKOFF_RULEBOOK.md` but have no code implementation:

| Function | Rulebook | Implementation |
|----------|----------|---------------|
| `_selling_climax()` | ✅ | ✅ |
| `_automatic_rally()` | ✅ | ✅ |
| `_secondary_test()` | ✅ | ✅ |
| `_spring()` | ✅ | ✅ |
| `_sign_of_strength()` | ✅ | ✅ |
| `_last_point_support()` | ✅ | ✅ |
| `_upthrust()` | ✅ | ❌ Missing |
| `_sign_of_weakness()` | ✅ | ❌ Missing |
| `_last_point_supply()` | ✅ | ❌ Missing |
| `_detect_distribution_phase()` | ✅ | ❌ Missing |

---

## Recommendation

1. Fix the dead code in `_detect_accumulation_phase()` (ACCUMULATION_A unreachable)
2. Implement distribution detection (Upthrust, SOW, LPSY, distribution phase)
3. Add `wyckoff_distribution` flag and distribution phase column
4. Wire distribution into Wyckoff Agent and ConfluenceScorer
