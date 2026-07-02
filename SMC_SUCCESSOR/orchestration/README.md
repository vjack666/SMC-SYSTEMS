# LangGraph — F7 Backtest Validation

## Why LangGraph?

LangGraph provides a structured, observable way to orchestrate multi-step
validation pipelines. Instead of chaining functions manually or writing a
monolithic script, the validation flow is expressed as a **directed graph**
where each node is an independent, testable unit.

Key benefits for F7:
- **Modularity** — each validation step is its own node (load, signal, bridge, ea, compare, report).
- **Observability** — state is explicit; easy to inspect, debug, and resume from any point.
- **Testability** — nodes can be tested in isolation via the harness.
- **Extensibility** — branching/conditional edges can be added later (e.g., retry on failure, parallel simulation).

## Graph Structure

```
load_data ──→ generate_signals ──→ simulate_bridge ──→ simulate_ea
                                                          │
                                                          ▼
                                                   compare_results
                                                          │
                                                          ▼
                                                   generate_report ──→ END
```

### Nodes

| Node | Description | Status |
|------|-------------|--------|
| `load_data` | Load OHLC data via `_data_legacy.load_frame()` | ✅ Active |
| `generate_signals` | Produce SignalMessage objects from data | ✅ Active (sample logic) |
| `simulate_bridge` | Simulate Bridge Module sending signals | ✅ Active |
| `simulate_ea` | Execute via `MT5BacktestRunner` (slippage, fills) | ✅ Active |
| `compare_results` | Compare Python vs EA trades via `TradeComparator` | ✅ Active |
| `generate_report` | Produce text report via `ReportGenerator` | ✅ Active |

## State Schema

```python
class ValidationState(TypedDict):
    symbol: str
    timeframe: str
    data_dir: str
    total_bars: int
    signals: list[dict]
    bridge_results: list[dict]
    ea_results: list[dict]
    comparison: dict | None
    report: str
    status: str
    errors: list[str]
```

## Usage

```python
from orchestration.backtest_validation_graph import run_validation

result = run_validation(symbol="EURUSD", timeframe="M15")
print(result["status"])
print(result["report"][:500])
```

## Next Steps

- [ ] Replace `generate_signals` with real signal pipeline adapter
- [ ] Add conditional edges (retry on error, abort on critical failure)
- [ ] Add checkpointing (resume from last completed node)
- [ ] Integrate with harness for automated validation runs
- [ ] Add parallel signal generation / EA simulation
