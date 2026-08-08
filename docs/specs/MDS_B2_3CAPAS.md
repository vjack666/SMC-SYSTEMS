# MDS_B2_3CAPAS.md — 3 capas HTF / ITF / exec (top-down) (B2)

- **Clasificación**: OBLIGATORIO · Fase B2 · **Estado: ✅ HECHO (en motor)**
- **SDD-first**: refleja `engine/plan.build_context_stack` + `top_down_allows_trade`.

## Propósito
Lectura top-down D1→H4→H1→M15→M5→M1: el sesgo de los TF altos filtra la
operación en los bajos. El "Jefe" (D1) manda; el "Ejecutor" (M5/M1) obedece.

## Por qué importa (geometría)
Es la jerarquía de la tesis: nadie opera contra el sesgo del Jefe. Cada capa se
lee por geometría (trend por swings, premium/discount por dealing range). Cero
indicadores. VOLUMEN: confirma el sesgo en el TF que lo rompe (dato, no indicador).

## Entradas (geometría + volumen)
- `ms`: DataFrames OHLC por TF (D1/H4/H1/M15/M5/M1).
- `t`: timestamp de evaluación.
- VOLUMEN: tick volume por TF para confirmar rompimientos de estructura.

## Lógica (engine/plan)
`build_context_stack(ms, t, tfs=("D1","H4","H1","M15","M5","M1"))` arma el stack
con premium/discount por capa. `top_down_allows_trade(stack, target, ...)`
aplica el gate: si el D1 está en contra, veta SHORT (d1_against_short). Anti
look-ahead por timestamp en cada capa.

## Salidas
`{"allow": bool, "bias_by_tf": {...}, "reason": str}`.

## Integración
`engine/plan.py` es única fuente. `ict_backtest/canonical.est_htf_ctx_fn` lo
construye y se lo pasa a `run_sequence` (backtest consumidor puro). Ley respetada.

## Verificación
`pytest tests/test_engine_plan_pd.py` + probe sintético de 4 capas (LONG ok, SHORT
veto). Ver skill smc-systems-devops §9g-b.
