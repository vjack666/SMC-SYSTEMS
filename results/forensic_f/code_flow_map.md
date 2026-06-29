# Code Flow Map for Experiment F Structural Stop Audit

1. Signal generation
   - scripts/rebuild_experiment_f_structural.py:ExperimentFBuilder.generate_signals()
   - scripts/rebuild_experiment_f_structural.py:ExperimentFBuilder._load_symbol_data() uses modules.bos.detector.detect_bos()
   - scripts/rebuild_experiment_f_structural.py:ExperimentFBuilder._find_entry_signals() uses modules.bos.detector.detect_bos() and modules.fvg.detector.detect_fvg()
   - entry signals are created when BO S direction matches FVG direction and the price intersects the zone within entry_retest_lookahead

2. Structural stop generation
   - scripts/rebuild_experiment_f_structural.py:ExperimentFBuilder.simulate_trades() calls modules.structural_sl.detector.calculate_structural_stop()
   - modules/structural_sl/detector.py:calculate_structural_stop() detects origin swing and liquidity sweep and sets structural_stop_price=origin_price

3. Stop transformation to sl_price
   - scripts/rebuild_experiment_f_structural.py:simulate_trades(), line where sl_price = float(stop.structural_stop_price)

4. Risk calculation
   - scripts/rebuild_experiment_f_structural.py:simulate_trades() computes risk = abs(entry_price - sl_price)

5. R multiple / TP calculation
   - scripts/rebuild_experiment_f_structural.py:simulate_trades() computes tp_price = entry_price + (risk * self.rr_ratio * direction)

6. Trade simulation and exit decision
   - scripts/rebuild_experiment_f_structural.py:simulate_trades() loops over future bars
   - LONG: sl_hit if low <= sl_price, tp_hit if high >= tp_price
   - SHORT: sl_hit if high >= sl_price, tp_hit if low <= tp_price
   - If no hit, final exit_price closes at the current bar close and holding_bars updates per step

7. Metrics generation
   - scripts/rebuild_experiment_f_structural.py:save_metrics() computes total_trades, wins, losses, win_rate, expectancy_r, std_dev_r, profit_factor, avg_stop_distance_atr, avg_holding_bars