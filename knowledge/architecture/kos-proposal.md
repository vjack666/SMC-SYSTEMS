# KOS Proposal — Knowledge Operating System for SMC_SUCCESSOR

> **Status**: Accepted  
> **Date**: 2026-06-30  
> **Author**: System Architecture  

---

## Problem

SMC_SUCCESSOR spans multiple projects (SMC SYSTEMS, GRID SCAPL 2, GRID_SCALP_COPIA) with ~250+ Python files, 90+ result files, and complex ICT/SMC/Wyckoff domain logic. Without a structured knowledge system:

- Agents start each session blind, wasting time rebuilding context.
- Architectural decisions are lost between sessions.
- Migration roadmap (LEGACY_AUDIT_REPORT.md) is not systematically consulted.
- No formal communication channel between agents and human.

## Proposed Solution

A **Knowledge Operating System (KOS)** — a persistent directory with structured Markdown files that function as the project's long-term memory.

### What KOS Provides

| Capability | Description |
|------------|-------------|
| **Persistent context** | Agents read knowledge/ before any decision, eliminating blind sessions |
| **Decision traceability** | Every architectural decision is timestamped and cross-referenced |
| **Inbox/Outbox** | Formal async communication between agents and human |
| **Versioned architecture** | Superseding, never deleting — full history preserved |
| **Roadmap enforcement** | LEGACY_AUDIT_REPORT.md migration plan is consulted before any change |

### Directory Structure

```
knowledge/
├── architecture/       # System architecture, component designs, proposals
├── decisions/          # Technical decisions with dates and reasoning
├── learnings/          # Discoveries from experiments, backtests, audits
├── references/         # Rulebooks (ICT, Wyckoff), research, external docs
├── inbox/              # Agent-to-human and agent-to-agent messages
└── outbox/             # Responses and confirmations
```

### Integration with Existing Agent Docs

The existing `/agent/` directory handles **session-level** documentation:

| File | Purpose | KOS Relation |
|------|---------|--------------|
| `START.md` | Entry point workflow | Triggers KOS read |
| `SESSION_PROTOCOL.md` | Session rules | References KOS |
| `PROJECT_STATE.md` | Current snapshot | KOS provides the full history |
| `HANDOFF.md` | Session handoff | Written every session |
| `TASKS.md` | Task tracking | Updated every session |
| `DECISIONS.md` | Decision log | Mirrors `knowledge/decisions/` |
| `CHANGELOG.md` | Project history | Summarizes KOS learnings |
| `CONTEXT.md` | Technical memory | Quick reference into KOS |

### Migration Path

1. ✅ Create `knowledge/` directory structure
2. ✅ Write KOS architecture doc (v1)
3. ✅ Wire into `opencode.json` instructions
4. ⬜ Create `knowledge/inbox/` and `knowledge/outbox/` when needed
5. ⬜ Migrate key learnings from `results/` into `knowledge/learnings/`
6. ⬜ Cross-reference `knowledge/decisions/` with `agent/DECISIONS.md`

---

## Risks

| Risk | Mitigation |
|------|------------|
| Knowledge grows stale | Mandatory update at end of every session |
| Duplication with agent docs | Clear boundary: agent/ = session, knowledge/ = permanent |
| Agents ignore KOS | Wired into opencode.json system_prompt + instructions |
| Too much overhead | Start minimal, expand organically as needed |
