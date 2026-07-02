# MT5 Bridge Module (F5)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PYTHON ENGINE                             │
│  ┌────────────┐  ┌────────────┐  ┌───────────────────────┐  │
│  │ Orchestrator│  │  Exporter  │  │       Receiver         │  │
│  │  (lifecycle │──│  (send)    │  │  (poll/drain results)  │  │
│  │   mgmt)     │  │            │  │                        │  │
│  └────────────┘  └─────┬──────┘  └──────┬────────────────┘  │
│                         │                │                    │
└─────────────────────────┼────────────────┼────────────────────┘
                          │                │
              ┌───────────▼────────────────▼───────────┐
              │         TRANSPORT LAYER                  │
              │   (ZeroMQ / File / Direct MT5 API)       │
              └───────────┬────────────────▲───────────┘
                          │                │
┌─────────────────────────┼────────────────┼────────────────────┐
│                         │                │                    │
│  ┌──────────────────────▼──┐  ┌──────────┴───────────────┐  │
│  │    MT5 EA (MQL5)         │  │   Account / Symbol Info  │  │
│  │    - receives signals     │  │     (quotes, balance,    │  │
│  │    - executes orders      │──│     positions, orders)   │  │
│  │    - sends results back   │  │                          │  │
│  └─────────────────────────┘  └──────────────────────────┘  │
│                    METATRADER 5                               │
└──────────────────────────────────────────────────────────────┘
```

## Data Flow

### Python → MT5 (Signal)
1. ML engine / signal pipeline produces a `SignalMessage`.
2. `MT5BridgeAdapter.send_signal()` serializes it via `SignalExporter`.
3. Transporter delivers it to the MT5 EA (ZeroMQ push / file write / direct API).
4. EA parses, validates, executes the order, and logs the result.

### MT5 → Python (Result / Status)
1. After execution, EA sends a `TradeResult` back via the transport.
2. `MT5Receiver.poll()` collects incoming messages periodically.
3. Downstream components consume `TradeResult`, `AccountStatus`, or `Heartbeat`.

## Protocol Recommendation

| Protocol | Latency  | Complexity | Reliability | Use Case                    |
|----------|----------|------------|-------------|-----------------------------|
| ZeroMQ   | Low      | Medium     | High        | **Recommended** for prod    |
| File     | High     | Low        | Medium      | Development / debugging     |
| Direct   | Lowest   | High       | High        | Same-process (Python EA)    |

**Primary recommendation:** ZeroMQ over TCP with PUSH/PULL pattern for signals
and PUB/SUB for account status / heartbeats. This gives low latency, loose
coupling, and built-in reconnection.

## File Structure

```
smc_successor/integration/mt5_bridge/
├── __init__.py          # Public exports
├── config.py            # MT5BridgeConfig dataclass
├── schema.py            # Data contracts (SignalMessage, TradeResult, etc.)
├── exporter.py          # SignalExporter (Python → MT5)
├── receiver.py          # MT5Receiver (MT5 → Python)
├── orchestrator.py      # MT5BridgeAdapter (lifecycle + orchestration)
└── README.md            # This file
```

## Next Steps (F5 implementation)

- [ ] Implement ZeroMQ transport in exporter & receiver
- [ ] Write MQL5 EA stub (signal consumer + result publisher)
- [ ] Add serialization tests (round-trip schema ↔ dict ↔ JSON)
- [ ] Integration test: exporter → file → receiver
- [ ] Integration test: Python ↔ MT5 via ZeroMQ (requires MT5 terminal)
- [ ] Add `AccountStatus` polling from MT5 account info
- [ ] Error handling / reconnection logic
