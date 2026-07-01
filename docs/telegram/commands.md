# Telegram Remote Control — Commands Reference

## Overview

All commands start with `/`. Arguments follow the command name.

```
/command <arguments>
```

## Commands

### /start

Initialize the bot and get connection status.

```
/start
```

Returns: current branch, active provider, and help hint.

### /status

Show current repository and system status.

```
/status
```

Returns: branch, last commit, dirty state, active provider, pending changes count.

### /summary

Generate a daily summary.

```
/summary
```

Returns: branch, modified files, active tasks, latest commits, documentation generated today, next recommended actions.

### /help

List all available commands or get help for a specific command.

```
/help
/help status
```

### /tasks

Show active and recent tasks.

```
/tasks
```

Returns: list of active tasks with progress, or recent tasks if none active.

### /cancel

Cancel active tasks.

```
/cancel          # cancel all active tasks
/cancel a1b2c3   # cancel specific task
```

### /research

Research a topic using the execution provider.

```
/research what is the current Sharpe ratio
```

Returns: task ID and execution result.

### /implement

Implement a feature or fix described in the argument.

```
/implement add trailing stop to scalping strategy
```

Returns: task ID, progress updates, and final result.

### /test

Run the project test suite.

```
/test
```

Returns: test output. Sends notification if tests fail.

### /backtest

Run a backtest with optional parameters.

```
/backtest
/backtest EURUSD M15 50000
```

Returns: task ID and backtest results.

### /benchmark

Run performance benchmarks.

```
/benchmark
```

Returns: task ID and benchmark results.

### /commit

Stage all changes and commit.

```
/commit
/commit fix: adjust TP ratio to 1.5R
```

Returns: commit output.

### /push

Push committed changes to remote.

```
/push
```

### /pull

Pull latest changes from remote.

```
/pull
```

Notifies on merge conflicts.

### /document

Generate documentation for a topic.

```
/document document the new Wyckoff module
```

Returns: task ID and documentation output.

### /logs

Show the last 30 lines of the Telegram agent log.

```
/logs
```

### /providers

List available execution providers.

```
/providers
```

### /stop

Cancel all active tasks.

```
/stop
```

### /shutdown (safe)

Requires confirmation. Shuts down the Telegram agent.

```
/shutdown
Bot: This operation modifies repository history.
Reply:
CONFIRM SHUTDOWN
```

### /restart

Restart the Telegram agent.

```
/restart
```

## Confirmation Flow

For destructive commands:

```
User: /reset
Bot:  This operation modifies repository history.
      Reply:
      CONFIRM RESET
User: CONFIRM RESET
Bot:  [executes the operation]
```

If the user sends anything else:

```
User: no
Bot:  Cancelled. Expected:
      CONFIRM RESET
```

## Free-form Messages

Non-command messages are treated as tasks and sent to the execution layer:

```
User: optimize the ML quality filter threshold
Bot:  Task #42 queued.
      Processing: 'optimize the ML quality filter threshold'
```

## Adding Custom Commands

In `command_router.py`:

```python
def _cmd_mycommand(self, args: str = "") -> str:
    return f"Result: {args}"

# Register in _register_defaults:
self.register("mycommand", self._cmd_mycommand)
```

Users can then call:

```
/mycommand some arguments
```
