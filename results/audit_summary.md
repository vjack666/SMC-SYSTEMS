# Audit Summary PAC/FVG

## Baseline Consistency
- baseline_consistent: False
- baseline_reference: {'metrics': 'results/fvg_mitigation_metrics.csv', 'trade_log': 'results/fvg_mitigation_trade_log.csv', 'comparison_summary': 'results/fvg_mitigation_comparison_summary.json'}

## Preguntas de negocio
1. Mitigacion aporta edge: delta_expectancy_B_vs_A=nan, delta_pf_B_vs_A=nan
2. Estructura aporta edge: delta_expectancy_C_vs_B=nan
3. Sesiones aportan edge: delta_expectancy_D_vs_C=nan
4. ML aporta edge real: delta_expectancy_E_vs_D=nan
5. Configuracion optima por expectancy: E
6. Variables explicativas principales: ver feature_importance.csv
7. Reglas candidatas a produccion: solo experimentos pass_success_criteria=true
8. Evidencia tabular: comparison_table.csv + symbol_breakdown.csv + expectancy_report.csv + drawdown_report.csv

## Validacion tecnica
- no_lookahead_ok: True
- no_lookahead_violations: 0
- walk_forward_folds: 5
- walk_forward_auc_mean: 0.09112934713570167

## Top Feature Importance (ML E)
- distance_eql: 0.163326
- distance_eqh: 0.159518
- distance_prev_day_high: 0.137496
- distance_prev_day_low: 0.132612
- mitigation_depth_pct: 0.076744
- hour_cos: 0.059353
- bars_since_fvg_creation: 0.057212
- bars_since_mitigation: 0.055580
- hour_sin: 0.055455
- mitigation_touch_count: 0.033369
