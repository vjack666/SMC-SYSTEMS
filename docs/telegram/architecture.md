# Telegram Remote Control — Architecture

## Overview

The Telegram agent provides a remote control interface for the SMC-SYSTEMS trading system. Authorized users can monitor, control, and develop the system entirely from Telegram.

## System Diagram

```
Telegram Client
       |
       v
  Telegram Bot API
       |
       v
  telegram_agent.py  (main loop, message handling)
       |
       +--> permissions.py      (authorization layer)
       +--> command_router.py    (command -> handler mapping)
       +--> task_queue.py        (async task execution)
       +--> notifications.py     (event-driven alerts)
       +--> session.py           (git/repo state)
       +--> execution_layer.py   (provider abstraction)
              |
              +--> OpenCodeProvider
              +--> LocalPythonProvider
              +--> ClaudeCodeProvider  (future)
              +--> CodexProvider       (future)
```

## Data Flow

1. Message arrives from Telegram
2. `permissions.py` checks if user is authorized
3. For commands: `command_router.py` maps to handler
4. For text: enqueued as task via execution layer
5. Long operations run in `task_queue.py` background thread
6. Progress/completion sent back via `notifications.py` → Telegram

## Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `telegram_agent.py` | Bot initialization, message dispatch, polling loop |
| `command_router.py` | Command registry, handler execution, task documentation |
| `task_queue.py` | Async task queue with progress, cancellation, threading |
| `notifications.py` | Multi-channel notification dispatch |
| `permissions.py` | User authorization via Telegram IDs |
| `session.py` | Git state tracking, repository awareness |
| `execution_layer.py` | Provider abstraction (OpenCode, Claude, etc.) |

## Design Decisions

1. **No direct shell execution**: All commands go through the execution layer, which can be swapped to different providers without changing business logic.

2. **Threading, not asyncio**: Long operations use `threading.Thread` to avoid blocking the async event loop. Progress callbacks bridge between thread and async worlds.

3. **Task documentation**: Every autonomous action generates a timestamped document in `docs/history/`. Nothing disappears.

4. **Confirmation for destruction**: Commands that modify history (`reset`, `hard_reset`, `shutdown`) require explicit `CONFIRM <CMD>` reply.

5. **Provider agnosticism**: The execution layer implements `Provider` protocol. New providers (Claude Code, Codex, Gemini CLI) implement the same protocol and register with `execution_layer.register_provider()`.
