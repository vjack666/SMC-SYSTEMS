# Deployment Guide (F8)

## Overview

This document covers the deployment of SMC-SYSTEMS for production trading.

**Status:** Reference-only. Apply AFTER all other phases are complete and validated.

---

## 1. Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8+ GB |
| Disk | 20 GB SSD | 50 GB SSD |
| Network | 10 Mbps | 50+ Mbps stable |
| OS | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |

## 2. Dependencies

```bash
# System
sudo apt-get update && sudo apt-get install -y python3.12 python3.12-venv git build-essential

# Python
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 3. MT5 Bridge (Windows VPS Only)

MT5 runs on Windows. Options:
- **Dedicated Windows VPS** + reverse SSH tunnel to Linux
- **Wine** (experimental, not recommended for production)
- **MT5 EA** that writes to shared folder / API

Configuration in `config/bridge.yaml`:
```yaml
mt5:
  symbol: EURUSD
  timeframe: M15
  data_dir: /data/mt5
  terminal_path: "C:/Program Files/MetaTrader 5/terminal64.exe"
```

## 4. Systemd Service

```ini
[Unit]
Description=SMC-SYSTEMS Trading Bot
After=network.target

[Service]
Type=simple
User=trading
WorkingDirectory=/opt/smc-systems
ExecStart=/opt/smc-systems/.venv/bin/python -m runner
Restart=on-failure
RestartSec=10
Environment=PYTHONPATH=/opt/smc-systems

[Install]
WantedBy=multi-user.target
```

## 5. Monitoring & Alerting

- **Health check endpoint** (if REST API enabled): `GET /health`
- **Logs**: `journalctl -u smc-systems -f`
- **Kill switch**: Place file at `config/KILL_SWITCH` to halt trading
- **Notifications**: Configure webhook URL in `config/alerts.yaml`

## 6. Recovery

1. Stop service: `sudo systemctl stop smc-systems`
2. Check logs: `journalctl -u smc-systems -n 100 --no-pager`
3. Fix issue
4. Restart: `sudo systemctl start smc-systems`

## 7. Backup

```bash
# Daily backup of models and config
tar -czf /backups/smc-$(date +%Y%m%d).tar.gz models/ config/ data/
```

## 8. Security

- Run as non-root user
- Use environment variables for MT5 credentials
- Never commit `.env` to git
- Restrict SSH to key-based auth only
- Use fail2ban for brute force protection
