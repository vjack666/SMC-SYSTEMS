# Deployment Guide — SMC SYSTEMS

> Go-live procedure for the SMC_SUCCESSOR trading system.
> Covers MT5 terminal, EA, Bridge, Signal Pipeline, Monitoring, and Governance.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Week 1 — Environment Setup](#2-week-1--environment-setup)
3. [Week 2 — MT5 & EA Installation](#3-week-2--mt5--ea-installation)
4. [Week 3 — Bridge & ZeroMQ](#4-week-3--bridge--zeromq)
5. [Week 4 — Signal Pipeline & Backtesting](#5-week-4--signal-pipeline--backtesting)
6. [Week 5 — Monitoring & Alerts](#6-week-5--monitoring--alerts)
7. [Week 6 — Governance & Go-Live](#7-week-6--governance--go-live)
8. [Troubleshooting](#8-troubleshooting)
9. [Rollback Procedure](#9-rollback-procedure)

---

## 1. Prerequisites

### Hardware
| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16 GB |
| Disk | 50 GB SSD | 100 GB SSD |
| Network | 10 Mbps | 50 Mbps |

### Software
| Component | Version | Source |
|-----------|---------|--------|
| Windows | 10/11 or Server 2019+ | — |
| Python | 3.12+ | python.org |
| MT5 Terminal | Latest | broker |
| MetaEditor | Bundled with MT5 | — |
| Git | 2.40+ | git-scm.com |

### Repository
```powershell
git clone https://github.com/vjack666/SMC-SYSTEMS.git
cd SMC-SYSTEMS
```

### Python Environment
```powershell
cd SMC_SUCCESSOR
python -m venv .venv
.venv\Scripts\Activate
pip install -e .
```

Verify installation:
```powershell
python -m harness --adapters echo
# Expected: "passed: echo smoke"
```

---

## 2. Week 1 — Environment Setup

### 2.1 Data Directory Structure
```
data/
  raw/            # Parquet OHLC files
  monitoring/     # Equity telemetry, alerts, reports
  governance/     # Model registry, auto-reports
```

Ensure data files exist:
```powershell
# Check for EURUSD M15 parquet data
python -c "from smc_successor._data_legacy import load_frame; print(load_frame('data/raw', 'EURUSD', 'M15').shape)"
# Expected: (50000, 7)
```

### 2.2 Harness Smoke Test
Run all adapters to verify the system is healthy:
```powershell
python -m harness
# All 12 scenarios must pass
```

### 2.3 Configuration Files
Create `config/bridge_config.yaml`:
```yaml
protocol: file
signal_log_dir: signals
heartbeat_interval_sec: 5
command_timeout_ms: 10000
max_retries: 3
```

Create `config/monitoring_config.yaml`:
```yaml
drift_check_interval_min: 60
alert_cooldown_sec: 300
drift_threshold_psi: 0.2
max_alert_history: 100
```

---

## 3. Week 2 — MT5 & EA Installation

### 3.1 Locate MT5 Data Folder
```powershell
# Find the correct terminal data folder
$termDir = "$env:APPDATA\MetaQuotes\Terminal"
Get-ChildItem $termDir -Directory | Where-Object { $_.Name -match '^[A-F0-9]{32}$' } |
  ForEach-Object {
    $origin = Join-Path $_.FullName "origin.txt"
    if (Test-Path $origin) {
      Write-Host "$($_.Name): $(Get-Content $origin -TotalCount 1)"
    }
  }
```

### 3.2 Install the EA
```powershell
# Copy EA files to the correct terminal folder
$brokerId = "908CDDF6DDEF089609CFD48700109B47"  # ForexClub example
$dst = "$env:APPDATA\MetaQuotes\Terminal\$brokerId\MQL5\Experts"
Copy-Item -Recurse -Force "MQL5\SMC_SYSTEMS_BRIDGE" "$dst\"
```

### 3.3 Compile (if modifying source)
```powershell
& "C:\Program Files\ForexClub MT5\metaeditor64.exe" /compile:"$dst\SMC_SYSTEMS_BRIDGE\SMC_SYSTEMS_BRIDGE.mq5"
# Expected: "0 errors, 0 warnings"
```

### 3.4 Attach EA to Chart
1. Open MT5 terminal
2. Drag `SMC_SYSTEMS_BRIDGE.ex5` onto a EURUSD M15 chart
3. Configure parameters:
   - `MagicNumber`: 20260701
   - `SignalDir`: `\Files\signals`
   - `LogLevel`: `Info`
4. Enable Algo Trading (Ctrl+E)
5. Verify `Expert` tab shows: "SMC_SYSTEMS_BRIDGE loaded successfully"

### 3.5 Manual Signal Test
```powershell
# Send a test signal via file mode
python -c "
from integration.mt5_bridge.config import MT5BridgeConfig
from integration.mt5_bridge.exporter import SignalExporter
from integration.mt5_bridge.schema import SignalMessage, SignalAction, OrderType
import tempfile, json
tmp = tempfile.mkdtemp()
cfg = MT5BridgeConfig(protocol='file', base_dir=tmp, signal_log_dir='signals')
exp = SignalExporter(cfg)
exp.start()
exp.send(SignalMessage(signal_id='test_001', symbol='EURUSD', action=SignalAction.BUY, order_type=OrderType.MARKET, volume=0.01, price=1.1050, stop_loss=1.1000, take_profit=1.1150))
exp.stop()
print('Signal file created')
"
```

---

## 4. Week 3 — Bridge & ZeroMQ

### 4.1 File Mode (Development)
File mode is the default and works without ZeroMQ:

```powershell
python -m harness --adapters mt5_bridge
# Expected: "passed: mt5 bridge smoke"
```

### 4.2 ZeroMQ Mode (Production)
Install ZeroMQ:
```powershell
pip install pyzmq
```

Edit `config/bridge_config.yaml`:
```yaml
protocol: zeromq
host: 127.0.0.1
push_port: 5556
pull_port: 5555
pub_port: 5557
command_timeout_ms: 10000
max_retries: 3
```

### 4.3 Start Bridge Orchestrator
```python
from integration.mt5_bridge.config import MT5BridgeConfig
from integration.mt5_bridge.orchestrator import BridgeOrchestrator

config = MT5BridgeConfig(protocol="zeromq")
orchestrator = BridgeOrchestrator(config)
orchestrator.start()
```

### 4.4 Bridge Health Check
```powershell
python -c "
from integration.mt5_bridge.schema import Heartbeat
hb = Heartbeat(source='python', status='ALIVE', uptime_sec=0)
print(f'Heartbeat: {hb.source} | {hb.status}')
"
```

---

## 5. Week 4 — Signal Pipeline & Backtesting

### 5.1 Generate Signals
```powershell
python -c "
from orchestration.backtest_validation_graph import run_validation
result = run_validation(symbol='EURUSD', timeframe='M15')
print(f'Status: {result[\"status\"]}')
print(f'Signals: {len(result[\"signals\"])}')
print(f'Report ({len(result[\"report\"])} chars)')
"
```

### 5.2 Run Full Validation Pipeline
```powershell
python scripts/test_validation_graph.py --symbol EURUSD --timeframe M15 --verbose
```

### 5.3 Compare Python vs EA
The LangGraph validation pipeline automatically:
1. Loads historical data
2. Generates EMA crossover signals
3. Simulates bridge I/O (file or ZeroMQ)
4. Simulates EA execution with slippage
5. Compares Python OHLC-walk P&L vs EA simulation
6. Generates a validation report

---

## 6. Week 5 — Monitoring & Alerts

### 6.1 Start Monitoring
```python
from monitoring import build_monitoring_system
from monitoring.config import MonitoringConfig

config = MonitoringConfig()
system = build_monitoring_system(config)
# system['drift_detector'], system['alerter'], system['equity_telemetry']
```

### 6.2 Configure Alerts
```python
from monitoring.alerter import Alerter

alerter = Alerter()
alert_id = alerter.send("INFO", "System started", "deploy")
print(f"Alert {alert_id} logged")
```

### 6.3 Track Performance
```python
from monitoring.performance_tracker import PerformanceTracker

tracker = PerformanceTracker()
tracker.record_trade(1.1050, 1.1080, 0.01, "BUY")
metrics = tracker.get_metrics()
print(f"Sharpe: {metrics['sharpe_ratio']}")
```

### 6.4 Generate Dashboard
```python
from monitoring.dashboard import generate_dashboard

dashboard = generate_dashboard(alerter, equity_telemetry, tracker)
print(dashboard["performance"]["sharpe_ratio"])
```

### 6.5 Monitoring Smoke Test
```powershell
python -m harness --adapters monitoring
# Expected: "passed: monitoring smoke"
```

---

## 7. Week 6 — Governance & Go-Live

### 7.1 Model Registry
```python
from governance.model_registry import ModelRegistry

registry = ModelRegistry()
model_id = registry.register("smc_v1", "1.0.0", {"sharpe": 1.5}, "models/smc_v1.pkl")
latest = registry.get_latest("smc_v1")
```

### 7.2 Retraining Scheduler
```python
from governance.retraining_scheduler import RetrainingScheduler

scheduler = RetrainingScheduler()
decision = scheduler.check(registry, {"sharpe": 1.3, "total_trades": 120, "last_retraining_trades": 70})
if decision["needs_retraining"]:
    print(f"Retraining needed: {decision['reason']}")
```

### 7.3 Auto Reports
```python
from governance.auto_report_generator import AutoReportGenerator

reporter = AutoReportGenerator()
report = reporter.generate(monitoring_data, registry_data, scheduler_data)
path = reporter.write_report(report)
print(f"Report written to {path}")
```

### 7.4 Governance Smoke Test
```powershell
python -m harness --adapters governance
# Expected: "passed: governance smoke"
```

### 7.5 Full System Test
```powershell
python -m harness
# All 12 scenarios must pass
```

---

## 8. Troubleshooting

### 8.1 EA Not Loading on Chart
| Symptom | Cause | Solution |
|---------|-------|----------|
| "Cannot load" in Experts tab | Wrong data folder | Verify broker ID in `$env:APPDATA\MetaQuotes\Terminal` |
| DLL calls disabled | Security setting | Tools > Options > Expert Advisors > Allow DLL imports |
| Algo Trading disabled | Button not pressed | Ctrl+E to enable |
| Compilation errors | MQL5 syntax | Check metaeditor log, fix includes |

### 8.2 Bridge Connection Issues
| Symptom | Cause | Solution |
|---------|-------|----------|
| ZeroMQ connection refused | Port in use | Change ports in config, restart |
| File mode: no files found | Wrong signal_dir path | Check SignalDir in EA matches exporter path |
| Timeout on send | MT5 not polling | Check EA is attached to chart with Algo Trading on |

### 8.3 Python Environment
| Symptom | Cause | Solution |
|---------|-------|----------|
| ModuleNotFoundError | Package not installed | `pip install -e .` from SMC_SUCCESSOR |
| Harness: Missing adapter | Not registered | Check `harness/__main__.py` ADAPTERS dict |
| FutureWarning | pandas version | Pre-existing, non-blocking |

### 8.4 Monitoring Alerts
| Symptom | Cause | Solution |
|---------|-------|----------|
| No alerts shown | Empty alert history | Trigger a test alert: `alerter.send("INFO", "test", "check")` |
| Drift not detected | Threshold too high | Lower `drift_threshold_psi` in monitoring config |
| Equity file corrupt | Concurrent writes | Add file locking in EquityTelemetry |

---

## 9. Rollback Procedure

### 9.1 Quick Rollback (MT5)
1. Remove EA from chart (right-click > Expert Advisors > Remove)
2. Delete or rename `MQL5\Experts\SMC_SYSTEMS_BRIDGE\`
3. Restart MT5 terminal

### 9.2 Quick Rollback (Python)
```powershell
cd SMC-SYSTEMS
git checkout <previous-stable-tag>
cd SMC_SUCCESSOR
pip install -e .
```

### 9.3 Full Rollback
1. Stop all Python processes (bridge, monitoring, signal pipeline)
2. Remove EA from all charts
3. Restore MT5 data folder from backup
4. Git checkout previous stable commit
5. Rebuild Python environment
6. Verify with harness smoke test

### 9.4 Backup Checklist
| Item | Location | Frequency |
|------|----------|-----------|
| Git repository | GitHub | Every commit |
| MT5 data folder | `%APPDATA%\MetaQuotes\Terminal` | Weekly |
| Monitoring data | `data/monitoring/` | Daily |
| Governance data | `data/governance/` | Daily |
| Bridge config | `config/` | Every change |

---

> **Document version:** 1.0.0
> **Last updated:** 2026-07-02
> **Maintainer:** SMC SYSTEMS Team
