# DECISIONS.md — Architectural & Technical Decisions

> Every important decision with date and reasoning.

---

### 2026-06-29: TP at 2R based on Structural SL

**Decision**: TP set to 2:1 ratio based on Structural SL distance.

**Reasoning**: ICT methodology typically uses 1:2 risk-reward or better. The structural SL is calculated from the origin swing, and TP is set at 2x that distance. This was the initial implementation choice.

**Revisited**: Backtest shows 78% of trades exit by hold limit (max 16 bars). TP may be too far. A 1.5R target would likely increase win rate at the cost of lower R per trade.

---

### 2026-06-29: Weighted Confluence Scoring adopted

**Decision**: Replace simple filter-based signal confidence with a weighted confluence scorer.

**Components**: PAC 30%, Wyckoff 25%, Exhaustion 20%, Structural SL 15%, ML 10%.

**Regime boosts**: Weights are adjusted by market regime (TRENDING, RANGING, HIGH_VOL, LOW_VOL, CHAOTIC).

**Reasoning**: Different market regimes favor different signal components. Regime-adaptive weighting improves signal quality across market conditions.

---

### 2026-06-29: GridSearchCV for ML training

**Decision**: Use GridSearchCV with 3-fold CV and ROC-AUC scoring when dataset ≥ 200 rows.

**Reasoning**: Automated hyperparameter tuning outperforms manual defaults. The 200-row threshold prevents CV on tiny datasets where it would be unreliable.

---

### 2026-06-29: PAC State Machine as mandatory filter

**Decision**: Scalping signals pass through PAC state machine before being emitted.

**States**: IDLE → FVG_DETECTED → FVG_MITIGATED → EXHAUSTION_CONFIRMED → STRUCTURE_CONFIRMED → ENTRY_SIGNAL.

**Reasoning**: Ensures only price action sequences that follow the complete ICT model (FVG → mitigation → exhaustion → BOS → entry) produce signals. Reduces false positives.

---

### 2026-06-28: Harness-first testing approach

**Decision**: All new modules must pass harness scenarios before integration.

**Reasoning**: Isolated module testing catches regressions early. Every module adapter implements the `ModuleAdapter` protocol with `run(events, parameters) -> dict`.

---

### 2026-06-28: Agent architecture is read-only analysis

**Decision**: Agents analyze market context and return structured evidence. They do not execute trades, set positions, or modify DataFrames.

**Reasoning**: Separation of concerns. The backtest engine and risk governor handle execution. Agents are purely analytical.

---

### 2026-06-28: v4 dataset schema

**Decision**: Drop `agent_decision_ml_probability` (100% NaN), add `year_month` column, bump schema version to v4.

**Reasoning**: The column offers no signal. The `year_month` enables time-based partitioning for walk-forward validation.

---

### 2026-06-30: Telegram Remote Control architecture

**Decision**: Build a modular Telegram agent with provider abstraction layer instead of direct shell execution.

**Components**: `telegram_agent.py`, `command_router.py`, `task_queue.py`, `notifications.py`, `permissions.py`, `session.py`, `execution_layer.py`.

**Provider protocol**: Any provider (OpenCode, Claude Code, Codex, Gemini CLI, local Python) implements `execute(command, context) -> ExecutionResult`. No business logic depends on a specific provider.

**Threading model**: Long-running tasks use `threading.Thread` instead of asyncio to avoid blocking the event loop. Progress callbacks bridge between thread and async.

**Confirmation protocol**: Destructive commands (`reset`, `shutdown`, `hard_reset`) require `CONFIRM <CMD>` reply before execution.

**Reasoning**: Telegram becomes the single remote interface. The provider abstraction allows swapping the AI agent without changing the control layer. Task documentation at `docs/history/` preserves every action.

