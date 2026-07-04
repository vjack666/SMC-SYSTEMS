# SMC Trading System -- Deployment Guide

Practical guide for deploying the SMC (Smart Money Concepts) trading system in production. Covers Windows-native and Linux/Wine deployments, service management, monitoring, and emergency procedures.

---

## 1. Prerequisites

**Software:**
- Python 3.11 or later (3.12+ recommended)
- MetaTrader 5 terminal (build 4000+)
- MT5 demo or live account
- Git

**Python dependencies** (installed via `uv sync` or `pip install -e .`):

```
pyyaml pandas numpy joblib scikit-learn
langgraph langchain pyzmq MetaTrader5
xgboost optuna
```

Optional but recommended:
- `nssm` (Windows Service manager) -- for running the runner as a service
- `wine` / `wine64` (Linux only) -- limited MT5 support via Wine

**Network:**
- Outbound access to the MT5 broker server(s) on port 443
- Stable internet connection (wired Ethernet recommended for VPS)

---

## 2. Environment Setup

**2.1 Create and activate a virtual environment**

```bash
python -m venv venv
```

Activate:

```powershell
# Windows (PowerShell)
venv\Scripts\Activate.ps1

# Windows (cmd)
venv\Scripts\activate.bat

# Linux / macOS
source venv/bin/activate
```

**2.2 Install dependencies**

```bash
uv sync
```

If `uv` is not available:

```bash
pip install -e .
```

**2.3 Configure environment variables**

| Variable | Purpose | Default |
|---|---|---|
| `SMC_LOG_DIR` | Log output directory | `./data/logs` |
| `SMC_DATA_DIR` | Data storage (parquet, CSV) | `./data` |
| `SMC_STATE_DIR` | Persistent state files | `./data` |
| `SMC_MT5_PATH` | Custom MT5 executable path | Autodetected |
| `SMC_MODE` | `PAPER` or `LIVE` | `PAPER` |

Example `.env` or system environment:

```bash
export SMC_LOG_DIR=/opt/smc/logs
export SMC_DATA_DIR=/opt/smc/data
export SMC_STATE_DIR=/opt/smc/state
export SMC_MODE=PAPER
```

On Windows, set via System Properties -> Environment Variables, or in PowerShell:

```powershell
[Environment]::SetEnvironmentVariable("SMC_MODE", "PAPER", "User")
```

**2.4 Verify the setup**

```bash
python -c "import MetaTrader5 as mt5; print(mt5.__version__)"
python -c "import pandas, numpy, joblib, sklearn, xgboost; print('OK')"
```

---

## 3. VPS Deployment (Windows Server)

**3.1 VPS provider options**

| Provider | Recommended for | Notes |
|---|---|---|
| Azure (B2s / B2ms) | Production | Reliable, good latency, desktop experience available |
| AWS EC2 (t3.medium) | Production | Larger instance needed for Windows GUI |
| Hetzner (CX22 / CX32) | Budget / dev | Best price/performance, Windows license extra |
| Contabo | Budget / dev | Cheapest, acceptable for paper trading |

**3.2 Windows VPS setup steps**

1. **Provision the VPS** with Windows Server 2019 or 2022.

2. **Enable desktop experience** (required for MT5 GUI):

   ```powershell
   Install-WindowsFeature -Name Desktop-Experience -IncludeAllSubFeature -Restart
   ```

3. **Install MetaTrader 5:**
   - Download from your broker's website or the official MetaQuotes site
   - Run the installer
   - Launch MT5 once, accept the license, let it initialize

4. **Install Python 3.11+** from python.org (check "Add Python to PATH").

5. **Install Git** (optional but recommended for updates).

6. **Clone the repository:**

   ```powershell
   git clone <repo-url> C:\SMC-SYSTEMS
   cd C:\SMC-SYSTEMS
   python -m venv venv
   venv\Scripts\activate
   pip install -e .
   ```

7. **Configure MT5 for auto-login** (see Section 5).

8. **Set up the startup sequence** (see Section 8).

**3.3 RDP considerations**

- Use a port other than 3389 if exposed to the internet.
- Set up a firewall rule to restrict RDP access to your IP.
- Consider using a VPN (WireGuard/OpenVPN) instead of direct RDP.

---

## 4. Running as a Service

### 4.1 Windows (NSSM)

Install NSSM from https://nssm.cc/download.

```powershell
# Install the service
nssm install SMC "C:\SMC-SYSTEMS\venv\Scripts\python.exe" `
    "C:\SMC-SYSTEMS\scripts\run_paper_trading.py"

# Optionally set the working directory
nssm set SMC AppDirectory "C:\SMC-SYSTEMS"

# Configure automatic restart on failure
nssm set SMC AppExit Default Exit
nssm set SMC AppThrottle 5000

# Set environment variables for the service
nssm set SMC AppEnvironmentExtra SMC_MODE=PAPER SMC_LOG_DIR=C:\SMC-SYSTEMS\data\logs

# Start the service
nssm start SMC

# Check status
nssm status SMC
```

To stop and remove:

```powershell
nssm stop SMC
nssm remove SMC confirm
```

### 4.2 Linux (systemd) -- Wine deployment

Create `/etc/systemd/system/smc-trader.service`:

```ini
[Unit]
Description=SMC Trading System (Wine/MT5)
After=network.target

[Service]
Type=simple
User=smc
WorkingDirectory=/opt/smc
Environment="SMC_MODE=PAPER"
Environment="SMC_LOG_DIR=/opt/smc/logs"
Environment="SMC_DATA_DIR=/opt/smc/data"
Environment="SMC_STATE_DIR=/opt/smc/state"
ExecStart=/opt/smc/venv/bin/python -m paper_trading.runner
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable smc-trader
sudo systemctl start smc-trader
sudo systemctl status smc-trader
```

---

## 5. MT5 Configuration

**5.1 Terminal settings**

- **Auto-login:** Tools -> Options -> Server -> check "Auto login"
- **Enable algo trading:** Tools -> Options -> Expert Advisors -> check "Allow Automated Trading"
- **DLL imports:** Tools -> Options -> Expert Advisors -> check "Allow DLL imports" (if required by the system)
- **News popups:** Tools -> Options -> News -> uncheck "Enable Push notifications" and disable news alerts
- **Chart popups:** Disable all popup notifications that could interrupt operation

**5.2 Market Watch**

- Ensure all traded symbols are visible in Market Watch (Ctrl+M).
- Right-click -> "Show All" if symbols are missing.
- Hide symbols that are not traded to reduce CPU load.

**5.3 Account verification**

Before starting the runner, verify in the terminal:

1. Connection status shows green (lower-left corner).
2. The correct account number and server are displayed.
3. Trade tab shows open positions (if any) matching the persistent state.

**5.4 Auto-start**

Add MT5 to Windows startup (`shell:startup` -> shortcut to `terminal64.exe`):

```
%ProgramFiles%\MetaTrader 5\terminal64.exe
```

Or via Task Scheduler at user logon with "Run with highest privileges" if needed.

---

## 6. Monitoring and Logging

**6.1 Log files**

| File | Location | Contents |
|---|---|---|
| Runner log | `{SMC_LOG_DIR}/paper_trading/runner.log` | Main operational log |
| Trade log | `{SMC_DATA_DIR}/paper_trading/trades.json` | JSON trade records |
| Trade log (CSV) | `{SMC_DATA_DIR}/paper_trading/trades.csv` | Tabular trade history |
| Positions | `{SMC_STATE_DIR}/paper_trading/positions.json` | Persistent position state |
| ML metrics | `{SMC_DATA_DIR}/ml/model_metrics.json` | Model performance metrics |
| Governor log | (in runner.log) | Mode transitions and risk events |

**6.2 Key log patterns to watch**

```text
# Healthy operation -- every poll interval
DATA_REFRESH completed  (X symbols in Y seconds)
GOVERNOR [NORMAL/CAUTION]  drawdown=X%  consecutive_losses=Y

# Warning signs
WARNING  Data refresh timeout for EURUSD
WARNING  Governor transition to CAUTION
ERROR    Order send failed: 10018 (invalid symbol)
CRITICAL Governor transition to DEFENSIVE or LOCKDOWN
```

**6.3 Monitoring commands**

```powershell
# Tail the runner log (PowerShell)
Get-Content -Path "C:\SMC-SYSTEMS\data\paper_trading\runner.log" -Tail 50 -Wait

# Check trade count
python -c "import json; t=json.load(open('data/paper_trading/trades.json')); print(f'{len(t)} trades')"

# Governor state
python -c "
import json
try:
    g=json.load(open('data/paper_trading/governor_state.json'))
    print(f'Mode: {g[\"mode\"]}, DD: {g[\"drawdown\"]:.2f}%, Losses: {g[\"consecutive_losses\"]}')
except: print('No governor state file')
"
```

---

## 7. Kill Switch and Emergency Stop

**7.1 Governor LOCKDOWN (automatic)**

The Governor enters `LOCKDOWN` mode automatically when:
- 5 consecutive losses occur, OR
- Portfolio drawdown exceeds 4%

In `LOCKDOWN`, no new trades are opened. The runner continues to monitor but does not act. Recovery requires manual intervention or resetting the governor state.

**7.2 Manual kill switch (graceful)**

The runner checks for a file at `{SMC_DATA_DIR}/KILL_SWITCH` on every poll iteration.

To trigger a graceful shutdown:

```powershell
echo "triggered" | Out-File -Encoding ascii C:\SMC-SYSTEMS\data\KILL_SWITCH
```

```bash
echo "triggered" > /opt/smc/data/KILL_SWITCH
```

On detecting `KILL_SWITCH`:
1. The runner logs the event.
2. `self.running` is set to `False`.
3. The main loop exits cleanly after the current iteration.
4. Open positions are persisted so they can be reloaded on restart.

**7.3 Emergency stop (hard)**

If the runner is not responding:

```powershell
# Windows: kill by Python process
taskkill /F /IM python.exe

# Find specific Python process
tasklist | findstr python

# Force kill specific PID
taskkill /F /PID <pid>
```

```bash
# Linux
pkill -f paper_trading.runner
kill -9 <pid>
```

After a hard kill:
1. Verify MT5 terminal is still running and connected.
2. Cross-check positions in MT5 against `positions.json`.
3. If there is a mismatch, manually reconcile in MT5 before restarting.
4. Remove the `KILL_SWITCH` file if it was the trigger.
5. Restart the runner -- it reloads positions from `positions.json`.

**7.4 Recovery procedure**

```
1. Remove KILL_SWITCH file       rm data/KILL_SWITCH or del data\KILL_SWITCH
2. Verify MT5 connection         Check terminal status bar
3. Verify position sync          Compare MT5 terminal vs positions.json
4. Reset governor (optional)     Delete data/paper_trading/governor_state.json
5. Restart the runner            nssm start SMC or python -m paper_trading.runner
6. Monitor first 5 minutes       Watch runner.log for errors
```

---

## 8. Startup Sequence

Follow this order every time the system starts:

```text
1. START MT5 terminal
   - Wait for connection (check status bar turns green)
   - Verify Market Watch shows all symbols
   - Verify auto-login succeeds

2. CHECK account info
   - Balance, leverage, margin free
   - Ensure enough margin for at least 1 micro lot

3. VERIFY directories
   - SMC_LOG_DIR exists and is writable
   - SMC_DATA_DIR exists and is writable
   - SMC_STATE_DIR exists and is writable

4. CHECK for KILL_SWITCH
   - If data/KILL_SWITCH exists, remove it
   - Otherwise the runner will shut down immediately

5. START the runner
   - nssm start SMC          (Windows service)
   - or python -m paper_trading.runner   (interactive)

6. VERIFY first data refresh
   - Check runner.log for DATA_REFRESH completed
   - If this fails, restart MT5 and retry

7. MONITOR first 5 minutes
   - Check for errors or warnings
   - Verify Governor state is NORMAL
   - Verify position persistence loaded correctly
```

---

## 9. Health Check

Run these checks periodically (every few hours or via a monitoring script).

**9.1 Runner health**

```powershell
# Check last log activity (should be within last 2 minutes)
Get-Item "C:\SMC-SYSTEMS\data\paper_trading\runner.log" | Select LastWriteTime

# Check for recent errors
Select-String -Path "C:\SMC-SYSTEMS\data\paper_trading\runner.log" -Pattern "(ERROR|CRITICAL)" | Select-Object -Last 10
```

**9.2 MT5 health**

- Terminal should show "Connected" (green indicator).
- Terminal uptime should match expected runtime (check Task Manager).
- If MT5 has been restarted, the runner needs to be restarted too.

**9.3 Position reconciliation**

- Open positions in MT5 should match `positions.json`.
- If mismatched, the runner may double-count or miss positions.
- Discrepancy typically requires manual reconciliation.

**9.4 Governor state**

- Should be `NORMAL` under normal conditions.
- `CAUTION` indicates some losses but acceptable.
- `DEFENSIVE` or `LOCKDOWN` requires investigation.

**9.5 Drawdown monitoring**

- Track peak-to-current drawdown daily.
- If approaching 4%, prepare for LOCKDOWN.
- Consider manual risk reduction before auto-trigger.

---

## 10. Troubleshooting

**10.1 MT5 connection issues**

| Symptom | Cause | Fix |
|---|---|---|
| "No connection" in terminal | Network down or broker server issue | Check internet, restart MT5, try broker status page |
| "Invalid account" | Wrong server or credentials | Verify login/password and server name in MT5 |
| Terminal disconnects periodically | Timeout or firewall | Check firewall rules, increase MT5 timeout settings |
| MT5 crashes silently | Out of memory or disk full | Restart MT5, clear log files, monitor resources |

**10.2 Symbol and data issues**

| Symptom | Cause | Fix |
|---|---|---|
| "Symbol not found" | Symbol not in Market Watch | Right-click Market Watch -> Show All, or add manually |
| Data download fails | Symbol unavailable or connection issue | Check MT5 connection, verify symbol trades on that server |
| Wrong data (gaps, wrong prices) | Broker data feed issue | Compare with another source, try a different timeframe |
| Parquet files corrupted | Abrupt shutdown | Delete corrupted parquet files, they will be re-downloaded |

**10.3 Order and position issues**

| Symptom | Cause | Fix |
|---|---|---|
| "Order send failed: 10018" | Symbol invalid or disabled algo trading | Enable algo trading in MT5, verify symbol |
| "Insufficient money" | Margin exceeded | Reduce position size, deposit funds |
| "Off quotes" | Price moved before order executed | The runner retries; if persistent, check data feed |
| Position mismatch after restart | State file and MT5 out of sync | Manually reconcile in MT5 terminal |

**10.4 ML model issues**

| Symptom | Cause | Fix |
|---|---|---|
| "Model file not found" | Training not run | Run `python -m ml.train` or the model training pipeline |
| "Feature mismatch" | Model trained with different features | Retrain model with current feature set |
| Model returns NaN | Data issue or extreme market | Check input features, falls back to no-trade |
| Optuna study not found | Missing study DB | Run hyperparameter tuning first |

**10.5 File and permission issues**

| Symptom | Cause | Fix |
|---|---|---|
| Permission denied | Logger cannot write to path | Check SMC_LOG_DIR exists and is writable |
| KILL_SWITCH detected on startup | Previous kill file not removed | Delete the KILL_SWITCH file and restart |
| "File in use" on Windows | Another process has the file locked | Restart the runner, avoid opening log files in editors |

**10.6 General checklist when things go wrong**

```
1. Is MT5 running and connected?            -> Restart MT5 if not
2. Is the runner process running?           -> Check task manager / ps
3. Are environment variables set?           -> Check SMC_MODE, SMC_LOG_DIR, etc.
4. Is the KILL_SWITCH file present?         -> Remove if found
5. Is there disk space?                     -> Logs can grow large over weeks
6. Is the governor in LOCKDOWN?             -> Investigate reason, reset state
7. Does positions.json match MT5?           -> Reconcile if not
8. Are all symbols in Market Watch?         -> Show All
9. Is algo trading enabled?                 -> Check MT5 settings
10. Restart MT5 first, then restart runner  -> Solves most connection issues
```
