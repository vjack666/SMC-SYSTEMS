# Trend Module (Multi-Timeframe)

## Status
- Implemented and executable.
- Pylance-clean across module files.
- Backtest executed with iterative tuning.
- **Not yet passing all target thresholds simultaneously.**

## Files
- `swing_detector.py`: Pivot-based swing high/low detection with left/right window and min-distance filtering.
- `structure_classifier.py`: HH/HL/LH/LL classification into `BULLISH | BEARISH | RANGING`.
- `mtf_analyzer.py`: D1/H4 macro alignment + M15 micro state (`CONTINUATION | PULLBACK | UNCLEAR`).
- `ml_model.py`: RandomForest confidence model with feature engineering, walk-forward training, save/load, and confidence prediction.
- `backtest.py`: Isolated trend-signal backtest and metrics generation.
- `__init__.py`: Public interface `get_trend_signal(...)`.

## Signal Logic
- Macro trend is derived from higher-timeframe agreement (D1 and H4).
- Micro state is derived from M15 context relative to macro trend.
- Valid signal requires:
  - macro in `BULLISH` or `BEARISH`
  - micro state `CONTINUATION`
  - ML confidence > threshold (default 0.65)

## ML Features
- ATR ratio: current ATR / ATR(20) mean
- Swing amplitude in ATR units
- Candle body ratio (10-bar mean)
- Distance from last swing in ATR units
- Volume trend slope over last 10 bars
- D1/H4 agreement flag
- Encoded micro state
- Consecutive structure count

## Backtest Setup
- Data source: `data/mt5/*.parquet`
- Symbols tested: EURUSD, GBPUSD, XAUUSD
- Entry condition: valid trend signal + micro continuation
- Exit model: ATR-based SL, TP at 2R, max hold bars = 20

## Iteration Results (current)

### Iteration 1 (confidence = 0.65)
- EURUSD:
  - trades: 1475
  - win rate: 0.3159
  - profit factor: 0.8715
  - max drawdown pct: 256.91
  - max daily drawdown pct: 44.06
  - sharpe: -1.0181
  - expectancy R: -0.0863
- GBPUSD:
  - trades: 7347
  - win rate: 0.3529
  - profit factor: 1.0222
  - max drawdown pct: 285.15
  - max daily drawdown pct: 40.00
  - sharpe: 0.1626
  - expectancy R: 0.0141
- XAUUSD:
  - trades: 11918
  - win rate: 0.3742
  - profit factor: 1.1111
  - max drawdown pct: 268.58
  - max daily drawdown pct: 35.00
  - sharpe: 0.7791
  - expectancy R: 0.0682

### Iteration 2 (confidence = 0.75)
- EURUSD:
  - trades: 304
  - win rate: 0.3586
  - profit factor: 1.1185
  - max drawdown pct: 38.00
  - max daily drawdown pct: 38.00
  - sharpe: 0.8363
  - expectancy R: 0.0754
- GBPUSD:
  - trades: 1929
  - win rate: 0.3375
  - profit factor: 0.9729
  - max drawdown pct: 145.84
  - max daily drawdown pct: 19.35
  - sharpe: -0.2039
  - expectancy R: -0.0177
- XAUUSD:
  - trades: 1743
  - win rate: 0.4068
  - profit factor: 1.2900
  - max drawdown pct: 63.09
  - max daily drawdown pct: 22.72
  - sharpe: 1.8846
  - expectancy R: 0.1683

### Iteration 3 (confidence = 0.80)
- EURUSD:
  - trades: 158
  - win rate: 0.3924
  - profit factor: 1.2917
  - max drawdown pct: 26.00
  - max daily drawdown pct: 26.00
  - sharpe: 1.9205
  - expectancy R: 0.1772
- GBPUSD:
  - trades: 357
  - win rate: 0.3249
  - profit factor: 0.9353
  - max drawdown pct: 34.55
  - max daily drawdown pct: 6.00
  - sharpe: -0.4985
  - expectancy R: -0.0433
- XAUUSD:
  - trades: 452
  - win rate: 0.4071
  - profit factor: 1.2450
  - max drawdown pct: 31.62
  - max daily drawdown pct: 17.00
  - sharpe: 1.6195
  - expectancy R: 0.1444

## Threshold Check Against Target
Target set:
- win rate > 50%
- profit factor > 1.4
- max drawdown < 8%
- max daily drawdown < 4%
- sharpe > 1.0
- expectancy > 0
- total trades >= 200

Current result:
- **Failed** on win rate, profit factor, and drawdown constraints.
- Some runs pass Sharpe/expectancy, but not simultaneously with drawdown and win-rate constraints.

## Model Artifact
- Saved at: `modules/trend/models/trend_classifier.pkl`

## Retrain
From workspace root:
- `python -m backtest.trend_backtest`

This retrains the model and refreshes:
- `results/trend_metrics.json`
- `results/trend_trades.json`
