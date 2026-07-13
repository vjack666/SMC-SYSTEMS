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

## 8. Modelos aislados (R4 — 2026-07-13)

Medición AISLADA de cada modelo ICT, separado del mix intradia. Fuente:
`ict_backtest/run_backtest.py --model {intradia,scalping,po3}`, motor vela-a-vela.
Reporte por experimento (E1–E5 del roadmap R4).

| Exp | Qué | Comando | Estado |
|-----|-----|---------|--------|
| E1 | Baseline intradia mezcla | `--model intradia` | histórico (§3/§4) |
| E2 | **Solo PO3 `complete=True` a-favor** | `--model po3 --htf H4 --ltf M15` | 🔄 corriendo (EURUSD M15) |
| E3 | Solo Turtle Soup `counter_trend=True` | `--model intradia --counter-trend` | ⏳ pendiente E2 |
| E4 | Solo Silver Bullet (kz + sweep + FVG) | `--model scalping` | ⏳ pendiente |
| E5 | Con `--cost` en todos | `+ --cost` | ⏳ pendiente |

**Gate R4:** no Optuna hasta que E2 (o el modelo elegido) tenga **PF OOS medio ≥ 1.10**
**y** ningún fold < 1, **o** se documente "frágil aceptado para paper".

### 8.1 E2 / E3 / E5 — PO3 y Turtle aislados (EURUSD M15, H4 sesgo, 2024-07→2026-07)

Fuente: `results/r4/r4_chain_20260713T161349Z.json` (`scripts/r4_chain.py`, 4 workers).

| Exp | Modelo | Cost | PF | WR | Trades | Exp(R) | Total R | MaxDD R |
|-----|--------|------|----|----|--------|--------|---------|---------|
| E2 | PO3 completo a-favor | sin | **0.286** | 12.5% | 8 | -0.625 | -5.0 | -6.0 |
| E3 | Turtle Soup (CT) | sin | **0.689** | 26.4% | 466 | -0.228 | -106.4 | -112.8 |
| E5 | PO3 completo a-favor | con (0.8/0.5/0.3) | **0.194** | 12.5% | 8 | -0.745 | -6.0 | -6.3 |
| E5 | Turtle Soup (CT) | con (0.8/0.5/0.3) | **0.511** | 26.4% | 466 | -0.386 | -180.0 | -181.6 |

**Veredicto R4 (gate):** NINGUNO supera PF ≥ 1.10. PO3 aislado además tiene
**muestra minima (8 trades / 2 anos)** → no concluyente, pero claramente sin edge.
Turtle Soup aislado (466 trades) es concluyente: **PF 0.689 sin cost, 0.511 con
cost → pierde sistematicamente**. Con costos empeora (esperable: mas friccion).

**Decision:** NO Optuna sobre estos modelos aislados (no cumplen el gate). Se
documenta como **"modelos aislados sin edge en EURUSD M15 — no promovidos"**.
El PF 1.61 del §4 era del pipeline ML combinado, NO de PO3/Turtle puros.

**Siguiente paso sugerido:** probar E4 (Silver Bullet, `--model scalping`, otro
regimen de killzone) antes de descartar el stack ICT intradia en M15.

```markdown
Métricas: ver [METRICS_CANON §3](../METRICS_CANON.md#3-ict_backtest-post-auditoría-2026-07-11).
No duplicar PF aquí.
```

Si una corrida nueva contradice este archivo: **actualizar § correspondiente** y poner fecha.
