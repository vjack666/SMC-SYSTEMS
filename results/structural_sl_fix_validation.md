# Structural Stop Loss Fix Validation

## Fix Status

- **Invalid LONG stops**: 0 (target: 0)
- **Invalid SHORT stops**: 0 (target: 0)
- **Invalid exit logic violations**: 0 (target: 0)
- **stop_distance_atr NaN count**: 0 (target: 0)
- **Total trades**: 14344
- **Holding bars unique values**: [np.int64(1), np.int64(2), np.int64(3), np.int64(4), np.int64(5), np.int64(6), np.int64(7), np.int64(8), np.int64(9), np.int64(10), np.int64(11), np.int64(12), np.int64(13), np.int64(14), np.int64(15), np.int64(16), np.int64(17), np.int64(18), np.int64(19), np.int64(20), np.int64(21), np.int64(22), np.int64(23), np.int64(24), np.int64(25), np.int64(26), np.int64(27), np.int64(28), np.int64(29), np.int64(30), np.int64(31), np.int64(32), np.int64(33), np.int64(34), np.int64(35), np.int64(36), np.int64(37), np.int64(38), np.int64(39), np.int64(40), np.int64(41), np.int64(42), np.int64(43), np.int64(44), np.int64(45), np.int64(46), np.int64(47), np.int64(48), np.int64(49), np.int64(50), np.int64(51), np.int64(52), np.int64(53), np.int64(54), np.int64(55), np.int64(56), np.int64(57), np.int64(58), np.int64(59), np.int64(60), np.int64(61), np.int64(62), np.int64(63), np.int64(64), np.int64(65), np.int64(66), np.int64(67), np.int64(68), np.int64(69), np.int64(70), np.int64(71), np.int64(72), np.int64(73), np.int64(74), np.int64(75), np.int64(76), np.int64(77), np.int64(78), np.int64(79), np.int64(80), np.int64(81), np.int64(82), np.int64(83), np.int64(84), np.int64(85), np.int64(86), np.int64(87), np.int64(88), np.int64(89), np.int64(90), np.int64(91), np.int64(92), np.int64(93), np.int64(94), np.int64(95), np.int64(96), np.int64(97), np.int64(98), np.int64(99), np.int64(100)]

## Validation Criteria

**Overall Status**: ✅ PASSED

- ✅ LONG stops are all below entry_price
- ✅ SHORT stops are all above entry_price
- ✅ Exit logic is consistent (no sl_hit with pnl_r > 0, no tp_hit with pnl_r < 0)
- ✅ stop_distance_atr has valid values
- ✅ Holding bars varies: [np.int64(1), np.int64(2), np.int64(3), np.int64(4), np.int64(5), np.int64(6), np.int64(7), np.int64(8), np.int64(9), np.int64(10)]...

## Comparison: Broken vs Fixed

| Metric | Broken | Fixed | Improvement |
|--------|--------|-------|-------------|
| Invalid LONG stops | 78 | 0 | 78 ✅ |
| Invalid SHORT stops | 55 | 0 | 55 ✅ |
| Exit logic violations | 133 | 0 | 133 ✅ |
| stop_distance_atr NaN | 141 | 0 | 141 ✅ |
| Total trades | 141 | 14344 | - |

## Trade Statistics (Fixed)

- **total_trades**: 14344
- **wins**: 5712
- **losses**: 8632
- **win_rate**: 0.39821528165086445
- **expectancy_r**: 0.014241992727054988
- **std_dev_r**: 1.243036858107981
- **profit_factor**: 1.0258339650109183
- **avg_stop_distance_atr**: 4.023996604342689
- **avg_holding_bars**: 49.680354155047404