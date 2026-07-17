# 07 — Fuentes (respaldo verificable)

| Campo | Valor |
|-------|-------|
| **ID** | `13/07_FUENTES` |
| **Versión** | 1.0 |
| **Fecha** | 2026-07-13 |

> Las fuentes **no** sustituyen el código del repo. Sirven para justificar el checklist profesional.

---

## Web / guías (2025–2026)

| Tema | Fuente | Uso en el libro |
|------|--------|-----------------|
| Event-driven vs vectorizado; look-ahead | [Brenndoerfer — Backtesting & Simulation frameworks](https://mbrenndoerfer.com/writing/backtesting-trading-strategies-simulation-frameworks) | §01, §02 |
| Next-bar open execution | [NautilusTrader issue #4063 — next-bar-open](https://github.com/nautechsystems/nautilus_trader/issues/4063) | §03 |
| Timestamp / look-ahead en datos | [NautilusTrader docs — Backtesting concepts](https://nautilustrader.io/docs/latest/concepts/backtesting/) | §02 |
| Bar replay (decisión sin ver el futuro) | [Bar Replay Backtesting Guide](https://www.tradingsfx.com/blog/bar-replay-backtesting-guide) | §01 |
| Pitfalls: look-ahead, costos, fills | [Medium — Stop faking your results](https://medium.com/algorithmic-and-quantitative-trading/stop-faking-your-results-the-most-common-backtesting-pitfalls-to-avoid-f8dd94d1ca8e) | §03 |
| Look-ahead en evaluación de PnL | [Quant.SE — lookahead bias](https://quant.stackexchange.com/questions/32002/trouble-understanding-lookahead-bias) | §03 |
| Sesgos y validación | [ForTraders — How to avoid bias](https://www.fortraders.com/blog/how-to-avoid-bias-in-backtesting) | §04 |
| Intro backtesting algorítmico | [Robot Wealth — Backtesting explained](https://robotwealth.com/back-basics-part-3-backtesting-algorithmic-trading/) | §01 |

---

## Literatura / conceptos (nombres canónicos)

| Concepto | Referencia típica |
|----------|-------------------|
| PBO, CPCV, DSR | López de Prado — *Advances in Financial Machine Learning* (Wiley) |
| Purge / embargo | López de Prado — same; time-series CV |
| Walk-forward analysis | Industria quant / CTA (múltiples exposiciones) |

En el repo: implementación en `ml/stats_validator.py` (PurgedKFold, CVaR, DSR, PBO).

---

## Fuentes internas (verdad del proyecto)

| Doc | Rol |
|-----|-----|
| `docs/ict/10_AUDITORIA_REFACCION/` | Hallazgos #1–#7 medidos |
| `docs/avances/AVANCES_ICT_BACKTEST_2026-07-11.md` | PF pre/post fix |
| `docs/METRICS_CANON.md` | Únicos números oficiales |
| `docs/plan/ADR-021_*.md` | Filosofía de libros |
| `docs/plan/ROADMAP_BIBLIOTECA_Y_APLICACION.md` | R0–R5; R6 en plan hermano |

---

## Política de citas en libros futuros

1. Primero el **código** y la **corrida** del repo.  
2. Luego auditoría interna.  
3. Luego fuente externa (URL + fecha de consulta en el commit si es crítica).  
4. Nunca copiar PF de un blog a METRICS_CANON.
