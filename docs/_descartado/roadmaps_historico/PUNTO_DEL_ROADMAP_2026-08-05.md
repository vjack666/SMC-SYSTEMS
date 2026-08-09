# Punto del Roadmap — 2026-08-05 (vista del MOTOR / trader humano)

Este diff cruza el roadmap histórico (CRONOGRAMA_Y_ROADMAP.md al 2026-07-21,
medido en el **backtest**) contra el estado REAL del **motor** (`engine/`) que
usa el trader humano hoy. Hecho por el agente humano para que el ingeniero
revierta y ubique el punto.

## Hallazgo central
El roadmap (2026-07-21) marca la mayoría de hitos como **CERRADOS** — pero
cerrados en `ict_backtest/` (el backtest, que es desechable). El motor
(`engine/`) se construyó DESPUÉS de esa fecha y está en un punto DISTINTO.
**El roadmap no refleja el motor.** Por eso el humano no podía ubicarse.

## Matriz roadmap → motor (2026-08-05)

| Hito roadmap (backtest) | Estado en BACKTEST (2026-07-21) | Estado en MOTOR engine/ (2026-08-05) | Veredicto |
|---|---|---|---|
| R1 POI state / tesis | ✅ backtest | engine/htf_narrative + poi_anchor | ✅ MOTOR tiene narrativa + ancla |
| R3.5 Brecha A1 (3 capas D1→H4→H1) | ✅ backtest (`top_down_allows_trade`) | ✅ **CERRADO hoy** (`engine/plan.py`) | ✅ MOTOR al día |
| Brecha A (POI anclado) | ✅ backtest (`htf_poi_fn` bonus) | ✅ **CERRADO hoy** (`engine/poi_anchor.py`) | ✅ MOTOR al día |
| Bias HTF (D1/H4/H1) | ✅ backtest | ✅ `engine/bias/narrative.py` | ✅ MOTOR al día (con bug T8 NEUTRAL en rango) |
| BOS/CHOCH estructura | ✅ backtest | ✅ `engine/bos/structure.py` | ✅ MOTOR al día |
| OB / FVG | ✅ backtest | ✅ `engine/order_block.py` / `engine/fvg_poi.py` | ✅ MOTOR al día |
| Liquidez BSL/SSL | ✅ backtest | ✅ `engine/liquidity_levels.py` | ✅ MOTOR al día |
| Dealing range EQ/premium-discount | ✅ backtest | ✅ `engine/dealing_range.py` | ✅ MOTOR al día |
| **B2 exec TF M5/M1** | ✅ backtest | ❌ **NO en motor** | 🔴 MOTOR ATRASADO |
| **C2 Silver Bullet / C3 Turtle / D1 OTE** | ✅ backtest (setups) | ❌ **NO en motor** | 🔴 MOTOR ATRASADO |
| **E1 Trade Management (BE/parcial/trailing)** | ✅ backtest | ❌ **NO en motor** | 🔴 MOTOR ATRASADO |
| R4 ICT puro (gate fondeo) | ✅ Cerrado (REJECT_NO_EDGE) | N/A (motor no es backtest) | — |
| R6 backtest profesional | 🔶 G1-G3 done / auditoría abierta | N/A | — |
| A11 arranque FundedNext | ✅ | ✅ (modo bajo demanda, auto-arranque OFF) | ✅ |

## Conclusión: ¿en qué punto del roadmap estamos?
Como trader humano, mi motor (lo que leo en vivo) tiene cerradas las capas de
**LECTURA** (sesgo, estructura, OB/FVG, liquidez, dealing range, narrativa HTF,
POI anclado, plan top-down 3 capas). Eso cubre la mayor parte de R1, R3.5,
Brecha A, y la lectura de la tesis 18.

Pero el motor AÚN NO tiene la capa de **EJECUCIÓN FINA** que el roadmap marcó
cerrada en el backtest:
- entry/SL/TP en M5/M1 (B2) — el motor solo opera M15.
- setups Silver Bullet / Turtle Soup / OTE (C2/C3/D1) — el motor no los nombra.
- gestión post-entrada BE/parcial/trailing (E1) — el motor no la tiene.
- bug T8: sesgo NEUTRAL perpetuo en rangos (el motor a veces no dice nada).

O sea: **el motor está en el punto "lectura completa, ejecución fina pendiente"
del roadmap**. El backtest estaba más adelantado en ejecución, pero el backtest
es desechable y el motor es lo permanente. El trabajo futuro del motor es
subir B2/C2/C3/D1/E1 al engine/ y arreglar T8.

## Próximo paso que el humano pide al ingeniero
1. Subir B2 (exec M5/M1) al motor — es lo que el humano haría para entrar fino.
2. Arreglar T8 (sesgo NEUTRAL en rango).
3. Luego C2/C3/D1 (setups) y E1 (trade mgmt) al motor, cuando el humano lo pida.
4. El backtest queda como demostración de que el motor funciona (desechable).

## Nota de orden
Los roadmaps originales están en `docs/planificacion/_roadmap_historico/` marcados
como HISTÓRICOS (no fuente de verdad). Este archivo es el mapa vivo del punto
actual desde la vista del motor.
