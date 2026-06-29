# MT5 Integration Report — SMC_SUCCESSOR

## Status: CONNECTED

| Component | Status | Notes |
|-----------|--------|-------|
| MT5 Terminal | ✅ Connected | ForexClub MT5 — Account 500236073 |
| Symbol Discovery | ✅ Available | `mt5.symbols_get()` returns all tradeable symbols |
| Historical Data | ✅ Downloading | M1 through D1 via `copy_rates_from_pos()` |
| Parquet Persistence | ✅ Working | `data/raw/{symbol}_{timeframe}.parquet` |
| Real Backtest | ✅ Working | 19 trades on EURUSD from real data |
| Test Suite | ✅ 99 passed | No regressions after data.py→data/ refactor |

---

## 1. Does MT5 connect correctly?

**Yes.** `MT5Connector` initializes the MT5 terminal via `mt5.initialize()` and validates the connection via `mt5.terminal_info()`. Three connection modes:

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

The connector retries up to 3 times with 2-second delays on transient failures.

**Known issues:**
- MT5 terminal must be running and logged in before connecting
- No automatic reconnection if terminal disconnects mid-session
- `connection refused` errors are raised as `ConnectionError` with MT5 error code

---

## 2. Are the candles real?

**Yes.** Candles are downloaded via `mt5.copy_rates_from_pos()`, which returns the MT5 server's native OHLCV data. Verified fields:

| Field | Source | Verified |
|-------|--------|----------|
| `time` | Unix seconds → UTC datetime | ✅ `pd.to_datetime(time, unit='s', utc=True)` |
| `open` | MT5 rate | ✅ |
| `high` | MT5 rate | ✅ |
| `low` | MT5 rate | ✅ |
| `close` | MT5 rate | ✅ |
| `tick_volume` | MT5 rate | ✅ |
| `spread` | MT5 rate | ✅ |

**Sample verification (EURUSD M15, 2026-06-29):**
```
time: 2026-06-29 04:45:00+00:00
open: 1.15327, high: 1.15329, low: 1.15310, close: 1.15317
tick_volume: 259, spread: 0
```

---

## 3. Does the backtest use downloaded data?

**Yes.** The `python -m smc_successor.backtest.real` command:

1. Connects to MT5
2. Checks `data/raw/` for cached parquet files
3. Downloads missing ones automatically
4. Runs the standard `run_combined_backtest()` pipeline
5. Outputs `results/trades.csv`, `results/metrics.json`, `results/equity_curve.csv`

**Backtest pipeline with real data:**

```
MT5 terminal
    │ copy_rates_from_pos()
    ▼
data/raw/{symbol}_{tf}.parquet
    │ load_frame()
    ▼
Signal Pipeline (BOS, FVG, CHOCH, OB, Trend, Filters)
    │
    ▼
FeatureEngine (34 features)
    │
    ▼
Risk Governor (per-symbol state)
    │
    ▼
Trade Simulation (SL/TP, MFE/MAE)
    │
    ▼
results/trades.csv + metrics.json + equity_curve.csv
```

---

## 4. What's missing for paper trading?

Paper trading needs everything we have now plus an **execution loop** that processes candles as they close:

| Missing Component | Priority | Description |
|------------------|----------|-------------|
| **Real-time candle watcher** | 🔴 Critical | Poll MT5 every 15 min for new M15 candle, trigger pipeline |
| **Order simulation** | 🔴 Critical | Convert signals to virtual orders, track fills/slippage |
| **Open position tracker** | 🔴 Critical | Track entries, SL/TP levels, floating P&L for open trades |
| **Position sizing** | 🟡 High | Compute lot size from risk_multiplier, account balance, SL distance |
| **Daily P&L reset** | 🟡 High | Reset governor day_drawdown at market open |
| **Telegram / console UI** | 🟢 Medium | Show open positions, P&L, next signal |
| **State persistence** | 🟢 Medium | Save open positions to disk so restart doesn't lose them |

**Simplest paper trading flow:**
```
Every 15 min (on new candle):
  1. Download latest M15, H4, D1 data
  2. Run signal pipeline
  3. If signal AND no position open → open virtual position
  4. Every tick/min → check SL/TP hit → close if triggered
  5. Log all trades to paper_trades.csv
```

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
| **Error recovery** | 🟡 High | Reconnect on terminal disconnect, re-sync positions |
| **Kill switch** | 🟡 High | Emergency close-all if drawdown exceeds limit |
| **Logging system** | 🟡 High | Structured logs (structlog) to file + console |
| **Telegram alerts** | 🟢 Medium | Signal generated, order filled, SL hit, daily summary |
| **VPS deployment** | 🟢 Medium | 24/7 operation on cloud VPS |

---

## Architecture Diagram (Current + Planned)

```
                     ┌─────────────────────────────┐
                     │      MT5 Terminal            │
                     │  (ForexClub — Account 5xxxx) │
                     └──────────────┬──────────────┘
                                    │ mt5.initialize()
                                    │ mt5.copy_rates_from_pos()
                                    ▼
              ┌─────────────────────────────────────┐
              │        MT5Connector                  │
              │  smc_successor/data/mt5/connector.py │
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

## File Inventory (Phase 3 additions)

```
smc_successor/
├── data/                          # was data.py, now package
│   ├── __init__.py                # re-exports load_frame, apply_time_window, MT5Connector
│   ├── mt5/
│   │   ├── __init__.py
│   │   └── connector.py           # MT5Connector class (180 lines)
│   └── raw/                       # parquet cache (auto-created)
├── backtest/
│   ├── real/
│   │   ├── __init__.py
│   │   └── __main__.py            # python -m smc_successor.backtest.real
│   └── engine.py                  # existing
├── _data_legacy.py                # original data.py (moved)
data/raw/                          # downloaded parquet files
results/                           # backtest output
download_candles.py                # CLI: python download_candles.py EURUSD M15 --count 100000
MT5_INTEGRATION_REPORT.md          # this file
```

## Commands Reference

```bash
# Download single symbol/timeframe
python download_candles.py EURUSD M15 --count 100000

# Download all timeframes for a symbol
python download_candles.py EURUSD --all-timeframes

# Run real backtest with MT5 data
python -m smc_successor.backtest.real --symbols EURUSD GBPUSD XAUUSD

# Run backtest with custom parameters
python -m smc_successor.backtest.real \
    --symbols EURUSD \
    --timeframe M15 \
    --count 50000 \
    --min-confidence 0.4 \
    --max-hold 12 \
    --no-ml
```
