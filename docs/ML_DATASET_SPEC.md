# ML Dataset Specification v4

## Schema Version

Current: `v4` (multi-symbol with combined output, year_month partition, timestamp, agent_decision_ml_probability dropped)

## File Layout

```
data/ml/
  {symbol}/
    v4_{symbol}.parquet          # Per-symbol dataset
  multi_symbol/
    v4_dataset.parquet           # Combined dataset (all symbols)
```

## Columns (75 total)

### Metadata (3)
- `schema_version` — always "v4"
- `symbol` — e.g. "EURUSD"
- `timestamp` — signal entry time (ISO string, UTC)

### Technical Features (31)
`bos_detected`, `bos_strength`, `choch_detected`, `choch_strength`,
`fvg_detected`, `fvg_size`, `fvg_fill_status`, `fvg_direction`,
`ob_detected`, `ob_distance`, `liquidity_sweep`,
`displacement_magnitude`, `displacement_bullish`, `displacement_bearish`,
`premium_discount_zone`, `premium_distance`, `ote_long_min`, `ote_short_min`,
`d1_bias`, `h4_bias`, `trend_alignment`, `trend_confidence`,
`ema_fast`, `ema_slow`, `ema_distance`, `ema_slope`,
`atr`, `atr_ratio`, `candle_range_vs_atr`, `volatility_regime`,
`rsi`, `rsi_slope`, `volume_ratio`, `momentum_strength`,
`spread`, `market_regime`, `directional_efficiency`, `range_compression`,
`direction`, `session`, `weekday`

### Agent Columns (22)
`agent_ict_bias`, `agent_ict_confidence`, `agent_ict_events`,
`agent_wyckoff_bias`, `agent_wyckoff_confidence`, `agent_wyckoff_phase`,
`agent_wyckoff_events`, `agent_wyckoff_spring`, `agent_wyckoff_upthrust`,
`agent_wyckoff_sos`, `agent_wyckoff_sow`, `agent_wyckoff_effort_divergence`,
`agent_structure_bias`, `agent_structure_confidence`, `agent_structure_events`,
`agent_decision_bias`, `agent_decision_confidence`, `agent_decision_reasons`,
`agent_decision_conflicts`, `agent_decision_conflict_penalty`,
`agent_decision_weighted_bias_sum`, `agent_decision_total_weight`

Note: `agent_decision_ml_probability` was dropped in v4 (always NaN at dataset build time).

### Trade Context (5)
`sl_distance`, `tp_distance`, `rr_ratio`, `expected_hold_bars`, `exit_reason`

### Labels (6)
`pnl_r`, `win`, `max_favorable_excursion`, `max_adverse_excursion`,
`holding_time`, `exit_reason`

### Partition Column (1)
`year_month` — e.g. "202405", derived from `timestamp`

## Training Columns

For ML training, the following columns are dropped:
- Metadata: `schema_version`, `symbol`, `timestamp`, `year_month`
- Agent: `agent_decision_ml_probability`
- Trade context at build time: `ml_probability`, `ml_threshold`
- Labels/targets: `win`, `pnl_r`, `max_favorable_excursion`, `max_adverse_excursion`, `holding_time`, `exit_reason`

Target column: `win` (binary: 1 = profitable trade, 0 = loss)

Feature list: `FEATURES_ML_V3` (55 features) — all technical features + agent columns + trade context features.

## Validation Criteria

1. No future leakage — columns like `future_return` must be absent
2. All critical features present (47 from CRITICAL_FEATURES)
3. All agent columns present (except `agent_decision_ml_probability`)
4. All label columns present
5. Schema version matches "v4"
6. Deterministic — re-reading the file produces identical data
7. Zero NaN values across all columns
8. Each symbol has >= 1 sample
