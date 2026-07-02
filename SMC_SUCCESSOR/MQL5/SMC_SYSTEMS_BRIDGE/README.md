# SMC_SYSTEMS_BRIDGE — MQL5 EA (F6)

## Overview

This Expert Advisor (EA) connects the Python trading engine (`SMC_SUCCESSOR`) to
MetaTrader 5. It polls for JSON signal files written by the Python bridge module
(`integration/mt5_bridge/exporter.py`), executes the corresponding orders, and
writes result JSON files back for the Python receiver to consume.

## Communication Protocol

| Direction | Format | File Pattern | Polled By |
|-----------|--------|-------------|-----------|
| Python → EA | `signal_{id}.json` | `signals/signal_*.json` | EA (OnTimer) |
| EA → Python | `result_{id}.json` | `signals/result_*.json` | Python (Receiver) |
| EA → Python | Heartbeat | `signals/heartbeat_mt5.json` | Python (Receiver) |
| EA → Python | Account status | `signals/account_status.json` | Python (Receiver) |

The JSON schema matches the Python contracts in `integration/mt5_bridge/schema.py`:
- **SignalMessage**: signal_id, symbol, action, order_type, volume, price, stop_loss, take_profit, comment, magic_number
- **TradeResult**: signal_id, ticket, code (0=OK), message, filled_volume, fill_price, commission, swap, profit
- **AccountStatus**: account_id, balance, equity, margin, margin_free, margin_level, floating_pnl, open_positions
- **Heartbeat**: source, status, uptime_sec, errors_last_window

## File Structure

```
MQL5/SMC_SYSTEMS_BRIDGE/
├── SMC_SYSTEMS_BRIDGE.mq5        # Main EA entry point
├── includes/
│   ├── JSONParser.mqh             # Minimal JSON read/write helpers
│   ├── SignalReceiver.mqh         # Poll + parse signal files
│   ├── OrderManager.mqh           # Execute buy/sell/close/modify orders
│   ├── AccountMonitor.mqh         # Send heartbeat + account status
│   └── Logger.mqh                 # File + terminal logger
└── README.md                      # This file
```

## How to Install & Compile

### 1. Copy files to MT5

Copy the entire `SMC_SYSTEMS_BRIDGE/` folder into your MT5 `MQL5` directory:

**Terminal path:**
```
C:\Program Files\ForexClub MT5\MQL5\Experts\SMC_SYSTEMS_BRIDGE\
```

Or use the terminal's built-in MetaEditor:
1. Open MetaEditor (F4 in MT5).
2. File → Open Data Folder → navigate to `MQL5\Experts\`.
3. Copy `SMC_SYSTEMS_BRIDGE/` there.

### 2. Compile

In MetaEditor:
1. Open `SMC_SYSTEMS_BRIDGE.mq5`.
2. Press F7 (Compile).

Verify no errors in the compilation log.

### 3. Attach to a chart

1. In MT5, open a chart (e.g., EURUSD M15).
2. Drag `SMC_SYSTEMS_BRIDGE` from the Navigator panel onto the chart.
3. Configure inputs:
   - `InpSignalsDir` — Must match the Python exporter's `signal_log_dir` (default: `signals`).
   - `InpMagicNumber` — Unique identifier (default: 20260701).
   - `InpHeartbeatSec` — Heartbeat frequency (default: 5).
   - `InpDefaultVolume` — Fallback volume if signal omits it.

### 4. Start the Python bridge

From `SMC_SUCCESSOR/`:
```bash
python -c "from integration.mt5_bridge.orchestrator import MT5BridgeAdapter; b=MT5BridgeAdapter(); b.start()"
```

## Configuration Notes

- The signals directory is relative to `TerminalDataPath\Files\`.
- Both Python and MT5 processes must point to the same directory.
- The EA uses `EventSetTimer(1)` — polls for new signals every 1 second.
- Magic number must be unique to avoid interference with other EAs.

## Next Steps (F6 implementation)

- [ ] Implement ZeroMQ transport for lower latency (align with F5)
- [ ] Add risk management (max drawdown, daily loss limits)
- [ ] Add signal validation (symbol check, volume limits)
- [ ] Implement order partial fill / retry logic
- [ ] Add unit tests (MQL5 script or Python-side validation)
