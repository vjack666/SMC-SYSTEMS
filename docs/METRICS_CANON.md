# Métricas canónicas — SMC-SYSTEMS

**Única fuente de números de performance para la documentación.**  
Los libros ICT/Wyckoff **no inventan** PF/WR: enlazan aquí o a reportes crudos.

**Actualizado:** 2026-07-12  
**Regla:** si un número cambia en código/corrida, se actualiza **solo este archivo** (+ el reporte crudo). Los libros citan la sección, no copian cifras sueltas.

---

## 1. Gates de calidad (roadmap)

| Gate | Criterio | Estado |
|------|----------|--------|
| Edge diagnosis OOS | PF ≥ 1.10 en >1 símbolo | ✅ (XAUUSD 1.376, USDCAD 1.264, …) |
| Walk-forward celda top (A12) | PurgedKFold, DSR>0, N≥200/fold, PF≥1.10 | 🔴 Falló 1er pase (pocos datos) |
| Costos en métricas | spread + commission + slippage explícitos | ⚠️ Cableado (`--cost`), no siempre aplicado |
| Harness | 100% escenarios | ✅ Objetivo de merge |

Ver: `docs/plan/CRONOGRAMA_Y_ROADMAP.md`.

---

## 2. Edge diagnosis (SMC puro, 2026-07-10)

Fuente: `docs/avances/EDGE_DIAGNOSIS_REPORT.md`, `results/edge_diagnosis/`.

| Concepto | Valor |
|----------|------:|
| Matriz | 21 variantes × 8 símbolos = 168 celdas |
| Errores / insufficient | 0 / 0 |
| Mejor variante (avg OOS PF) | `no_session` → **1.159** |
| Peor variante (avg OOS PF) | `prox_1` → **1.084** |
| Mejor símbolo (avg OOS PF) | **XAUUSD 1.376** |
| Peores símbolos | AUDUSD 0.849 · NZDUSD 0.809 |
| **Celda TOP** | `no_session` × XAUUSD → OOS PF **1.642**, N=900, Sharpe 3.28, WR 55.1% |

---

## 3. ict_backtest (post-auditoría 2026-07-11)

Fuente: `docs/ict/logs/CAPA2_REFAC_CORRIDACORREGIDA.log`, `CAPA3_REFAC_WF.log`, `docs/avances/AVANCES_ICT_BACKTEST_2026-07-11.md`.

| Corrida | Valor | Notas |
|---------|------:|-------|
| Capa 2 PF (antes fix #1/#2) | ~2.003 | Inflado por look-ahead / CHOCH copia |
| Capa 2 PF (después fix) | **1.548** | Edge honesto, aún >1 |
| Capa 3 WF OOS PF medio | **3.389 ± 2.303** | 3 folds OOS, **21 trades** |
| Capa 3 WR OOS medio | 58.3% | |
| Veredicto Capa 3 | **Edge frágil** | PF medio >1 pero **algún fold <1** |
| Costos en Capa 3 final | **NO** | Aplicar `--cost` en re-runs |

Mejores params Capa 3 (in-sample Optuna, 12 trials):  
`displace_gap=6`, `bos_gap=5`, `require_displacement=True`, `tp_mode=liquidity`.

---

## 4. Backtest combinado multi-símbolo + ML (histórico)

Fuente: `docs/auditorias/COMPLETION_REPORT.md` / README.

| Métrica | Valor |
|---------|------:|
| WR | 63.7% |
| PF | 1.61 |
| Sharpe | 3.33 |
| Max DD | 4.96% |

Tratar como **referencia de pipeline ML**, no como gate del stack ICT puro.

---

## 5. Gate CHOCH→BOS confirm (2026-07-12)

Fuente: `scripts/compare_choch_bos_confirm.py` (EURUSD M15, motor naive).

| | GATE off | GATE on |
|--|---------:|--------:|
| Señales | 1594 | 1153 |
| PF | -0.466 | -0.497 |
| WR | 34.8% | 33.5% |

**Veredicto:** en EURUSD M15 naive **no aporta edge**. Default: `mandatory_choch_bos_confirm=False`.

---

## 6. Ítem D — Sweep / OTE prevalencia (EURUSD M15)

Fuente: `docs/ict/10_SWEEP_OTE_FILTRO.md`.

| Feature | Prevalencia aprox. | Nota |
|---------|-------------------:|------|
| Sweep activo | ~66% | Útil como filtro |
| OTE en banda 62–79% | ~1% | Casi no-op en M15 actual |

---

## 7. Cómo citar desde un libro

```markdown
Métricas: ver [METRICS_CANON §3](../METRICS_CANON.md#3-ict_backtest-post-auditoría-2026-07-11).
No duplicar PF aquí.
```

Si una corrida nueva contradice este archivo: **actualizar § correspondiente** y poner fecha.
