# PROTOCOL_AUX_CAND-03-05 — Habilitación de HYP-001 (medición de `aligned`)

> **Protocolo de diseño (2026-08-10). NO EJECUTADO.** Auxiliares de HABILITACIÓN para
> HYP-001: su único propósito es producir una población `aligned>0` medible. NO constituyen
> evidencia de que el HTF funcione (ver HYP-001/hypothesis.md).
>
> Trazabilidad: derivado de `docs/architecture/MICRO_AUDIT_HYPOTHESES.md` Fase G.3 (CAND-03, CAND-05)
> y Fase G.4 (pre-requisito). Esta versión CORRIGE la 1ª/2ª pasada con dos hechos del repo:
> (a) el gate YA está relajado; (b) el runner citado no existe en la ruta original.

## 0. Estado real del motor (verificado en repo, 2026-08-10)

- `engine/bias/narrative.py:88-94` — `HtfBias.aligned` YA usa gate relajado:
  `non_neutral >= 2` y `len(set(non_neutral)) == 1` (sin contradicción). Es el cierre M7 (2026-08-08).
- `engine/bias/narrative.py:246-293` — `compute_htf_bias_series` emite `aligned` por cierre H4
  propagado por `ffill` a H1/M15.
- `engine/plan.py:375+` — `top_down_allows_trade` consume el sesgo vía `stack[tf]["trend"]`
  (D1/H4/H1) con `require_d1/h4/h1`. Es el gate operativo de la prueba padre.
- **El runner `scripts/measure_structure_effectiveness.py` NO existe** en la ruta citada por
  `LABORATORIO_ICT_SMC.md`. Existe en `scripts/_legacy/measure_structure_effectiveness.py`
  (huérfano, no verificado). El instrumento de medición de `aligned` debe localizarse/validarse
  antes de ejecutar (ver PASO 0 de cada auxiliar).

## 1. Naturaleza de los auxiliares

| ID | Qué hace | Qué NO hace |
|----|----------|------------|
| CAND-03 | Mide `aligned_hit_pct` en EURUSD bajo el gate YA relajado (¿aparece `aligned>0`?) | No modifica el motor; no prueba edge |
| CAND-05 | Mide `aligned_hit_pct` en GBPUSD (y otros) bajo el mismo gate (¿depende del símbolo?) | No modifica el motor; no prueba edge |

Si ambos producen `aligned>0`, HYP-001 se vuelve MEDIBLE → se habilita EXP-001 (prueba padre).
Si ambos dan `aligned=0%`, HYP-001 queda unfalsiable y se revisa la tesis (o se investiga CAND-04).

## 2. Pre-requisitos (regla fundamental del contrato §0/§5)

Antes de CUALQUIER ejecución (no hoy):
- `git rev-parse HEAD` → `run/commit` (commit base del motor ya-relajado).
- Hash de `config.yaml` y `data_manifest.json` (símbolos, rangos, hashes de parquet/CSV).
- El instrumento de medición debe ser una fuente VIVA y verificada, no `_legacy/` sin validar.

> Nota G.4 corregida: NO se modifica `engine/bias/narrative.py` para estos auxiliares (el gate ya
> está relajado). Por tanto no aplica "congelar hash antes del cambio" — el hash a congelar es el
> del estado ACTUAL del motor. Si en el futuro se quisiera un gate aún más laxo, sí aplicaría G.4.

## 3. CAND-03 — Protocolo determinista (EURUSD)

**Paso 0 — Instrumento**: localizar y validar el emisor de `aligned_hit_pct`. Opciones vivas en repo:
`scripts/_legacy/measure_structure_effectiveness.py` o `scripts/diagnose_bias_trace.py`. Verificar que
produce `aligned_hit_pct` por TF y compara contra baseline. Si ninguno sirve, el código del auxiliar
se escribe en `research/experiments/EXP-AUX-03/code/` consumiendo `compute_htf_bias_series` directo.

**Paso 1 — Datos**: EURUSD M15 + HTF, mismo dataset de HALLAZGOS (113.123 barras, ~4.5 años).
`data_manifest.json` con hash del parquet.

**Paso 2 — Config** (`config.yaml` aux-03):
```
symbol: EURUSD
max_bars: 113123
swing_lookback: 5
confirm_bars: 2
k: 5
gate: relaxed        # ya en motor (narrative.py:88)
n_perm: 50           # baseline por permutación
seed: 42
```

**Paso 3 — Ejecución**: correr instrumento con la config; capturar `aligned_hit_pct` por TF
(D1/H4/H1/M15) y `against_hit_pct`.

**Paso 4 — Baseline del auxiliar**: `aligned_hit_pct` bajo gate estricto ya medido = 0%
(HALLAZGOS_SESGO_BACKTEST, T8). El auxiliar pregunta si bajo gate RELAJADO `aligned_hit_pct > 0`.

**Paso 5 — Criterio de éxito del auxiliar** (no de HYP-001):
- ÉXITO (habilita HYP-001): `aligned_hit_pct > 0` en al menos un TF con N eventos suficiente
  (p.ej. N >= 30 para estimación estable).
- FALLO (no habilita): `aligned_hit_pct = 0%` → HYP-001 unfalsiable vía EURUSD; pasar a CAND-05.

## 4. CAND-05 — Protocolo determinista (GBPUSD y otros)

**Paso 0-2**: igual que CAND-03 pero `symbol: GBPUSD` (y opcionalmente USDCHF/USDCAD, mismos rangos).

**Paso 3-4**: mismo instrumento/config, distinto símbolo.

**Paso 5 — Criterio**:
- ÉXITO: `aligned_hit_pct(GBPUSD) > 0` bajo el mismo gate → la alineación es propiedad del régimen
  (no solo artefacto de EURUSD) → HYP-001 medible en GBPUSD.
- FALLO en TODOS los símbolos: la alineación es artefacto de gate/mercado, no de régimen →
  empuja a relajar aún más el gate (nuevo auxiliar) o a revisar CAND-04.

## 5. Qué ENTREGA este protocolo (sin ejecutar)

- `research/experiments/EXP-AUX-03/` y `EXP-AUX-05/` solo se crean al EJECUTAR (hoy no).
- El diseño aquí fija: instrumento, datos, config, baseline, criterio de éxito, y la regla de que
  el éxito de los auxiliares SOLO habilita HYP-001, no la prueba.
- La PRUEBA PADRE (EXP-001) es un EXP distinto (backtest canónico segmentando fills por `aligned`
  vs `against`), que se diseña aparte tras este.

## 6. Dominio REAL / OTC

- REAL (descubrimiento): datos reales EURUSD/GBPUSD del repo; medición de si `aligned` aparece.
- OTC (validación): la prueba padre (EXP-001) valida el edge; los auxiliares solo lohabilitan.
- ADR-005: DEUDA de trazabilidad (no existe físicamente en repo); se aplica criterio literal del
  Director hasta crear el artefacto.

---
*Protocolo de diseño. Sin ejecución. Sin modificación de código. Pendiente de autorización para ejecutar.*
