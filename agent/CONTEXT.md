# CONTEXT.md — Persistent Technical Knowledge

> Information future sessions must remember.

---

## Trading Concepts

- **Scalping system**: M15 timeframe, 7 forex pairs, max 16-bar hold
- **Minimum confluence**: Configurable (default 0.52). Signal confidence must exceed this.
- **Structural SL**: Stop loss at the origin swing (ICT concept), TP at 2:1 (to be reviewed)
- **PAC**: Price Action Confirmation — 4-state sequence (FVG→Mitigation→Exhaustion→BOS→Entry)

## SMC (Smart Money Concepts)

- **BOS**: Break of Structure — price breaking beyond key swing point, confirming trend
- **CHOCH**: Change of Character — price breaking against prevailing trend
- **FVG**: Fair Value Gap — 3-candle imbalance, price expected to return and fill
- **OB**: Order Block — last candle before displacement, institutional orders
- **Liquidity sweep**: Price spikes beyond swing point then reverses (stop hunt)
- **Displacement**: Strong directional move, large body, small wick, 2x+ average range
- **Premium/Discount zones**: Below 50% = discount (buy), above 50% = premium (sell)

## Wyckoff Rules

- **Cycle**: Accumulation → Markup → Distribution → Markdown
- **Accumulation phases A-E**: SC (selling climax), AR (automatic rally), ST (secondary test), Spring, SOS (sign of strength), LPS (last point of support)
- **Volume confirmation**: High volume on breakouts, low volume on pullbacks
- **Spring**: Brief break below support, immediate reversal — final shakeout before markup
- **Upthrust**: Brief break above resistance, immediate reversal — final lure before markdown

## ML Assumptions

- **Feature schema**: Defined in `features_schema.json` and `ML_DATASET_SPEC.md`
- **Target**: Binary classification (win/loss based on PnL > 0)
- **Models**: XGBoost (primary), LightGBM (alternative), scikit-learn ensemble (fallback)
- **Training**: Walk-forward validation, GridSearchCV (3-fold) for dataset ≥ 200 rows
- **v4 schema**: Dropped `agent_decision_ml_probability` (always NaN), added `year_month`
- **Quality filter**: Applied as post-scoring gate, not integrated into agent confidence

## Detection Logic

- **Swing detection**: Zigzag method, local high/low confirmed when price reverses by N ATR units
- **FVG**: Gap between wick of C1 and wick of C3 where price didn't trade
- **BOS**: Must close beyond prior swing point (wick not sufficient)
- **CHOCH**: Break of key swing against trend, requires follow-through bar
- **OB detection**: Last opposing candle before displacement move within 5-10 bars

## Constraints

- Agents read context, never modify it
- Agents never execute trades or set risk parameters
- All modules must pass Harness scenarios before integration
- Backtest uses GovernorPool for per-symbol risk management
- Python 3.11, path to .venv: `.venv\Scripts\python.exe`

## Coding Conventions

- `from __future__ import annotations` at top of every Python file
- Type hints required for all function signatures
- Dataclasses for configuration objects
- Pathlib for filesystem operations
- Pandas DataFrame for all tabular data
- F-string formatting preferred
- YAML for fixture/scenario definitions
- Parquet (Zstd compression) for data storage
- Docstrings follow Google style
- Test files under `tests/` mirror source structure
