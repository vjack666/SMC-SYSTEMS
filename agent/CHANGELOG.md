# CHANGELOG.md — Project Evolution

> Human-readable chronological history.

---

## 2026-06-29: Fase 3 completed — ML Expansion + Weighted Confluence Scoring

- Created `strategy/confluence_scorer.py` with regime-adaptive weighted scoring
- Added 11 new numerical and 2 categorical features to ML pipeline
- Implemented GridSearchCV in `train_quality_model.py` with 3-fold CV
- Added `regime_score` column to regime detector
- Backtest 100k EURUSD M15 shows 55 trades, 54.5% win rate, PF 0.64
- Known issues: LONG trades lose, TP too far, confidence range too narrow
- Pushed Fases 1-3 to GitHub

## 2026-06-29: Fase 2 completed — Stochastic Exhaustion + Wyckoff

- Created `modules/stochastic_exhaustion/` (detector, config, backtest)
- Created `modules/wyckoff/` (detector, config, backtest)
- Added PAC state EXHAUSTION_CONFIRMED
- Integrated both modules into `strategy/scalping_setup.py`
- Added filters `filter_exhaustion`, `filter_wyckoff`
- Max confluence increased from 5 to 7

## 2026-06-28: Fase 1 completed — PAC State Machine + Structural SL

- PAC State Machine connected to main flow via `_apply_pac_to_context()`
- Structural SL activated via `_apply_structural_sl_to_context()`
- FVG detector extended with zone columns
- `ScalpingConfig` amplified with 5 new parameters
- Backtest verified: 5000 bars EURUSD → 6 signals
- First git commit created

## 2026-06-28: Fase 0 completed — Diagnosis + Audit

- Project inventory completed
- Architecture documented
- SMC_SUCCESSOR repository analyzed
- Known problems catalogued
- This changelog started

## 2026-06-30: Telegram Remote Control Agent created

- Created `automation/` module with 8 files:
  - `telegram_agent.py` — main bot loop and message dispatch
  - `command_router.py` — 20 command handlers with task documentation
  - `task_queue.py` — async task queue with progress and cancellation
  - `notifications.py` — event-driven notification dispatch
  - `permissions.py` — Telegram User ID whitelist
  - `session.py` — git state and repository awareness
  - `execution_layer.py` — provider abstraction (OpenCode, Claude, Codex, local Python)
  - `providers/` — pluggable provider implementations
- Created `docs/telegram/` with 4 documentation files (architecture, setup, security, commands)
- Created `.env.example` with all configuration options
- Created `logs/` directory for agent logging
- Provider protocol allows swapping OpenCode, Claude Code, Codex, Gemini CLI, or local Python
- Destructive commands require `CONFIRM <CMD>` reply before execution

## 2026-06-30: Wyckoff detector fix + phase-aware filter + KOS knowledge

- Fixed dead code in `_detect_accumulation_phase()` (ACCUMULATION_A was unreachable)
- Added distribution detection: `_upthrust()`, `_sign_of_weakness()`, `_last_point_supply()`, `_detect_distribution_phase()`
- Added Markup/Markdown phase detection via swing labels + macro direction
- Enhanced `filter_wyckoff` in scalping_setup.py to use phase-aware logic (not just accumulation boolean)
- Added `apply_wyckoff_to_trend()` in context_engine.py for trend confidence adjustment based on phase conflict
- Created `knowledge/theories/wyckoff/` with theory.md + implementation.md
- Created `knowledge/research/completed/2026-06-30-wyckoff-smc-integration.md`
- Created `knowledge/summaries/wyckoff.md` + `knowledge/index.json`

## 2026-06-30: Wyckoff structured knowledge + KOS inbox/outbox

- Created `knowledge/references/wyckoff-theory.md` — comprehensive Wyckoff theory reference
- Created `knowledge/learnings/wyckoff-implementation.md` — implementation audit findings
- Created `knowledge/inbox/` and `knowledge/outbox/` for formal agent communication
- Found 5 issues in Wyckoff detector (dead code, missing distribution, event independence)

## 2026-06-30: KOS + Harness README

- Created `knowledge/` directory with KOS architecture system:
  - `knowledge/architecture/kos-architecture-v1.md` — Knowledge Operating System design
  - `knowledge/architecture/kos-proposal.md` — Proposal and rationale
  - Subdirectories: `decisions/`, `learnings/`, `references/`
- Created `SMC_SUCCESSOR/harness/README.md` — comprehensive Harness documentation
- Updated `opencode.json` with KOS instructions + Spanish system_prompt for autonomous agent behavior
- Agent now reads KOS + Harness + LEGACY_AUDIT_REPORT before any technical decision
