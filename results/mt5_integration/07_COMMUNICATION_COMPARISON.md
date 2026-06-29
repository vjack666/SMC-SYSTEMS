# FASE 2: MT5 Integration Methods Comparison
## Research on Python ↔ MetaTrader5 Communication Architectures

**Scope**: Compare 6 communication methods for production trading  
**Criteria**: Latency, robustness, maintainability, backtest compatibility, live trading readiness  
**Goal**: Recommend best-fit architecture for SMC SYSTEMS

---

## EXECUTIVE SUMMARY

| Method | Latency | Robustness | Maintainability | Backtest | Live | Recommendation |
|--------|---------|-----------|-----------------|----------|------|-----------------|
| **A) MetaTrader5 Package** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⚠️ Limited | ⭐⭐⭐⭐ | ✅ **PRIMARY** |
| **B) CSV Bridge** | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ✅ **FALLBACK** |
| **C) JSON Bridge** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ Secondary |
| **D) TCP Socket** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⚠️ Difficult | ⭐⭐⭐⭐ | ⭐ Advanced |
| **E) ZeroMQ** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⚠️ Difficult | ⭐⭐⭐⭐⭐ | ⭐ Enterprise |
| **F) REST Local API** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⚠️ Limited | ⭐⭐⭐ | ⭐ If available |

**Recommendation**: **A (MetaTrader5 Package) + B (CSV Bridge) for failover**

---

## 1. METHOD A: MetaTrader5 PYTHON PACKAGE

### Overview
Direct Python integration with MetaTrader5 platform via official `MetaTrader5` package.  
**Official**: Yes (MetaTrader5 LLC)  
**Current**: Package v5.0.45, widely used in production

### Architecture
```
Python Script
    ↓
MetaTrader5 Python Package (import MetaTrader5)
    ↓
MT5 WebAPI / Direct IPC
    ↓
MetaTrader5 Terminal
    ↓
MT5 Strategy Tester / Live Account
```

### Advantages
✅ **Direct integration**: Lowest latency, most reliable  
✅ **Official support**: Maintained by MetaTrader5 developers  
✅ **Rich API**: Can query account, open positions, order history, account info  
✅ **Live trading ready**: Direct connection to live account  
✅ **Backtesting ready**: Can query historical OHLC, run backtest  
✅ **No infrastructure**: No intermediate server needed  
✅ **Event-driven**: Can listen to market events in real-time  
✅ **Feature extraction**: Can query M1/M5/M15/H1/D1 data directly  

### Disadvantages
❌ **MT5 terminal required**: Must run MetaTrader5 on same machine or network  
❌ **Windows/Linux only**: Not available for macOS (MT5 not available for mac)  
❌ **Connection state**: If terminal closes, connection breaks  
❌ **Single account**: One Python process typically per account  
❌ **Authentication**: Credentials stored locally in terminal  
❌ **Backtest limitations**: Strategy Tester has different order model than live trading  

### Connection Code Example

```python
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pandas as pd

# 1. Connect to MT5
if not mt5.initialize(path="C:\\Program Files\\MetaTrader 5\\terminal64.exe"):
    print("Failed to initialize MT5")
    mt5.shutdown()
    quit()

# 2. Login to account
if not mt5.login(account=123456, password="password", server="BrokerServer"):
    print("Login failed")
    mt5.shutdown()
    quit()

# 3. Query account info
account_info = mt5.account_info()
print(f"Balance: {account_info.balance}")
print(f"Equity: {account_info.equity}")
print(f"Free Margin: {account_info.margin_free}")

# 4. Get OHLC data
rates = mt5.copy_rates_from_pos('EURUSD', mt5.TIMEFRAME_H1, 0, 100)
df = pd.DataFrame(rates)

# 5. Send order
order = mt5.order_send({
    'action': mt5.TRADE_ACTION_DEAL,
    'symbol': 'EURUSD',
    'volume': 1.0,
    'type': mt5.ORDER_TYPE_BUY,
    'price': 1.0985,
    'tp': 1.1005,
    'sl': 1.0975,
})

# 6. Check position
positions = mt5.positions_get(symbol='EURUSD')
for pos in positions:
    print(f"Position: {pos.symbol}, Volume: {pos.volume}, Profit: {pos.profit}")

# 7. Close connection
mt5.shutdown()
```

### Latency Profile
```
Python call → IPC → MT5 process → Broker API → Trade Execution
Latency: <10ms (local machine) to <100ms (if remote terminal)
```

### Backtest Integration
```
Option 1: Run Python script that queries historical data, simulates trades
Option 2: Use MT5 Strategy Tester directly (no Python in loop)
Option 3: Hybrid - Python generates signals, EA executes in backtest
```

### Live Trading Integration
```
✅ READY: Direct connection to live account
   - Order placement: Direct
   - Position tracking: Direct
   - Account updates: Direct
   - No additional infrastructure needed
```

### Robustness Considerations
- **Terminal crash**: Script stops working (mitigation: auto-restart, watchdog)
- **Connection loss**: Reconnect logic needed
- **Race conditions**: Multiple processes accessing same account (use locks)
- **Error handling**: Must catch order rejection, network errors, etc.

### Failover Strategy
```
Primary: MetaTrader5 Python package
Fallback: Switch to CSV file bridge if connection lost
Mechanism: Try Python package, fall back to CSV write, with retry logic
```

---

## 2. METHOD B: CSV BRIDGE

### Overview
File-based communication using CSV files as message queue.  
**Simplicity**: Maximum  
**Reliability**: Good (filesystem is stable)  
**Speed**: Slow (file I/O overhead)

### Architecture
```
Python Script
    ↓
Write CSV: signals.csv
    ↓
[Local Filesystem]
    ↓
MT5 EA reads CSV every bar
    ↓
EA opens order based on CSV
    ↓
EA writes trade_results.csv
    ↓
Python reads results.csv
```

### Advantages
✅ **Simplicity**: Minimal coding required, easy to debug  
✅ **Robustness**: Files don't crash, filesystem is reliable  
✅ **Universal**: Works on any OS, any MT5 instance  
✅ **Backtest compatible**: Strategy Tester can read CSV  
✅ **Debugging**: Can inspect CSV files directly  
✅ **No infrastructure**: Just read/write files  
✅ **Language agnostic**: Any language can write CSV (Python, C#, etc.)  
✅ **Async naturally**: File-based is async by nature  

### Disadvantages
❌ **Latency**: File I/O is slow (~50-500ms per transaction)  
❌ **Delay between signals**: Signal generated, written to disk, read by EA, processed on next bar  
❌ **Race conditions**: If Python writes while EA reads, file corruption possible  
❌ **Locking issues**: File locks can cause read/write contention  
❌ **Network**: If MT5 on different machine, network file share is unreliable  
❌ **Timing**: Signals can lag 1-2 bars behind real-time  
❌ **Scaling**: Doesn't scale to many symbols/fast timeframes  

### CSV Schema

**Python → MT5 (signals.csv)**:
```csv
signal_id,timestamp_utc,symbol,direction,entry_price,sl_price,tp_price,risk_usd,ml_score,session
EURUSD_20260601_153000,2026-06-01T15:30:00Z,EURUSD,1,1.09850,1.09750,1.10050,125.00,0.72,EUROPEAN
GBPUSD_20260601_154500,2026-06-01T15:45:00Z,GBPUSD,-1,1.55200,1.55400,1.54800,125.00,0.68,EUROPEAN
```

**MT5 → Python (trade_results.csv)**:
```csv
signal_id,order_id,entry_price,entry_time,exit_price,exit_time,exit_reason,pnl_usd,pnl_r,holding_bars
EURUSD_20260601_153000,123456,1.09851,2026-06-01T15:30:05Z,1.10051,2026-06-01T16:45:12Z,TP_HIT,250.00,2.0,12
```

### Code Example

**Python (Signal Export)**:
```python
import pandas as pd
from datetime import datetime

def export_signals_to_csv(signals: List[Dict], csv_path: str):
    """Export signals to CSV for MT5 EA to read."""
    df = pd.DataFrame(signals)
    
    # Ensure columns in order
    columns = ['signal_id', 'timestamp_utc', 'symbol', 'direction', 
               'entry_price', 'sl_price', 'tp_price', 'risk_usd', 'ml_score']
    df = df[columns]
    
    # Write with locking (atomic write to prevent race condition)
    temp_path = csv_path + '.tmp'
    df.to_csv(temp_path, index=False, float_format='%.8f')
    
    import shutil
    shutil.move(temp_path, csv_path)  # Atomic rename
    
    logger.info(f"Exported {len(df)} signals to {csv_path}")

def read_trade_results_from_csv(csv_path: str) -> pd.DataFrame:
    """Read trade results from MT5 EA."""
    try:
        df = pd.read_csv(csv_path)
        logger.info(f"Read {len(df)} results from {csv_path}")
        return df
    except FileNotFoundError:
        logger.warning(f"Results file not found: {csv_path}")
        return pd.DataFrame()
```

**MQL5 (Signal Import)**:
```mql5
#include <trade.h>

CTrade trade;
string SIGNALS_FILE = "signals.csv";
string RESULTS_FILE = "trade_results.csv";

void OnTick() {
    // Read signals CSV
    int handle = FileOpen(SIGNALS_FILE, FILE_READ | FILE_CSV);
    
    if (handle == INVALID_HANDLE) {
        Print("Cannot open signals file");
        return;
    }
    
    // Skip header
    string header = FileReadString(handle);
    
    // Read each signal
    while (!FileIsEnding(handle)) {
        string line = FileReadString(handle);
        
        // Parse CSV
        string signal_id, symbol, entry_price_str, sl_price_str, tp_price_str;
        int direction;
        
        // Split CSV parsing...
        // Create order if signal matches current bar
        
        if (signal.entry_bar == current_bar) {
            MqlTradeRequest request;
            MqlTradeResult result;
            
            request.action = TRADE_ACTION_DEAL;
            request.symbol = signal.symbol;
            request.type = (signal.direction == 1) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
            request.volume = signal.volume;
            request.price = signal.entry_price;
            request.tp = signal.tp_price;
            request.sl = signal.sl_price;
            request.comment = signal.signal_id;
            
            OrderSend(&request, &result);
            
            // Write result to file
            FileWrite(RESULTS_FILE, result.comment, result.order, ...);
        }
    }
    
    FileClose(handle);
}
```

### Latency Profile
```
Python generates signal
    ↓
Writes CSV (1-5ms)
    ↓
EA reads CSV on next bar (H1 = 1 hour later, best case 1 minute for M1)
    ↓
Order placed on following bar (minimum 1-2 bars delay)
```

**Effective delay**: 1-2 bars (at least 2 bar lags in worst case)

### Backtest Integration
```
✅ READY: Strategy Tester can read CSV files
   - Place EA in Strategy Tester
   - EA reads signals.csv (can be pre-generated by Python)
   - Strategy Tester replays bars, EA executes trades
   - Results written to trade_results.csv
   - Python validates results match expectation
```

### Live Trading Integration
```
⚠️ WORKS BUT SLOW: Real-time gaps possible
   - Python generates signal
   - CSV written to file share (if remote) → latency
   - EA reads on next bar → latency
   - Order placed with potentially 1-2 bar delay
   - For 1-hour candles: Up to 2 hours of delay possible
```

### Robustness Considerations
- **File locking**: Use atomic writes (write to .tmp, then rename)
- **Missing files**: Handle gracefully (no error if file doesn't exist yet)
- **Encoding**: Use UTF-8, specify encoding in code
- **Delimiter**: Use comma, handle edge cases (commas in comments)
- **Network shares**: Can be unreliable over slow connections

---

## 3. METHOD C: JSON BRIDGE

### Overview
JSON-based message format using file I/O or local API.  
**Balance**: Between CSV and TCP complexity  
**Scalability**: Better than CSV for complex signals

### Architecture
```
Python Script (generates signals as JSON)
    ↓
Write signals.json (atomic write)
    ↓
MT5 EA reads signals.json (parse JSON)
    ↓
EA validates schema, places order
    ↓
Write trade_results.json
    ↓
Python reads, validates results
```

### Advantages
✅ **Structured**: JSON schema can be validated  
✅ **Complex data**: Can include nested structures, arrays  
✅ **Human readable**: Easy debugging and inspection  
✅ **Rich format**: Arrays, objects, booleans, null  
✅ **Language support**: Most languages have JSON parsers  
✅ **Schema validation**: Can define exact format expected  

### Disadvantages
❌ **Parsing overhead**: JSON parsing is slower than CSV  
❌ **Still file-based**: Same latency issues as CSV  
❌ **JSON in MQL5**: Not natively supported, requires custom parser  
❌ **Complexity**: More code to parse vs CSV split  
❌ **File locking**: Same issues as CSV  

### JSON Signal Format
```json
{
  "signals": [
    {
      "signal_id": "EURUSD_20260601_153000",
      "timestamp_utc": "2026-06-01T15:30:00Z",
      "symbol": "EURUSD",
      "direction": 1,
      "entry_price": 1.09850,
      "sl_price": 1.09750,
      "tp_price": 1.10050,
      "risk_usd": 125.00,
      "ml_score": 0.72,
      "confidence": 0.88,
      "features": {
        "bos_strength": 0.85,
        "fvg_size_atr": 0.85,
        "confluence_alignment": 0.92
      }
    }
  ],
  "export_timestamp": "2026-06-01T15:30:00Z",
  "version": "1.0"
}
```

### Python Code Example
```python
import json
from typing import List, Dict

def export_signals_to_json(signals: List[Dict], json_path: str):
    """Export signals as JSON."""
    payload = {
        'signals': signals,
        'export_timestamp': datetime.now().isoformat() + 'Z',
        'version': '1.0',
        'count': len(signals)
    }
    
    # Atomic write
    temp_path = json_path + '.tmp'
    with open(temp_path, 'w') as f:
        json.dump(payload, f, indent=2)
    
    import shutil
    shutil.move(temp_path, json_path)
    
    logger.info(f"Exported {len(signals)} signals to JSON")
```

### MQL5 Code Example
```mql5
// MQL5 JSON parsing requires custom code or library
// Simplified example:

class JsonSignal {
public:
    string signal_id;
    string symbol;
    int direction;
    double entry_price;
    double sl_price;
    double tp_price;
    double risk_usd;
};

// Parse JSON line by line (very manual without library)
// Or use external JSON library

void ParseSignalsJson(string json_content) {
    // Manual parsing: find "signal_id", extract value, etc.
    // This is complex and error-prone in MQL5
    
    // Better: use simple JSON library or convert to CSV in Python
}
```

### Latency Profile
```
Same as CSV (file I/O dominated)
Parsing overhead: +5-10ms (negligible compared to file I/O)
```

### Backtest Integration
```
✅ WORKS: Strategy Tester can read JSON files
   - Pre-generate signals as JSON
   - EA parses JSON on each bar
   - Slower than CSV due to parsing
```

---

## 4. METHOD D: TCP SOCKET BRIDGE

### Overview
Direct TCP socket connection between Python and MT5 EA.  
**Speed**: Very fast (network latency only)  
**Complexity**: Moderate (socket programming required)  
**Firewall**: Requires port opening

### Architecture
```
Python Script
    ↓
TCP Socket Client (port 12345)
    ↓
[Network / Localhost]
    ↓
MT5 EA (TCP Server listening on port 12345)
    ↓
Order execution in MT5
```

### Advantages
✅ **Real-time**: Latency ~1-5ms (same machine) to ~50ms (network)  
✅ **Streaming**: Can push updates continuously  
✅ **Two-way**: Python can receive position updates in real-time  
✅ **No files**: No disk I/O, no locking issues  
✅ **Scalable**: Can handle high-frequency signals  

### Disadvantages
❌ **Complexity**: Socket programming required  
❌ **MQL5 limited**: MT5 has limited socket support (no built-in TCP server)  
❌ **Network**: Firewall rules required  
❌ **Error handling**: More complex (timeouts, disconnects)  
❌ **Backtest**: Strategy Tester doesn't support real sockets  
❌ **Debugging**: Hard to inspect messages (not human-readable)  

### Python TCP Client Example
```python
import socket
import json
import threading

class TCPSignalClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
    
    def connect(self):
        """Connect to MT5 EA TCP server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            logger.info(f"Connected to {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.connected = False
    
    def send_signal(self, signal: Dict):
        """Send signal to MT5 EA."""
        if not self.connected:
            logger.warning("Not connected - reconnecting...")
            self.connect()
        
        try:
            message = json.dumps(signal) + '\n'
            self.socket.sendall(message.encode())
            logger.debug(f"Sent signal: {signal['signal_id']}")
        except Exception as e:
            logger.error(f"Send failed: {e}")
            self.connected = False
    
    def receive_update(self) -> Dict:
        """Receive position update from EA."""
        try:
            data = self.socket.recv(4096).decode()
            if data:
                update = json.loads(data.strip())
                return update
        except Exception as e:
            logger.error(f"Receive failed: {e}")
        
        return None
    
    def disconnect(self):
        if self.socket:
            self.socket.close()
            self.connected = False
```

### MQL5 TCP Server (Simplified - Requires external DLL)
```mql5
// MQL5 has limited built-in network support
// Options:
// 1. Use external DLL (complex)
// 2. Use WebSocket bridge
// 3. Use REST API bridge
// 4. Use CSV (fallback)

// Example using external DLL:
#import "kernel32.dll"
int WSAStartup(int version, int& data[]);
#import

// This is complex and not recommended for production
```

### Latency Profile
```
Python sends → Network packet → MT5 receives → Process → MT5 sends order
Latency: 1-50ms depending on network
```

### Backtest Integration
```
❌ DIFFICULT: Strategy Tester doesn't support real TCP sockets
   - Would require DLL implementation
   - Not portable across MT5 terminals
   - Use CSV bridge for backtest instead
```

### Live Trading Integration
```
⚠️ WORKS: Real-time communication possible
   - Direct connection to EA
   - Order placed immediately on signal
   - Requires firewall port opening
   - Requires DLL or external library in MT5
```

---

## 5. METHOD E: ZeroMQ BRIDGE

### Overview
Professional message queue using ZeroMQ (industrial-grade MQ).  
**Enterprise**: Yes  
**Reliability**: Excellent (message persistence, retry logic)  
**Complexity**: Moderate-High

### Architecture
```
Python (ZeroMQ Publisher/Requester)
    ↓
ZeroMQ Broker / Direct Socket
    ↓
MT5 EA (ZeroMQ Subscriber/Responder)
    ↓
Order execution
```

### Advantages
✅ **Reliable**: Message acknowledgment, queuing  
✅ **Scalable**: Can handle many connections  
✅ **Pattern-based**: PUB-SUB, REQ-REP, PUSH-PULL patterns  
✅ **Fast**: Optimized for low-latency messaging  
✅ **Language agnostic**: ZeroMQ available for Python, C++, MQL5  
✅ **Async**: Natural async messaging patterns  

### Disadvantages
❌ **Complexity**: Requires ZeroMQ library  
❌ **MQL5 support**: Limited (requires external library)  
❌ **Learning curve**: More complex patterns to learn  
❌ **Infrastructure**: ZeroMQ broker may need to run separately  
❌ **Backtest**: Doesn't work in Strategy Tester (no real network)  
❌ **Firewall**: Requires port opening  

### Python ZeroMQ Publisher Example
```python
import zmq
import json

class ZeroMQSignalPublisher:
    def __init__(self, port: int = 5555):
        self.port = port
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(f"tcp://*:{port}")
        logger.info(f"ZeroMQ Publisher listening on port {port}")
    
    def publish_signal(self, signal: Dict):
        """Publish signal to subscribed EAs."""
        topic = signal['symbol']  # Can filter by symbol
        message = json.dumps(signal)
        
        # Send: topic + space + message
        self.socket.send(f"{topic} {message}".encode())
        logger.debug(f"Published signal for {topic}")
    
    def close(self):
        self.socket.close()
        self.context.term()

# Usage
publisher = ZeroMQSignalPublisher()
for signal in signals:
    publisher.publish_signal(signal)
```

### MQL5 ZeroMQ Subscriber (with library)
```mql5
// Requires external ZeroMQ library for MQL5

#include "Zmq/Zmq.mqh"

Context context("127.0.0.1", 5555);
Socket socket(context, ZMQ_SUB);

void OnTick() {
    char msg[];
    if (socket.recv(msg) > 0) {
        // Parse JSON message
        // Place order...
    }
}
```

### Latency Profile
```
Python publishes → ZeroMQ network → EA receives → Process
Latency: 1-10ms (same machine) to 50ms (network)
```

---

## 6. METHOD F: REST LOCAL API

### Overview
HTTP REST API running on local machine.  
**If available**: Some MT5 providers offer local REST APIs  
**Consistency**: Varies by broker

### Architecture
```
Python Script
    ↓
HTTP POST /api/signals
    ↓
Local REST Server (Python/Node.js)
    ↓
MT5 EA reads HTTP endpoint OR
Bridge service connects to MT5
    ↓
Order execution
```

### Advantages
✅ **HTTP standard**: Universal protocol  
✅ **Debugging**: Can test with curl/Postman  
✅ **Firewall**: Can use standard ports (80, 443)  
✅ **Async naturally**: HTTP requests are stateless  

### Disadvantages
❌ **Not standard**: Most brokers don't offer local REST API  
❌ **Latency**: HTTP overhead (200-500ms typically)  
❌ **Complexity**: Need to run separate server  
❌ **Backtest**: Doesn't work in Strategy Tester  
❌ **Limited availability**: Check with broker first  

### When This Works
- Some premium MT5 accounts offer REST APIs
- Some EA builders provide REST bridge services
- Some prop firms offer REST for funded accounts

---

## DETAILED COMPARISON TABLE

| Criterion | A: MT5 Pkg | B: CSV | C: JSON | D: TCP | E: ZMQ | F: REST |
|-----------|-----------|-------|--------|--------|--------|---------|
| **Implementation Time** | 2 days | 1 day | 1 day | 3 days | 4 days | 2 days |
| **Python Complexity** | Low | Low | Low | Medium | Medium | Low |
| **MQL5 Complexity** | None | Low | Medium | High* | High* | Medium |
| **Latency (local)** | <10ms | 50-200ms | 60-250ms | 1-5ms | 1-10ms | 100-500ms |
| **Latency (network)** | 50-200ms | 500-2000ms | 600-2500ms | 50-200ms | 50-200ms | 300-1000ms |
| **Backtest Support** | Limited | ✅ Good | ✅ Good | ❌ No | ❌ No | ❌ No |
| **Live Trading** | ✅ Excellent | ⚠️ Works | ⚠️ Works | ✅ Good | ✅ Excellent | ✅ If available |
| **Failure Recovery** | Good | Excellent | Excellent | Medium | Excellent | Good |
| **Scalability** | Good | Limited | Limited | Excellent | Excellent | Medium |
| **Firewall Issues** | No | No | No | Yes | Yes | No |
| **Infrastructure** | MT5 only | Filesystem | Filesystem | Socket | ZMQ broker | REST server |
| **Debugging** | Logs | CSV inspect | JSON inspect | Network sniffer | Network sniffer | HTTP logs |
| **Production Ready** | ✅ YES | ✅ YES | ✅ YES | ⚠️ Yes* | ✅ YES* | ⚠️ Maybe |

*Requires DLL or advanced MQL5 coding

---

## RECOMMENDED ARCHITECTURE

### Primary: Method A (MetaTrader5 Package)

**When to use**:
- MT5 terminal on same machine as Python
- Live trading with direct account connection
- Need lowest latency
- Want direct API access

**Pros**: Best performance, official support, rich API  
**Cons**: Requires MT5 terminal running

**Implementation**:
```python
# 1. Connect
mt5.initialize()
mt5.login(account, password, server)

# 2. Generate signals
signals = generate_trading_signals()

# 3. Place orders
for signal in signals:
    order = mt5.order_send({
        'action': mt5.TRADE_ACTION_DEAL,
        'symbol': signal['symbol'],
        'volume': signal['position_size_lots'],
        'type': signal['direction_to_mt5_type'],
        'price': signal['entry_price'],
        'tp': signal['tp_price'],
        'sl': signal['sl_price']
    })

# 4. Monitor
positions = mt5.positions_get()
```

### Secondary: Method B (CSV Bridge) - **Fallback**

**When to use**:
- MT5 terminal on different machine
- Need reliable, simple failover
- Backtesting with consistent interface
- Cannot use Method A

**Pros**: Simple, reliable, works everywhere  
**Cons**: Slower, 1-2 bar delay typical

**Implementation**:
```python
# 1. Generate signals
signals = generate_trading_signals()

# 2. Export to CSV
export_signals_csv(signals, 'C:/signals.csv')

# 3. Wait for results
import time
time.sleep(2)  # Wait for EA to process

# 4. Read results
results = read_results_csv('C:/trade_results.csv')
```

### For Backtesting: Method B (CSV) Only

**Reason**: Strategy Tester cannot use Method A (no Python execution in tester)

**Flow**:
```
1. Python generates signals from historical data
2. Write signals.csv
3. Run EA in Strategy Tester reading CSV
4. EA executes trades
5. Python validates results.csv matches expectations
```

---

## IMPLEMENTATION DECISION MATRIX

**Choose based on your scenario:**

```
┌─ Do you have MT5 terminal on same machine?
│
├─ YES → Use Method A (MetaTrader5 Package)
│        ├─ Best latency
│        ├─ Direct API
│        ├─ Live trading ready
│        └─ Backtest use Method B
│
└─ NO → Use Method B (CSV Bridge)
        ├─ Works anywhere
        ├─ Simple implementation
        ├─ Slower but reliable
        └─ Backtest with same method
```

**For high-frequency / low-latency:**
- Use Method D (TCP) or E (ZMQ)
- Requires more infrastructure
- Skip if H1 timeframe

**For enterprise / professional:**
- Use Method E (ZMQ)
- Best reliability
- Requires infrastructure investment

---

## MIGRATION PATH

**Phase 1**: Start with Method A (MetaTrader5 Package)
- Get trading system working
- Direct connection, highest reliability
- Lowest implementation time

**Phase 2**: Add Method B (CSV) as fallback
- When Method A connection fails
- Graceful degradation
- Same EA code, different signal source

**Phase 3**: (Optional) Add Method D/E for low-latency
- Only if needed for scalability
- Can implement later when ready
- Don't add complexity too early

---

## CONFIGURATION EXAMPLE (Phase 1+2)

```python
# integration/mt5_bridge/config.py

BRIDGE_CONFIG = {
    'primary_method': 'MT5_PACKAGE',  # Primary
    'fallback_method': 'CSV_BRIDGE',  # Fallback
    
    'mt5_package': {
        'enabled': True,
        'terminal_path': 'C:\\Program Files\\MetaTrader 5\\terminal64.exe',
        'account': 123456,
        'server': 'BROKER_SERVER',
        'retry_max': 3,
        'timeout_sec': 5
    },
    
    'csv_bridge': {
        'enabled': True,
        'signals_file': './data/signals_export.csv',
        'results_file': './data/trade_results.csv',
        'poll_interval_sec': 2,
        'cleanup_old_after_hours': 24
    },
    
    'failover': {
        'auto_switch': True,
        'switch_on_error': True,
        'retry_interval_sec': 30,
        'log_all_switches': True
    }
}
```

---

## CONCLUSION

### Recommended Setup for SMC SYSTEMS

**Architecture**: Hybrid A + B

```
┌─ Python Signal Generation
│
├─ [PRIMARY] Method A: MetaTrader5 Package
│  ├─ Use if MT5 terminal available
│  ├─ Latency: <10ms
│  └─ Live trading ready
│
├─ [FALLBACK] Method B: CSV Bridge
│  ├─ Use if Method A fails
│  ├─ Latency: 50-200ms
│  └─ Always works
│
└─ [BACKTEST] Method B: CSV Bridge
   ├─ Pre-generate signals
   ├─ Run in Strategy Tester
   └─ Validate against Python
```

**Implementation phases**:
1. ✅ Phase 1 (FASE 5): Implement Method A (MT5 Package bridge)
2. ✅ Phase 2 (FASE 5): Add Method B (CSV fallback)
3. ✅ Phase 3 (FASE 7): Backtest using CSV
4. ✅ Phase 4 (FASE 8): Monitor both methods in production

**Success criteria**:
- [ ] Method A connects successfully
- [ ] Signals placed within 1 second
- [ ] Method B fallback works
- [ ] Results synchronized with Python
- [ ] Backtest matches live trading
- [ ] Both methods tested under load

---

## NEXT STEPS

1. **FASE 3**: Integrate Method A + B into target architecture diagram
2. **FASE 4**: Define schemas for Method A API + CSV format
3. **FASE 5**: Implement bridge module using both methods
4. **FASE 6**: MT5 EA with Method A + CSV fallback support
5. **FASE 7**: Backtest validation of both methods
6. **FASE 8**: Production roadmap with monitoring
