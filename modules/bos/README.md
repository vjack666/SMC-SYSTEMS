# BOS Module (Break of Structure)

## What is implemented

- `modules/bos/data_loader.py`: loads MT5 parquet datasets by symbol/timeframe.
- `modules/bos/detector.py`: baseline rule-based BOS detector using swing structure + ATR.
- `modules/bos/ml_model.py`: ML quality scorer for BOS events (real vs fake break).
- `backtest/bos_backtest.py`: isolated BOS backtest with SL/TP at RR 1:2 and metrics export.

## Data source

- Input files from `data/mt5/*.parquet` generated with MT5 downloader.
- Symbols: EURUSD, GBPUSD, XAUUSD.
- Timeframe tested: M15.

## Backtest outputs

Generated in `results/`:

- `bos_trades.json`
- `bos_metrics.json`

## Latest measured metrics

Current default configuration (walk-forward):

- confidence threshold: `0.55`
- trend alignment filter: `enabled`
- session filter: `enabled` (symbol-adjusted UTC windows)
- liquidity sweep filter: `available, disabled by default`
- walk-forward split: train `40%`, test `30%`, step `15%`
- RR: `1:2`

Metrics:

- total trades: `240`
- win rate: `45.00%`
- profit factor: `1.58`
- max drawdown: `-16.00 R`
- expectancy: `0.32 R`

Best precision-oriented configuration found:

- confidence threshold: `0.60`
- walk-forward split: train `45%`, test `30%`, step `15%`

Metrics:

- total trades: `68`
- win rate: `58.82%`
- profit factor: `2.79`
- max drawdown: `-6.00 R`

Interpretation:

- There is a clear precision vs sample-size trade-off in current BOS logic.
- High precision is achievable, but not with minimum sample-size target.
- Sample-size target is achievable, but current win rate stays below 50%.

## Threshold status

Target thresholds from agent instructions:

- win rate: `> 50%`
- profit factor: `> 1.4`
- max drawdown: `<= 1.0` (interpretation pending unit definition)
- minimum trades: `>= 200`

Current status:

- Win rate threshold: met only in low-sample precision setup.
- Profit factor threshold: met.
- Minimum trades threshold: met in current default walk-forward setup.
- Drawdown threshold: not met if interpreted in raw `R` units.

## Next iteration focus (BOS still in progress)

1. Add volatility regime filter (ATR percentile) to skip low-quality ranges.
2. Add news-event exclusion windows around high-impact macro releases.
3. Add adaptive confidence threshold by session and symbol.
4. Add calibration step (probability reliability curve) before thresholding.
5. Re-run until all thresholds pass simultaneously.