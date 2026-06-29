# Pullback Audit: Research vs Current System

Date: 2026-05-30
Scope: Compare external pullback research principles with current pullback detector behavior.

## Research Baseline (what is usually recommended)

1. Pullback quality improves when there is clear higher-timeframe trend.
2. Best workflow is multi-timeframe: context on higher TF, pullback execution on lower TF.
3. Pullback should occur near support/resistance or dynamic value (moving averages/structure).
4. Prefer pullback continuation over reversal context.
5. Avoid chaotic and compressed market regimes.
6. Trend alignment across TFs is a key condition.

## Current System Audit

### 1) Multi-timeframe design
Status: PASS

Evidence:
- Trend context from D1/H4 with lower timeframe usage in pullback view.
- File: modules/trend/context_engine.py
- File: modules/pullback/view.py

### 2) Pullback inside trend (not reversal)
Status: PASS

Evidence:
- Requires macro direction from trend score thresholds.
- Invalidates pullback on opposite CHOCH or opposite BOS.
- File: modules/pullback/view.py

### 3) Pullback near value/structure zones
Status: PASS (basic)

Evidence:
- Uses EMA fast/slow zone + FVG/OB anchor proximity.
- File: modules/pullback/view.py

Gap:
- No explicit swing-level support/resistance hierarchy by HTF zone map.

### 4) Regime filtering
Status: PARTIAL PASS

Evidence:
- Rejects LOW_VOL and CHAOTIC for valid pullbacks.
- File: modules/pullback/view.py

Observed behavior on full dataset:
- LOW_VOL valid rate: 0.000000
- CHAOTIC valid rate: 0.000000
- HIGH_VOL valid rate: 0.002188
- TRENDING valid rate: 0.002987
- RANGING valid rate: 0.003715

Gap:
- RANGING currently yields highest valid-rate, which conflicts with stricter trend-pullback doctrine.

### 5) Trend alignment quality gate
Status: PASS (strong)

Observed behavior on full dataset:
- ALIGNED valid rate: 0.010161
- NEUTRAL valid rate: 0.000696
- DIVERGENT valid rate: 0.000000

Interpretation:
- Detector correctly prioritizes aligned trend conditions.

### 6) Practical signal density
Status: RISK

Observed behavior:
- Global valid rate: 0.00256 (768 / 300000)
- EURUSD: 0.00174
- GBPUSD: 0.00207
- XAUUSD: 0.00387

Interpretation:
- Detector is very selective. This can be good for quality, but may under-supply setups unless used as a filter rather than a primary trigger.

## Output Artifacts Used

- results/pullback_audit_global.json
- results/pullback_audit_summary.json
- results/pullback_view_latest.csv

## Audit Conclusion

Overall alignment with research: GOOD.

What is already correct:
1. Multi-timeframe context.
2. Continuation-vs-reversal separation.
3. Structural and zone-based pullback checks.
4. Strong alignment gate.
5. Chaotic/low-vol rejection.

Main gaps to close:
1. Tighten RANGING handling (currently too permissive relative to trend-pullback doctrine).
2. Add HTF structural support/resistance map for pullback destination quality.
3. Add volume quality condition (low-volume retrace / volume expansion on continuation) to reduce false positives.

## Recommended Next Iteration (without changing execution engine)

1. Add explicit rule: valid pullback requires trend_alignment == ALIGNED and regime_state in {TRENDING, HIGH_VOL} by default.
2. Add HTF zone distance feature (distance to recent D1/H4 swing/OB/FVG cluster) and require threshold.
3. Add volume quality pair:
- retrace volume <= rolling median volume
- continuation attempt volume >= rolling median volume
4. Keep pullback module as context-only output and evaluate effect in audit first.
