# Telegram Remote Control — Setup Guide

## Prerequisites

- Python 3.11+
- `python-telegram-bot` library
- `python-dotenv` library
- A Telegram Bot Token (from [@BotFather](https://t.me/botfather))

## Installation

### 1. Install dependencies

```bash
pip install python-telegram-bot python-dotenv
```

### 2. Create a Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot`
3. Choose a name and username
4. Copy the API token

### 3. Get your Telegram User ID

1. Search for [@userinfobot](https://t.me/userinfobot) on Telegram
2. Send `/start`
3. Copy your numeric ID

### 4. Configure `.env`

Copy `.env.example` to `.env` and fill in:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklmNOPqrSTUvwxYZ
TELEGRAM_AUTHORIZED_USERS=123456789
REPOSITORY_PATH=C:\Users\SECRETARIA DORADO\SMC-SYSTEMS
ACTIVE_PROVIDER=local_python
LOG_LEVEL=INFO
```

### 5. Run the agent

```bash
python -m automation.telegram_agent
```

Or activate the virtual environment first:

```bash
.venv\Scripts\python.exe -m automation.telegram_agent
```

## Verifying Installation

1. Open Telegram
2. Find your bot
3. Send `/start`
4. Bot should reply with status

## Running as Background Service

### Windows (Scheduled Task)

1. Open Task Scheduler
2. Create a new task
3. Trigger: At startup
4. Action: Start a program
   - Program: `.venv\Scripts\python.exe`
   - Arguments: `-m automation.telegram_agent`
   - Start in: `C:\Users\SECRETARIA DORADO\SMC-SYSTEMS`

### Windows (Startup Script)

Create `start_telegram_agent.bat`:

```batch
@echo off
cd /d C:\Users\SECRETARIA DORADO\SMC-SYSTEMS
.venv\Scripts\python.exe -m automation.telegram_agent
```

Place in `shell:startup`.
