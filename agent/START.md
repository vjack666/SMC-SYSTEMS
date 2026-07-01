# START.md — Entry Point

When I type only:

```
start
```

the agent must automatically execute the following workflow.

---

## Startup Workflow

1. Confirm current git branch.
2. Run `git status`.
3. Pull latest changes from GitHub.
4. Stop and report merge conflicts if any.
5. Read every document inside `/agent` in this order:

```
START.md
PROJECT_STATE.md
HANDOFF.md
TASKS.md
DECISIONS.md
CHANGELOG.md
CONTEXT.md
SESSION_PROTOCOL.md
```

6. Read the repository README.
7. Locate every roadmap, architecture or planning document in the repository.
8. Read the Harness documentation completely.
9. Extract every project rule, coding standard, validation rule and autonomous workflow from the Harness.
10. Build an internal understanding of the current project state.
11. Produce a short startup summary including:

- Current objective
- Current implementation status
- Pending tasks
- Current priorities
- Possible blockers

12. Wait for instructions.

## Rule

The agent must never start modifying code automatically after startup.
