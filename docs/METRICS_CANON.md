# Métricas canónicas — SMC-SYSTEMS

**Única fuente de números de performance para la documentación.**  
Los libros ICT/Wyckoff **no inventan** PF/WR: enlazan aquí o a reportes crudos.

**Actualizado:** 2026-07-24  (corrección estado R5/datos; números de corridas históricas intactos)  
**Regla:** si un número cambia en código/corrida, se actualiza **solo este archivo** (+ el reporte crudo). Los libros citan la sección, no copian cifras sueltas.

> **ENMIENDA DATOS R5 (2026-07-24):** `XAUUSD_M15` **ya existe** (~4.5 años, 2022-01→2026-07).  
> Inventario vivo: `docs/DATA_STATUS.md`. Las frases de §0 que dicen "XAUUSD M15 ausente / EXCLUIDO por falta M15"  
> describen la **corrida del 2026-07-17**, no el disco de hoy. **No reabrir R5 por data.**  
> Bloqueo real de edge = **re-run A12** (+ calidad de motor), no "bajar el parquet del oro".

> **Pendiente R6 (reloj profesional):** tras cerrar HTF closed-only + next-open + costs default (`docs/plan/PLAN_BACKTEST_PROFESIONAL.md`), re-medir Capa 2/3 y **reemplazar** las cifras de §3 si cambian. Hasta entonces, §3 sigue siendo post-auditoría swing/CHOCH (2026-07-11), **sin** fix multi-TF incompleto.

---

## 0. R6.4 M2 — Ablation de reloj (2026-07-16) · RESULTADO HONESTO

**Motor:** EVENT-SEQUENCE canónico (generate_sequence_signals: SL estructural + RR 1:3 + killzone + HTF closed-only).
**Datos:** EURUSD M15, HTF H4, últimas 8000 velas (~3 meses). Params por defecto.
**Script:** `scripts/r6_ablation.py` (motor real recortado).

| Modo | Fill | Costos | PF | WR | Trades |
|------|------|--------|---:|---:|-------:|
| G1 (teoría) | signal_close | OFF | **-2.49** | 38.9% | 18 |
| G1+G2 | next_open | OFF | **-2.52** | 38.9% | 18 |
| G1+G2+G3 (prod) | next_open | ON | **-4.89** | 38.9% | 18 |

**Veredicto EURUSD M15:** 🔴 **GATE R6 NO PASA** (PF<1.10 incluso en teoría).
- El reloj (G1) y el fill (G2) apenas cambian el PF (el motor ya genera señales donde open≈close).
- Los costos (G3) hunden ~2R adicionales (de -2.5 a -4.9), como dicta la física.
- N=18 es muestra pequeña (la ventana de esa ablation era ~8000 velas; A12 multi-año ya puede usar M15 largo en disco).

### R6.4 M2 — Multi-símbolo (2026-07-16, extensión) · RESULTADO HONESTO

Mismo motor canónico (generate_sequence_signals, SL estructural + RR 1:3 + killzone
+ HTF closed-only), 8000 velas (~3 meses), HTF H4. Script `scripts/r6_ablation.py`.

| Símbolo | G1 teoría | G1+G2 | PROD (costos ON) | WR prod | N | Gate prod (PF≥1.10) |
|---------|----------:|------:|-----------------:|--------:|--:|:-------------------:|
| EURUSD  | -2.49     | -2.52 | **-4.89**        | 38.9%   | 18 | 🔴 |
| GBPUSD  | -3.21     | -3.20 | **-7.07**        | 40.0%   | 30 | 🔴 |
| USDCHF  | +9.95     | +9.99 | **-0.13**        | 48.0%   | 25 | 🔴 |
| USDCAD  | +5.11     | +5.09 | **-8.64**        | 36.8%   | 38 | 🔴 |

### R6 — v2 mtf (motor multi-TF D1→H4→H1→M15) · 2026-07-17 · RESULTADO HONESTO

**Motor:** `ict_backtest/v2/run_v2.py --mode mtf` (cascada D1→H4→H1→M15, filtro top-down
premium/discount + sesgo HTF). **Costos ON**, OOS 0.3.
**Datos:** 7 majors (EURUSD, GBPUSD, USDJPY, AUDUSD, NZDUSD, USDCAD, USDCHF). Ventana
disponible ~6 meses (2026-01-18→2026-07-16, H1/M15 bajados de MT5 demo esa sesión).
**XAUUSD EXCLUIDO en ESA corrida** (en 2026-07-17 el runner/local no tenía M15 usable;
hoy el parquet existe — ver enmienda arriba / `docs/DATA_STATUS.md`).  
Reporte snapshot: `docs/avances/BACKTEST_V2_MTF_REPORTE_2026-07-17.md`.

| Símbolo | orders | trades | WR    | PF      | R     | OOS_PF   | coverage |
|---------|-------:|-------:|------:|--------:|------:|---------:|----------|
| EURUSD  | 0      | 0      | 0.0%  | 0.000   | 0.0   | —        | 86.1% v2_partial |
| GBPUSD  | 1      | 1      | 0.0%  | 0.000   | -1.0  | 0.000    | 86.1% v2_partial |
| USDJPY  | 1      | 1      |100.0% | inf*     | +1.0  | inf*     | 86.1% v2_partial |
| AUDUSD  | 4      | 4      | 0.0%  | 0.000   | -4.4  | 0.000    | 86.1% v2_partial |
| NZDUSD  | 2      | 2      | 0.0%  | 0.000   | -2.2  | 0.000    | 86.1% v2_partial |
| USDCAD  | 4      | 4      |25.0%  | 0.510   | -1.5  | 0.000    | 86.1% v2_partial |
| USDCHF  | 3      | 3      |33.3%  | 0.295   | -1.5  | inf*     | 86.1% v2_partial |

`* inf` = ganó el único trade sin pérdida → PF indefinido (N=1), NO edge real.

**Veredicto v2 mtf:** 🔴 **GATE NO PASA** (ningún símbolo PF OOS ≥ 1.10; sample 0-4 trades).
El filtro multi-TF deja pasar tan pocos setups que el PF negativo de R6.4 desaparece por
falta de operaciones, no por edge. Coverage `v2_partial` = 86.1% (C06 POI anclado MISSING).
Conclusión (2026-07-17): el nuevo motor añade disciplina top-down, pero esa corrida
no demostró edge (N 0–4). **Post-2026-07-24:** datos multi-año XAUUSD/EURUSD M15 ya en disco
(R5 cerrado a nivel datos). La brecha abierta es **re-run A12 + edge del motor**, no "falta parquet".

> ⚠️ **AUDITADO 2026-07-17 (docs/auditorias/AUDIT_R6_V2_MTF_Y_EDGEDIAG_2026-07-17.md):**
> este backtest **NO es reproducible** — el commit eb691c5 no versionó `ict_backtest/v2/`.
> El veredicto es provisional hasta versionar el motor + resolver fallas de ablación/DSR-PBO.
> **Falla "XAUUSD M15 ausente" = RESUELTA en datos (2026-07-24).**

**Veredicto global:** 🔴 GATE R6 NO PASA en NINGÚN símbolo en modo producción (ablation R6.4).
- Reloj (G1→G2): ruido (<0.1 PF en todos). El motor ya opera open≈close.
- Costos (G2→G3): HUNDEN todo (USDCHF +9.99→-0.13; USDCAD +5.09→-8.64). Es física, no bug.
- USDCHF/USDCAD dan PF + en TEORÍA (sin costos, WR 40-48%): el motor detecta
  estructura direccional real, pero el edge es MÁS FINO que el costo de transacción.
  No es "sin edge", es "edge < costo". Mejorar EDGE (RR/filtro), no quitar costos.
- Conclusión: el cuello NO es reloj/look-ahead (limpio desde R4/R6.1). Es edge < costo
  en las ventanas cortas medidas. **Siguiente paso real = A12 walk-forward multi-año
  (data R5 ya disponible)** y/o mejorar el motor (RR, filtro, símbolos de mayor rango).
- N baja (18-38) en R6.4 era por ventana ~8000 velas, no porque falte el archivo M15 largo.

**Bug G3 encontrado y corregido:** `simulate_trade` dividía la comisión por `risk`
(inflaba pnl_r cuando risk~0 por SL mal ubicado a <1 pip del entry en hold_limit
lejano → PF falsamente -70). Fix: comisión en precio + piso risk 1 pip. Test:
`test_cost_does_not_inflate_pnl_with_small_risk`.

**Conclusión:** EURUSD M15 con el motor canónico de esa ablation NO tiene edge en ~3 meses.
No es un bug de R6 — es el veredicto honesto de esa ventana. Próximo paso sugerido:
**A12 con XAUUSD/EURUSD M15 multi-año ya en disco** (y re-baseline con costs ON), no re-descargar R5.

---

## 1. Gates de calidad (roadmap)

| Gate | Criterio | Estado |
|------|----------|--------|
| Edge diagnosis OOS | PF ≥ 1.10 en >1 símbolo | ✅ (XAUUSD 1.376, USDCAD 1.264, …) |
| Walk-forward celda top (A12) | PurgedKFold, DSR>0, N≥200/fold, PF≥1.10 | 🔴 Pendiente re-run (1er pase falló; **data multi-año ya disponible**) |
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

> ⚠️ **ADVERTENCIA LOOK-AHEAD (2026-07-13):** Las corridas R4 v2 / v2.5 / v2.6
> (§8.1 y §8.2 previo) estaban CONTAMINADAS por look-ahead cross-timeframe en
> el join H4→M5 (`row_at_time` leía la barra H4 aún en formación: 97.4% de las
> velas M5 afectadas, ver `docs/auditorias/AUDIT_LOOKAHEAD_HTF.md`). Sus PF NO
> son concluyentes. La corrida LIMPIA es **R4 v2.7** (fix aplicado). Usar SOLO
> v2.7 para decidir Optuna.

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

### 8.2 R4 v2 / v2.5 — displacement ON + re-medicion (2026-07-13)

**v2** (`results/r4/r4v2_chain_20260713T172623Z.json`, 8 workers):
displacement ON, confirm_bars=2 (default motor). EURUSD+GBPUSD, M15.

| Exp | Modelo | PF | WR | Trades | Total R |
|-----|--------|----|----|--------|---------|
| EURUSD | Turtle+disp | **1.143** | 36.4% | 11 | +1.0 |
| GBPUSD | Turtle+disp | 0.533 | 21.1% | 19 | -7.0 |
| EURUSD | PO3+disp | 0.000 | 0% | 1 | -1.0 |
| GBPUSD | PO3+disp | 0.000 | 0% | 0 | 0 |
| EURUSD | Silver+disp (M15) | 0.000 | 0% | 0 | 0 |
| GBPUSD | Silver+disp (M15) | 0.000 | 0% | 0 | 0 |
| EURUSD | PO3+disp+cost | 0.000 | 0% | 1 | -1.1 |
| EURUSD | Turtle+disp+cost | 0.920 | 36.4% | 11 | -0.6 |

| **v2.5** (`results/r4/r4v25_chain_20260713T182942Z.json`, 4 workers):
| Silver Bullet con M5 reales (50k bajadas via MT5) + PO3 remedir.
| (ANTES de los parches de TF/mapeo — Silver/PO3 silenciados).
| | EURUSD | Silver+disp (M5) | 0.000 | 0% | 0 |
| | GBPUSD | Silver+disp (M5) | 0.000 | 0% | 0 |
| | EURUSD | PO3+disp (M15) | 0.000 | 0% | 1 |
| | GBPUSD | PO3+disp (M15) | 0.000 | 0% | 0 |
|
| **v2.6** (`results/r4/r4v26_chain_20260713T192129Z.json`, 4 workers):
| MISMOS experimentos PERO con los 3 parches aplicados (TF dinamico +
| choch_status mapeado). displacement ON.
| | EURUSD | Silver+disp (M5) | 0.000 | 0% | **0** |
| | GBPUSD | Silver+disp (M5) | 0.000 | 0% | **0** |
| | EURUSD | PO3+disp (M15) | **2.000** | 50% | 2 |
| | GBPUSD | PO3+disp (M15) | 0.000 | 0% | 1 |

### 8.2b R4 v2.7 — CORRIDA LIMPIA (look-ahead fix, 2026-07-13)

**v2.7** (`results/r4/r4v27_chain_20260713T201306Z.json`, 4 workers):
Tras aplicar los 4 fixes de la IA externa (look-ahead HTF corregido en
`row_at_time`, exec_tf explícito, choch_status mapeado, displacement HTF en
sequence.py). Silver Bullet corre **SIN `--require-displacement`** (ruptura
rápida NY AM es incompatible con displacement en vela M5, ver AUDIT_BUG_SILVER_TF).

⚠️ **v2.7 tenía look-ahead RESIDUAL (2.08% de velas en límite H4):** el primer
parche solo descontaba `freq` en la rama asof, no en el match exacto. La IA lo
detectó probando el propio parche (M5 08:00 devolvía H4 08:00 sin cerrar). Fix
aplicado + test de regresión (`test_row_at_time_exact_boundary_closed`, 8/8
passed). **v2.7 NO es "limpio confirmado"** — re-correr en **v2.8** con el fix
residual para veredicto definitivo. Ver `AUDIT_LOOKAHEAD_HTF.md` (Fix residual).

| Exp | Modelo | PF | WR | Trades | Total R | MaxDD R |
|-----|--------|----|----|--------|---------|---------|
| EURUSD | **Silver (M5, sin disp)** | **0.896** | 32.4% | **71** | -4.9 | -10.8 |
| GBPUSD | **Silver (M5, sin disp)** | **0.639** | 25.0% | **72** | -19.5 | -20.5 |
| EURUSD | PO3+disp (M15) | 0.000 | 0% | 2 | -2.0 | -2.0 |
| GBPUSD | PO3+disp (M15) | 0.000 | 0% | 0 | 0.0 | 0.0 |

**Veredicto (gate PF≥1.10, SOLO v2.7 válido — v2/v2.5/v2.6 contaminados):**
- **Silver Bullet: RECHAZADO** — PF 0.896/0.639 con muestra REAL (71/72 trades).
  No era bug de silenciamiento: al destaparlo da señales y **sigue perdiendo**.
  Modelo sin edge (o mal calibrado en RR/SL). Archivar como "sin edge".
- **PO3: INCONCLUSO** — 2/0 trades, insuficiente. Dispara poco en M15.
- **Turtle Soup: PENDIENTE re-medir** — v2 (PF 1.143 EURUSD) estaba contaminado
  por look-ahead. Re-correr en v2.8 para veredicto limpio.
- El look-ahead NO hundía Silver (lo mataba el displacement); afecta más a
  PO3/Turtle (sesgo H4 contaminado). Re-medir Turtle es prioritario.

**Parches aplicados (autorizados por Ruben, SIN commit — regla de hierro):**
1. `rules.checklist_scalping` l.198: sweep busca el TF cargado (M5/M15/M1),
   no "M15" hardcoded.
2. `rules.checklist_scalping` l.181: direccion usa el exec TF cargado.
3. `engine._build_estructura` l.251: `choch_status` mapeado desde
   `choch_signal` (el PO3 en backtest ignoraba el CHOCH).

**Resultado de los parches:**
- Silver Bullet paso de 0 → **122 senales "ready"** en EURUSD M5 (50k velas).
  El backtest SÍ lo detecta ahora. PERO el filtro `require_displacement`
  (R4 v2, que SI mejoro Turtle 0.689→1.143) **mata TODAS las 122**:
  0 de las 122 velas ready tienen displacement en M5. Silver Bullet (ruptura
  rapida NY AM) es INCOMPATIBLE con el filtro displacement. R4 v2.6 Silver = 0
  trades NO es bug ni "sin edge": es régimen incompatible.
  (Siguiente paso: re-medir Silver SIN --require-displacement.)
- PO3 paso de 1→2 senales EURUSD, PF 0.000→**2.000** (50% WR). El
  mapeo choch funciono: el PO3 ahora ve el CHOCH. PERO 2 trades = muestra
  INSUFICIENTE (requiere >=30 para conclusion). GBPUSD: 1 trade.

**Veredicto R4 (gate) — FINAL:**
- **Turtle Soup: UNICO medido honestamente.** EURUSD PF 1.143 (11t, roza
  gate ligero) / GBPUSD PF 0.533 (19t, PIERDE). NO cumple gate robusto.
- **PO3:** parche choch funciono (PF 2.000 EURUSD) PERO muestra insuficiente
  (2-3 trades). No concluyente. Necesita mas simbolos o ventana mas larga.
- **Silver Bullet:** 122 setups teoricos, 0 ejecutables con displacement. El
  filtro displacement (que ayudo a Turtle) lo anula. Re-medir SIN displacement.
- El PF 1.61 del §4 era del pipeline ML combinado, NO de modelos puros.

### 8.3 R4-clean + funding-gate 6m (2026-07-17) — CIERRE OFICIAL

**Script:** `scripts/r4_clean_funding_gate.py`  
**Informe:** `docs/auditorias/R4_CIERRE_FUNDING_2026-07-17.md`  
**JSON:** `results/r4/r4_clean_funding_LATEST.json`

Meta de producto: en ~6 meses de histórico, shape de fondeo (~8% sin romper ~4% daily / ~8% max DD a 1% riesgo/trade).

| Celda (H4→M15, 180d, costos ON) | Trades | PF | Equity% fondeo | Viable fondeo |
|----------------------------------|--------|-----|----------------|---------------|
| EURUSD Turtle CT | 5 | 0.70 | −0.97 | NO |
| EURUSD Sequence AT | 5 | 1.18 | +0.37 | NO (no llega a +8%) |
| GBPUSD Turtle CT | 7 | 0.34 | −3.33 | NO |
| GBPUSD Sequence AT | 9 | 0.06 | −6.50 | NO |

**Veredicto R4 final:** `REJECT_NO_EDGE` — ICT mecánico (sequence tesis 18) **no** apto para live/auto ni para pretender challenge FundedNext.  
**Decisión:** NO Optuna sobre estos modelos. Observador + riesgo humano OK; bot ICT NO.

**Decision actual (pre-8.3, histórico):** NO Optuna sobre modelos aislados. Turtle no cumple gate
robusto; PO3 muestra insuficiente; Silver pendiente de re-medicion sin
displacement. Parches de backtest aplicados y verificados (smoke 122 ready),
SIN commit por regla de hierro de Ruben.

```markdown
Métricas: ver [METRICS_CANON §3](../METRICS_CANON.md#3-ict_backtest-post-auditoría-2026-07-11).
No duplicar PF aquí.
```

Si una corrida nueva contradice este archivo: **actualizar § correspondiente** y poner fecha.
