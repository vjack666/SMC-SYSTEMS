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
- **Distribution phases A-E**: UT (upthrust), SOW (sign of weakness), LPSY (last point of supply) — mirror of accumulation events
- **Volume confirmation**: High volume on breakouts, low volume on pullbacks
- **Spring**: Brief break below support, immediate reversal — final shakeout before markup
- **Upthrust**: Brief break above resistance, immediate reversal — final lure before markdown
- **Phase-aware filter**: AccumulationE/MARKUP + bullish macro_direction = OK; DistributionE/MARKDOWN + bearish = OK; conflict reduces trend_confidence by 30%
- **Detector output**: 14 columns — 3 classic (SC/AR/ST), 3 accumulation (Spring/SOS/LPS), 3 distribution (UT/SOW/LPSY), 4 meta (phase, accum, distrib, markup/markdown)
- **Dist tracking**: `last_dist_high_idx`/`last_dist_low_idx` tracked unconditionally (not gated by accumulation events)

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

## Session 2 Findings (2026-06-30)

- **wyckoff_distribution = 0 on all tested data**: `_upthrust()`, `_sign_of_weakness()`, `_last_point_supply()` never fire on 10k-bar samples of EURUSD/GBPUSD/XAUUSD. Distribution phase detection is effectively dead code despite the phase priority fix. Root cause unknown — may be: (a) resistance distance threshold too tight, (b) volume threshold too high, (c) swing window too small for the trend context.
- **Bearish PAC exhaustion has no Wyckoff signal**: Since `wyckoff_distribution` never fires, bearish PAC entries rely solely on stochastic exhaustion. Meanwhile bullish entries benefit from `wyckoff_accumulation` (fires on ~63-81% of bars). This creates an asymmetry favoring LONG entries.
- **Signal confidence too uniform**: 11 backtest signals cluster at 2 values (0.6886, 0.7866). Scorer needs more input variance.
- **Backtest trade sim time matching**: GBPUSD/XAUUSD produce debug signals but 0 backtest trades. Suspect string precision mismatch in `_simulate_trade_with_stats`.
- **TP=3R needed for PF > 1.0**: At TP=2R the system had PF=0.48. Changing to TP=3R gave PF=1.258 at 27.3% WR. The breakeven WR for PF>1 is ~25% at 3:1 RR, so the system barely clears it.
- **Single-trend dependency**: All 3 winning trades are EURUSD SHORT in March 2026. The system needs multi-symbol diversification to be robust.
- **PAC fallback**: When both exhaustion sources fail, `_build_exhaustion_series` returns False for all bars. Currently uses `use_stochastic or use_wyckoff` gate; when both are False, falls back to all-True. But when both are True and neither fires (e.g., bearish with no distribution), PAC state machines get no exhaustion signal.

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
