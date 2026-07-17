# Reporte — Backtest v2 mtf (motor multi-TF) + Mapa ICT M15

**Fecha:** 2026-07-17
**Autor:** Hermes (ejecución) · revisión Ruben
**Alcance:** correr el motor v2 mtf (D1→H4→H1→M15) con costos ON y validación OOS sobre
los 7 símbolos disponibles; construir el mapa ICT M15 estilo TradingView (6 meses);
comparar contra R6.4 (legacy H4→M15).

---

## 1. Qué se corrió (datos reales, no simulados)

- Motor: `ict_backtest/v2/run_v2.py --mode mtf` (cascada D1→H4→H1→M15, filtro top-down
  premium/discount + sesgo HTF).
- Costos: ON (default producción). OOS: 0.3 (30% final fuera de muestra).
- Símbolos: EURUSD, GBPUSD, USDJPY, AUDUSD, NZDUSD, USDCAD, USDCHF.
  **XAUUSD EXCLUIDO** (falta M15 localmente).
- Ventana: datos disponibles ~6 meses (2026-01-18 → 2026-07-16). El H1/M15 se descargó
  esta sesión vía `scripts/download_h1_mtf.py` (MT5 MetaQuotes-Demo, ~6 meses de histórico).
- Scripts nuevos: `scripts/run_bt_v2_mtf.py`, `scripts/build_m15_structure.py`,
  `scripts/download_h1_mtf.py`.

---

## 2. Resultados v2 mtf (costos ON, OOS 0.3)

```
SÍMBOLO   orders trades  WR     PF      R      OOS_PF   cov
EURUSD       0     0   0.0%  0.000   0.0    —       86.1% [v2_partial]
GBPUSD       1     1   0.0%  0.000  -1.0   0.000    86.1% [v2_partial]
USDJPY       1     1 100.0%  inf*    1.0   inf*     86.1% [v2_partial]
AUDUSD       4     4   0.0%  0.000  -4.4   0.000    86.1% [v2_partial]
NZDUSD       2     2   0.0%  0.000  -2.2   0.000    86.1% [v2_partial]
USDCAD       4     4  25.0%  0.510  -1.5   0.000    86.1% [v2_partial]
USDCHF       3     3  33.3%  0.295  -1.5   inf*     86.1% [v2_partial]
```
`* inf` = ganó el único trade y no hubo pérdida → PF indefinido (N=1). NO es edge real.

---

## 3. Comparación R6.4 (legacy) vs v2 mtf

```
SÍMBOLO      R6.4 PF    v2 mtf PF   v2 mtf N   Nota
EURUSD        -4.89     0.000 (0 tr)  0        filtro lo excluye todo
GBPUSD        -7.07     0.000         1        legacy perdía fuerte; v2 no opera
USDJPY          —        inf*         1        N=1, no concluyente
AUDUSD          —       0.000         4        todos perdieron
NZDUSD          —       0.000         2        todos perdieron
USDCAD        -8.64     0.510         4        1 ganador de 4
USDCHF        -0.13     0.295         3         1 ganador de 3
```
R6.4 usó 8000 velas (~2 años); v2 mtf usó ~6 meses. Sample no comparable en tamaño.

---

## 4. Lectura honesta

1. **El v2 mtf es MUY más selectivo.** 0–4 trades/símbolo en 6 meses (legacy hacía 18–38).
   El filtro top-down D1+H1+premium/discount mata casi todo. Diseño "menos, mejor", pero
   el sample queda minúsculo → PF 0.000 = no hay suficiente para medir.
2. **Donde legacy perdía fuerte (GBPUSD -7.07, USDCAD -8.64), v2 no pierde porque casi no
   opera.** No es que "ganó": el filtro lo dejó fuera. El PF negativo desaparece por falta
   de trades, no por edge.
3. **Ningún símbolo pasa el gate de producción** (PF OOS ≥ 1.10). Los "inf" son trampa de N=1.
4. **Coverage v2_partial = 86.1%**: 14 implementadas, 3 parciales, **1 ausente (C06 = POI
   anclado a narrativa HTF)**. El propio reporte del motor dice:
   *"resultado de implementación parcial — NO interpretar como edge de la tesis ICT completa"*.

---

## 5. Conclusión

El motor nuevo **no "arregla" el fallo de R6.4** — simplemente opera tan poco que el PF
negativo desaparece por falta de trades. El veredicto R6 (gate no pasa en producción) se
mantiene. La brecha real es la MISMA advertida en AGENTS.md:

- **Falta POI anclado (C06 missing)** en el motor.
- **Falta R5 (datos ≥3–4 años)** — la cuenta MT5 demo solo da ~6 meses. XAUUSD M15 ausente.

El filtro multi-TF añade disciplina, no edge. Para declarar "stack ICT intradía sin edge"
hace falta cerrar la brecha B (POI anclado) y A1 (3 capas reales) sobre datos profundos.

---

## 6. Mapa ICT M15 (visual, estilo TradingView)

- `scripts/build_m15_structure.py` generó 110 frames PNG (`results/mapa_m15_build/
  EURUSD_M15_frame_0000.png` → `frame_0109.png`) sobre EURUSD M15, últimos 6 meses.
- Cada frame muestra velas acumuladas + zonas ICT detectadas HASTA ese punto: Order Block,
  FVG, BSL/SSL (liquidez), BOS activo, CHOCH, premium/discount 50%, OTE.
- **No es precio en vivo**: avanza sobre el histórico cerrado. Para animación, unir en GIF.
- Tabla de estructura en vivo (BOS/FVG/CHOCH/OB fluyendo por TF):
  `results/bt_v2/EURUSD/mtf_intraday/live_structure.csv` (61.347 eventos).

---

## 7. Pendiente (no resuelto en esta sesión)

- R5: bajar ≥3–4 años M15 (XAUUSD bloqueado por datos demo). Requiere terminal FundedNext real.
- A12: walk-forward OOS de `no_session`×XAUUSD (bloqueado por R5).
- C06 POI anclado en motor v2.
- (Opcional) unir frames M15 en GIF animado.
