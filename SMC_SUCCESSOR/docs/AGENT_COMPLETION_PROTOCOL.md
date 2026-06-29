# Agent Task Completion Protocol

## Purpose

Standardise how agents signal task completion to prevent premature termination and ensure all verification steps execute before reporting done.

## Required Steps

When any task reaches completion, the agent MUST execute the following in order:

### 1. Verification

Run all applicable checks:

- **Tests**: `python -m pytest -xvs --no-header` (or targeted subset)
- **Lint/Type checks**: If configured for the project (`ruff`, `mypy`, `pyright`, etc.)
- **Execution validation**: When the task produces a runnable artifact (model, dataset, script), verify it loads/executes without error

Do NOT skip verification because "it worked before." Every change requires re-verification.

### 2. Final Report

Produce a structured report containing:

- **Files changed**: Paths and summary of what was modified
- **Tests/Results**: Pass/fail count, any regressions
- **Errors found**: Any issues discovered during verification
- **Next recommended step**: One concrete follow-up action

### 3. Completion Notification

After verification passes:

```
[console]::beep(1000,500)
TASK COMPLETED
```

- Do NOT trigger the notification before verification finishes.
- Do NOT use fake completion messages.
- Completion means the requested task is actually validated — all tests pass, all assertions hold, no known regressions.

## When to Trigger

| Scenario | Action |
|----------|--------|
| Single self-contained task | Verify, report, notify |
| Multi-step task chain | Verify each step, notify only at final step |
| Exploratory / research-only | Skip notification, provide findings |
| Error / blocked | Report blocker, do NOT notify |

## Integration

This protocol is part of the permanent agent instructions. Every future task follows these rules automatically.
