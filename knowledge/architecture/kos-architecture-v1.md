# KOS Architecture v1 — Knowledge Operating System

> **Version**: 1.0  
> **Date**: 2026-06-30  
> **Status**: Active  

---

## Purpose

KOS is the persistent memory and decision framework for SMC_SUCCESSOR agents. It ensures every session resumes exactly where the previous one ended, without requiring human explanation.

---

## Directory Layout

```
knowledge/
├── architecture/       # System architecture & component design
│   ├── kos-architecture-v1.md
│   └── kos-proposal.md
├── decisions/          # Technical decisions (mirrors agent/DECISIONS.md)
├── learnings/          # Discoveries, patterns, experimental results
└── references/         # External docs, rulebooks, research papers
```

---

## Core Principles

1. **Knowledge before action** — Every technical decision must be preceded by reading relevant knowledge.
2. **Inbox/Outbox communication** — Formal async messaging between agents and systems.
3. **Versioned knowledge** — Architecture docs use v1, v2, etc. Old versions are never deleted, only superseded.
4. **Self-documenting** — Every session updates at least one knowledge file.
5. **Harness-first validation** — All new modules must pass harness scenarios before knowledge is updated.

---

## Communication Protocol

### Inbox (`knowledge/inbox/`)

Agents write structured messages to signal needs, blockers, or requests.

```
---
to: "human | agent:<name>"
from: "agent:<name>"
type: "request | report | blocker | proposal"
subject: "<short description>"
---
Body content...
```

### Outbox (`knowledge/outbox/`)

Agents read responses and confirmations from here.

```
---
in_reply_to: "<message_id>"
status: "accepted | rejected | needs_clarification"
---
Response body...
```

---

## Agent Memory Flow

```
START.md triggers workflow
        │
        ▼
Read knowledge/ before any decision
        │
        ▼
Consult LEGACY_AUDIT_REPORT.md for roadmap
        │
        ▼
Execute task following Harness rules
        │
        ▼
Update knowledge/ with results
        │
        ▼
Update agent docs (PROJECT_STATE, HANDOFF, TASKS, CHANGELOG, CONTEXT)
        │
        ▼
Commit & push
```

---

## Constraints

- `knowledge/` is the single source of truth. Duplication is permitted only for cross-referencing.
- Agents never delete knowledge, only add or supersede.
- Superseded docs must link to their replacement.
- All knowledge files use Markdown with YAML frontmatter.
