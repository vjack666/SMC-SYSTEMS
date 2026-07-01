# SESSION_PROTOCOL.md — Mandatory Workflow

Every work session must follow this protocol.

---

## Startup

- Run `git status`.
- Run `git pull` (origin main).
- Read all agent documentation under `/agent/`.
- Read the Harness documentation (`SMC_SUCCESSOR/harness/`).
- Read any roadmap or planning documents found.
- Build internal context before making any changes.

---

## During Development

- Follow all rules defined in the Harness documentation.
- Preserve existing architecture. Do not restructure without explicit approval.
- Avoid regressions: verify that previously working functionality still works.
- Validate before finishing: run tests, type checks, lint.
- Update documentation when decisions change.

---

## End of Session

1. Update `PROJECT_STATE.md` with current architecture and milestone status.
2. Update `HANDOFF.md` with completed work, remaining tasks, modified files, validation status, and recommended next step.
3. Update `TASKS.md` — move finished items to Completed, update In Progress / Next.
4. Update `CHANGELOG.md` with a human-readable summary of changes.
5. Stage all relevant changes.
6. Commit with a descriptive message following conventional commits format.
7. Push to GitHub.
