# Telegram Remote Control — Security

## Threat Model

The Telegram agent controls a trading system that could execute financial transactions. Security is the highest priority.

## Authentication

- **Telegram User ID whitelist**: Only configured user IDs can interact with the bot
- No password-based authentication
- No hardcoded secrets (all via `.env`)
- Bot token must never be committed to git

## Authorization

The `permissions.py` module maintains an in-memory set of authorized IDs loaded from `TELEGRAM_AUTHORIZED_USERS` in `.env`.

```
TELEGRAM_AUTHORIZED_USERS=123456789,987654321
```

Multiple IDs can be separated by commas.

## Safe Commands

Potentially destructive commands require explicit confirmation:

| Command | Protection |
|---------|-----------|
| `reset` | Requires `CONFIRM RESET` reply |
| `shutdown` | Requires `CONFIRM SHUTDOWN` reply |
| `hard_reset` | Requires `CONFIRM HARD_RESET` reply |

The bot stores pending confirmations per user ID in memory. If the user sends anything other than the expected confirmation, the operation is cancelled.

## Execution Safety

- Commands go through the execution layer, never directly to shell
- The execution layer can be limited to specific providers
- Timeout: all operations have a 600-second (10 min) timeout
- No trade execution or real funds manipulation via Telegram
- The execution layer only controls the development workflow, not the trading engine

## Network Security

- Bot communicates exclusively via Telegram's HTTPS API
- No open ports required on the machine (outbound HTTPS only to api.telegram.org)
- No custom network protocols
- No web servers

## Data Protection

- No sensitive data stored in git
- `.env` file is gitignored
- Logs contain command names but not tokens
- Task history documents do not contain credentials

## Incident Response

If the bot token is compromised:

1. Revoke the token via [@BotFather](https://t.me/botfather): `/revoke`
2. Generate a new token: `/token`
3. Update `.env` with the new token
4. Restart the agent

If an unauthorized user gains access:

1. Remove their ID from `TELEGRAM_AUTHORIZED_USERS`
2. Restart the agent
3. Revoke and regenerate the bot token
