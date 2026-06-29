# Informe Forense – Experimento E
Fecha: 2026-05-30  |  Trades E: 1776  |  Total R: 471.52  |  PF: 2.28

---

## 1. Qué tienen en común los mejores trades (top 100)

- Sesión dominante: **london**
- Dirección dominante: **SHORT**
- Estructura dominante: **bos**
- Hora más frecuente (UTC): **9h**
- Símbolo dominante: **EURUSD**
- Media ML probability: **0.6218**
- Media mitigation_depth_pct: **0.2743**
- Fuente: results/top_100_winners.csv

---

## 2. Qué tienen en común los peores trades (top 100 losers)

- Sesión dominante: **london**
- Dirección dominante: **SHORT**
- Estructura dominante: **bos**
- Hora más frecuente (UTC): **21h**
- Símbolo dominante: **EURUSD**
- Media ML probability: **0.6423**
- Media mitigation_depth_pct: **0.1237**
- Fuente: results/top_100_losers.csv

---

## 3. Variables con mayor frecuencia en ganancias

- **session_bucket**: ganadores → `new_york` (40.8%)
- **side**: ganadores → `SHORT` (52.3%)
- **structure_event**: ganadores → `bos` (100.0%)
- **ob_state**: ganadores → `none` (100.0%)
- **structure_scale**: ganadores → `internal` (100.0%)

---

## 4. Variables con mayor frecuencia en pérdidas

- **session_bucket**: perdedores → `new_york` (37.1%)
- **side**: perdedores → `LONG` (53.2%)
- **structure_event**: perdedores → `bos` (100.0%)
- **ob_state**: perdedores → `none` (100.0%)
- **structure_scale**: perdedores → `internal` (100.0%)

---

## 5. Zonas de ML Score con mayor retorno

- Mejor quintil ML: **(0.616, 0.681]** → mean expectancy = **0.3182R**
- Fuente: results/experiment_E.csv / results/charts/ml_score_vs_expectancy.png

---

## 6. Tamaño de FVG que funciona mejor

- Mejor quintil FVG size (ATR): **(2.12, 3.179]** → mean expectancy = **0.8948R**
- Fuente: results/forensic_trades_dataset.csv / results/charts/fvg_size_vs_expectancy.png

---

## 7. Profundidad de mitigación óptima

- Mejor quintil mitigation_depth_pct: **(-0.4, 0.2]** → mean expectancy = **0.3743R**
- Fuente: results/forensic_trades_dataset.csv / results/charts/mitigation_depth_vs_expectancy.png

---

## 8. Sesión con mejor rendimiento

- **overlap**: expectancy=0.3196R  n=594
- **london**: expectancy=0.2895R  n=495
- **new_york**: expectancy=0.2014R  n=687

→ Sesión óptima: **overlap** (0.3196R/trade)
- Fuente: results/charts/expectancy_by_session.png

---

## 9. Horas con mejor rendimiento

- **7:00 UTC**: mean=0.7636R  n=63
- **14:00 UTC**: mean=0.4443R  n=96
- **16:00 UTC**: mean=0.3695R  n=264
- **15:00 UTC**: mean=0.3273R  n=120
- **17:00 UTC**: mean=0.3265R  n=261

→ Mejor hora individual: **7:00 UTC** (0.7636R/trade)
- Fuente: results/charts/winrate_by_hour.png

---

## 10. Combinación exacta con mayor expectancy observado

- Combinación: **session=london | side=SHORT | structure=bos**
- Expectancy: **0.4739R/trade**  n=279
- Fuente: results/forensic_trades_dataset.csv

---

## Archivos generados
- `results/forensic_trades_dataset.csv`
- `results/forensic_event_timeline.csv`
- `results/replay_dataset.csv`
- `results/top_100_winners.csv`
- `results/top_100_losers.csv`
- `results/charts/` — 18 gráficas + 7 scatter plots
