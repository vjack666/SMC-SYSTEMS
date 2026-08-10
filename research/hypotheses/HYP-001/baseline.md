# HYP-001 — Baseline exacto (fijado 2026-08-10)

> Complementa `hypothesis.md`. Define SIN AMBIGÜEDAD contra qué se compara HYP-001.
> NO es ejecución: es la especificación del contraste estadístico.

## 1. Población de prueba

- **Grupo `aligned`** (tratamiento): fills de la estrategia canónica donde
  `HtfBias.aligned == True`, i.e. la entrada pasó `top_down_allows_trade(...,
  require_d1/h4/h1=True)` con D1/H4/H1 no-contradictorios (gate ya relajado,
  `engine/bias/narrative.py:88-94`).
- **Grupo `against`** (control): misma estrategia canónica, misma corrida, mismo
  `costs ON`, misma `seed`, pero fills donde el sesgo no califica como `aligned`
  (incluye contra-sesgo y neutral). Es el MISMO motor sin el filtro aligned.

Esto garantiza que la comparación aisla el efecto del filtro HTF, no el de otros
parámetros de la estrategia.

## 2. Variable primaria

- `WR_aligned` = win rate del grupo `aligned`.
- `PF_aligned` = profit factor del grupo `aligned` (suma ganancias / suma pérdidas).
- Análogos `WR_against`, `PF_against` para el control.

## 3. Baselines (tres niveles, cada uno responde una pregunta distinta)

### 3.1 Baseline teórico de ruido (¿la dirección es azar?)
- `WR_random ≈ 0.50` (win rate de una moneda justa en fills binarios).
- Uso: si `WR_aligned ≈ 0.50`, el filtro no añade dirección predictiva alguna.

### 3.2 Baseline por permutación (¿la señal es ruido browniano del tramo?)
- Ya empleado en `docs/tesis/HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md` §7.8/7.9:
  `n_perm = 50` permutaciones de `bos_dir`/`choch_dir`; reporta
  `against_hit_baseline_mean ≈ 0.72-0.77` en EURUSD 113k.
- Uso: `against_hit` observado (72-75%) ≈ baseline permutado ⇒ el ~72-75% es
  ruido del tramo, NO edge. El mismo procedimiento se aplica a `WR_aligned`.

### 3.3 Baseline de control intra-corrida (¿el filtro mejora sobre ignorar sesgo?)
- **Este es el baseline decisivo de HYP-001**: `WR_against` y `PF_against`
  (la misma estrategia sin filtro aligned, misma corrida).
- HYP-001 se acepta SOLO si `WR_aligned > WR_against` Y `PF_aligned > 1.0`.
- No se compara contra un número de aire: se compara contra el control hermano.

## 4. Criterio de falsación (idempotente, sin ajuste de narrativa)

HYP-001 queda **REFUTADA** si, en la población `aligned>0` (producida por los
auxiliares CAND-03/05):
- `WR_aligned <= WR_against` (el filtro no mejora la dirección), O
- `PF_aligned <= 1.0` (la ventaja no es económicamente positiva tras costs).

Y adicionalmente si `WR_aligned ≈ WR_random` y ≈ baseline por permutación, se
confirma que el filtro HTF es ruido, no edge.

## 5. Significancia (tribunal, ver contrato §8)

- Test: comparación de proporciones (WR) + ratio de PF; ajuste **FDR** (o
  Bonferroni) con `alpha = 0.05` sobre los TF/segmentos evaluados.
- El `verdict.yaml` de EXP-001 incluirá `adjusted_p` y `method`.
- La población `aligned` debe ser suficiente (N eventos >= 30 por segmento) para
  que la estimación sea estable; si no, veredicto **INCONCLUSIVA** (nuevo EXP con
  más datos), no REFUTADA forzada.

## 6. Qué NO es el baseline de HYP-001

- NO es "el motor ya tiene HTF, luego funciona" (eso es la falacia que 3B.2 evita).
- NO es el resultado de CAND-03/05 (esos solo producen la población `aligned`;
  no cuentan como evidencia de edge).
- NO es un baseline externo arbitrario; es el control `against` de la misma corrida.

---
*Baseline fijado por diseño. Sin ejecución. Pendiente: ejecutar auxiliares (CAND-03/05) para
producir la población `aligned`, luego EXP-001 con este contraste.*
