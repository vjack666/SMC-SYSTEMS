# Prompt para IA externa — SMC-SYSTEMS backtest ICT (R4)

Contexto: queremos medir modelos ICT aislados (PO3, Turtle Soup, Silver Bullet)
en un backtest vela-a-vela honesto antes de Optuna. Encontré que PO3 y Silver
Bullet daban 0-1 señales no por "sin edge" sino por bugs del backtest que los
silenciaban. Apliqué 3 parches (commit b641a83, rama main). Necesito una
segunda opinión ingenieril sobre los parches, el diseño del motor, y qué
medir a continuación. Repo: https://github.com/vjack666/SMC-SYSTEMS (main @ b641a83)

## BUGS ENCONTRADOS Y PARCHES YA APLICADOS

### Bug 1 (Silver Bullet) — `ict_backtest/rules.py` `checklist_scalping`
El checklist buscaba el sweep y la dirección en "M15" HARDCODEADO, pero el
backtest de scalping corre con `--ltf M5` (no carga M15). Resultado: sweep
siempre "none" -> item FALTA permanente -> 0 señales.
Parche: derivar el exec TF de la estructura (M5/M15/M1 por prioridad):
```python
_exec_tf = next((t for t in ("M15","M5","M1") if t in estructura and estructura[t]), None)
sw = _sweep_dir(estructura, (_exec_tf,)) if _exec_tf else "none"
# y m15 = estructura.get(_exec_tf, {}) para la direccion
```
Tras el parche: Silver Bullet pasó de 0 -> 122 señales "ready" en EURUSD M5.

### Bug 2 (PO3) — `ict_backtest/engine.py` `_build_estructura`
`build_features` crea `choch_signal` pero el engine lo pasaba como
`choch_status` (vacío). La fase D del PO3 ignora el CHOCH en backtest.
Parche:
```python
"choch_status": str(row.get("choch_signal", row.get("choch_status", ""))),
```
Tras el parche: PO3 EURUSD PF 0.000 -> 2.000 (50% WR), pero solo 2 trades.

### Bug 3 (H1 test, NO tocado) — `tests/test_ict_backtest.py::test_choch_differs_from_bos`
Falla (AssertionError: no se produjo ningun BOS). Causa: el test asume
`confirm_bars=1` pero el motor usa `confirm_bars=2` por defecto (filtra BOS de
1 vela). `confirm_bars=2` es diseño correcto (filtra fakeouts), reduce ~24% de
eventos. El test está mal escrito para el comportamiento actual.

## NÚMEROS R4 (commit b641a83, displacement ON)

| Modelo | PF | WR | Trades | Nota |
|--------|----|----|--------|------|
| Turtle EURUSD | 1.143 | 36.4% | 11 | roza gate ligero |
| Turtle GBPUSD | 0.533 | 21.1% | 19 | PIERDE |
| PO3 EURUSD | 2.000 | 50% | 2 | parche OK, muestra insuficiente |
| PO3 GBPUSD | 0.000 | 0% | 1 | insuficiente |
| Silver EURUSD | 0.000 | 0% | 0 | 122 ready pero 0 con displacement |
| Silver GBPUSD | 0.000 | 0% | 0 | idem |

Hallazgo clave: el filtro `require_displacement` (que SÍ mejoró Turtle
0.689->1.143) MATA Silver Bullet: de las 122 señales ready, 0 tienen
displacement en la vela M5. Silver Bullet (ruptura rápida NY AM) es
INCOMPATIBLE con exigir displacement fuerte en M5.

## PREGUNTAS PARA LA IA EXTERNA

1. ¿Los 3 parches son la forma correcta de arreglar el contrato de TF/mapeo,
   o hay un diseño más limpio (ej pasar `exec_tf` al checklist en vez de
   derivarlo por prioridad dentro de la función)?

2. ¿Es correcto medir Silver Bullet SIN `require_displacement` (como el
   backtest "oficial" Capa 2 del SDD, que no lo exige por defecto)? ¿O el
   displacement debería evaluarse en el HTF/sweep y no en la vela de entrada M5?

3. PO3 da PF 2.000 pero solo 2 trades en EURUSD (M15, 2024-07->2026-07).
   ¿Cómo aumentar la muestra honestamente (más símbolos? más ventana?) sin
   overfit? ¿El gate R4 (PF OOS >=1.10 y >=30 trades) es razonable?

4. ¿El motor vela-a-vela es correcto o hay look-ahead en cómo alinea el sesgo
   H4 por vela (`estructura.get(htf,{}).get("trend")`)? ¿Cómo validar que no
   mira futuro?

5. H1: ¿arreglar el test (asumir confirm_bars=2) o cambiar el motor? ¿El test
   debería usar la config real del motor?

Archivos clave: ict_backtest/engine.py, ict_backtest/rules.py,
ict_backtest/run_backtest.py, scripts/r4_chain.py, docs/METRICS_CANON.md §8,
docs/auditorias/AUDIT_BUG_*.md
