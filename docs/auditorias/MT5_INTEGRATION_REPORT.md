# MT5 Integration Report — SMC_SUCCESSOR

## Status: CONNECTED

| Component | Status | Notes |
|-----------|--------|-------|
| MT5 Terminal | ✅ Connected | ForexClub MT5 — Account 500236073 |
| Symbol Discovery | ✅ Available | `mt5.symbols_get()` returns all tradeable symbols |
| Historical Data | ✅ Downloading | M1 through D1 via `copy_rates_from_pos()` |
| Parquet Persistence | ✅ Working | `data/raw/{symbol}_{timeframe}.parquet` |
| Real Backtest | ✅ Working | 91 trades across 4 symbols from real data |
| Test Suite | ✅ Passing | All harness scenarios + pytest suite |

---

## 1. Does MT5 connect correctly?

**Yes.** Connection via `mt5.initialize()` validated with `mt5.terminal_info()`. Three modes:

```python
# Context manager (recommended)
with MT5Connector() as mt5:
    info = mt5.terminal_info()

# Explicit
connector = MT5Connector()
connector.connect()
connector.disconnect()

# Lazy auto-connect
connector.ensure_connected()
```

Retries up to 3 times with 2-second delays on transient failures.

**Known issues:**
- MT5 terminal must be running and logged in
- No automatic reconnection on disconnect
- `connection refused` raised as `ConnectionError` with MT5 error code

---

## 2. Are the candles real?

**Yes.** Downloaded via `mt5.copy_rates_from_pos()` — MT5 server native OHLCV.

| Field | Source | Verified |
|-------|--------|----------|
| `time` | Unix seconds → UTC datetime | ✅ `pd.to_datetime(time, unit='s', utc=True)` |
| `open` / `high` / `low` / `close` | MT5 rate | ✅ |
| `tick_volume` | MT5 rate | ✅ |
| `spread` | MT5 rate | ✅ |

---

## 3. Does the backtest use downloaded data?

**Yes.** The backtest pipeline:

1. Connects to MT5
2. Checks `data/raw/` for cached parquet
3. Downloads missing ones automatically
4. Runs `run_combined_backtest()` pipeline
5. Outputs `results/trades.csv`, `results/metrics.json`, `results/equity_curve.csv`

**Pipeline:**
```
MT5 terminal
    │ copy_rates_from_pos()
    ▼
data/raw/{symbol}_{tf}.parquet
    │ load_frame()
    ▼
Signal Pipeline (BOS, FVG, CHOCH, OB, displacement, zones, Trend, Filters)
    │ FeatureEngine (30+ features)
    ▼
Risk Governor (per-symbol state machine)
    ▼
Trade Simulation (SL/TP, MFE/MAE)
    ▼
results/trades.csv + metrics.json + equity_curve.csv
```

---

## 4. What's missing for paper trading?

| Missing Component | Priority | Description |
|------------------|----------|-------------|
| **Real-time candle watcher** | 🔴 Critical | Poll MT5 every 15 min for new M15 candle, trigger pipeline |
| **Order simulation** | 🔴 Critical | Convert signals to virtual orders, track fills/slippage |
| **Open position tracker** | 🔴 Critical | Track entries, SL/TP levels, floating P&L for open trades |
| **Position sizing** | 🟡 High | Compute lot size from risk_multiplier, account balance, SL distance |
| **Daily P&L reset** | 🟡 High | Reset governor day_drawdown at market open |
| **Telegram / console UI** | 🟢 Medium | Show open positions, P&L, next signal |
| **State persistence** | 🟢 Medium | Save open positions to disk for restart recovery |

---

## 5. What's missing for live trading?

Everything from paper trading, plus:

| Missing Component | Priority | Description |
|------------------|----------|-------------|
| **MT5 order execution** | 🔴 Critical | `mt5.order_send()` for market/limit/SL/TP orders |
| **Real position sync** | 🔴 Critical | `mt5.positions_get()` to reconcile with internal state |
| **Margin validation** | 🔴 Critical | Check free margin before opening |
| **Slippage model** | 🟡 High | Configure expected slippage in pips |
| **Commission model** | 🟡 High | Broker commission per lot |
| **Error recovery** | 🟡 High | Reconnect on disconnect, re-sync positions |
| **Kill switch** | 🟡 High | Emergency close-all if drawdown exceeds limit |
| **Logging system** | 🟡 High | Structured logs (structlog) to file + console |
| **Telegram alerts** | 🟢 Medium | Signal, fill, SL, daily summary |
| **VPS deployment** | 🟢 Medium | 24/7 on cloud VPS |

---

## Architecture Diagram

```
                     ┌─────────────────────────────┐
                     │      MT5 Terminal            │
                     └──────────────┬──────────────┘
                                    │ mt5.initialize()
                                    │ mt5.copy_rates_from_pos()
                                    ▼
              ┌─────────────────────────────────────┐
              │        MT5Connector                  │
              │  _data_legacy.py (load_frame)        │
              └────────────────┬────────────────────┘
                               │ save_parquet()
                               ▼
              ┌─────────────────────────────────────┐
              │      data/raw/*.parquet              │
              │  (cached OHLCV — M15, H1, H4, D1)   │
              └────────────────┬────────────────────┘
                               │ load_frame()
                               ▼
              ┌─────────────────────────────────────┐
              │       Signal Pipeline                │
              │  detectors → indicators → regime     │
              │  → filters → confluence → signal     │
              └────────────────┬────────────────────┘
                               │ FeatureEngine
                               ▼
              ┌─────────────────────────────────────┐
              │       Risk Governor (per-symbol)     │
              │  GovernorPool → mode → risk_mult     │
              └────────────────┬────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
          ┌─────────────────┐   ┌─────────────────┐
          │  Backtest (now)  │   │ Paper Trading    │
          │  simulate trade  │   │ (next)           │
          │  → trades.csv    │   │ → mt5.order_send │
          └─────────────────┘   └─────────────────┘
```

---

## File Structure

```
_data_legacy.py                 # MT5 data loading + connector
data/
├── raw/                        # parquet cache (auto-created)
mt5_bridge/                     # Bridge module
├── schema.py                   # Data contracts
├── exporter.py                 # Signal export (ZeroMQ/file)
├── receiver.py                 # Result reception
├── zeromq_transport.py         # ZMQ transport layer
├── orchestrator.py             # Bridge lifecycle
└── harness_adapter.py          # Harness integration
backtest/
├── engine.py                   # Backtest engine
├── real/                       # real-data backtest runner
└── validation/                 # MT5 backtest validation
    ├── mt5_backtest_runner.py
    ├── trade_comparator.py
    └── report_generator.py
results/                        # Backtest output
scripts/
├── download_candles.py         # CLI data downloader
├── live_market_read.py         # Live MT5 read test
├── first_live_test.py          # First order test
└── full_pipeline_demo.py       # Full pipeline demo
```

## Commands Reference

```bash
# Download single symbol/timeframe
python download_candles.py EURUSD M15 --count 100000

# Download all timeframes for a symbol
python download_candles.py EURUSD --all-timeframes

# Run harness scenarios
python -m harness

# Run real backtest with MT5 data
python -m backtest.real --symbols EURUSD GBPUSD

# Run LangGraph validation
python scripts/test_validation_graph.py --symbol EURUSD --timeframe M15

# Live market read (read-only)
python scripts/live_market_read.py

# Full pipeline demo (reads live data, generates signals)
python scripts/full_pipeline_demo.py
```
