# 01 — Checklist de backtest profesional

| Campo | Valor |
|-------|-------|
| **ID** | `13/01_CHECKLIST_PROFESIONAL` |
| **Versión** | 1.0 |
| **Fecha** | 2026-07-13 |
| **Estado** | Stable |

---

## 1. Teoría

Un backtest profesional no “prueba si la idea habría ganado en el chart”.  
**Simula un sistema de trading en el tiempo**: datos → decisión → orden → fill → costos → riesgo → métricas, **con la misma información que habría tenido un operador o bot en vivo**.

Si el simulador ve el futuro (aunque sea una mecha de H4 incompleta), el número es **ficción estadística**, no edge.

---

## 2. Práctica (qué miran los profesionales)

### A. Integridad del tiempo (look-ahead)

| # | Punto | Pregunta de auditoría |
|---|-------|------------------------|
| A1 | Causalidad de features | ¿La fila `t` solo usa datos ≤ `t`? |
| A2 | Confirmación de swings | ¿El swing se expone solo en la vela de confirmación? |
| A3 | Multi-TF | ¿HTF solo **cerradas** a `now`? |
| A4 | Indicadores | ¿EMA/ATR/RSI sin ventana centrada ni futuro? |
| A5 | Labels ML | ¿El target no filtra el outcome del trade a features de entrada? |

### B. Ejecución realista

| # | Punto | Pregunta |
|---|-------|----------|
| B1 | Timing de fill | ¿Signal close → fill next open (o modelo de latencia)? |
| B2 | Spread | ¿Spread bid/ask por símbolo y sesión? |
| B3 | Slippage | ¿Adverso al trade, no cero? |
| B4 | Comisión | ¿Round-turn en pips o dinero? |
| B5 | Path OHLC | ¿Orden SL/TP en la misma barra es pesimista o documentado? |
| B6 | Gaps | ¿Apertura de sesión / lunes salta SL sin fill mágico en el vacío? |
| B7 | Swap / overnight | ¿Si el hold cruza rollover, hay financiamiento? |

### C. Validación anti-overfit

| # | Punto | Pregunta |
|---|-------|----------|
| C1 | OOS | ¿Hay hold-out temporal nunca usado para tunear? |
| C2 | Walk-forward | ¿Train → test en el **futuro**, multi-fold? |
| C3 | Purge / embargo | ¿Se evitan trades que cruzan el corte train/test? |
| C4 | Multiple testing | ¿Cuántas variantes se probaron antes del “ganador”? |
| C5 | PBO / DSR | ¿Hay métrica de probabilidad de overfit / Sharpe deflactado? |
| C6 | N mínimo | ¿Trades OOS suficientes para no confiar en ruido? |
| C7 | Estabilidad de params | ¿Los hiperparámetros saltan de fold a fold? |

### D. Datos y régimen

| # | Punto | Pregunta |
|---|-------|----------|
| D1 | Zona horaria | ¿UTC canónico; killzones en la misma TZ que el live? |
| D2 | Timestamp | ¿Open vs close de barra documentado (MT5 = open)? |
| D3 | Completitud | ¿Huecos, duplicados, relojes de broker? |
| D4 | Régimen | ¿El edge vive solo en un subconjunto (tendencia 2023–24)? |
| D5 | Símbolos | ¿Multi-asset o un solo par “ganador”? |

### E. Portafolio y riesgo

| # | Punto | Pregunta |
|---|-------|----------|
| E1 | Una posición | ¿Se bloquean señales mientras hay trade abierto? |
| E2 | Correlación | ¿EURUSD + GBPUSD abren el mismo riesgo 2×? |
| E3 | Sizing | ¿R fijo / Kelly / % equity; coherente con prop firm? |
| E4 | DD diario | ¿Reglas FundedNext / prop se simulan? |
| E5 | Código único | ¿Live y backtest llaman la **misma** función de decisión? |

---

## 3. Algoritmo (cómo auditar en 30 min)

```text
1. Elegir 1 símbolo + 1 TF reloj (LTF)
2. Tomar 3 timestamps al azar en el medio de una H4
3. Dump de features HTF usadas en t → ¿OHLC HTF ya “completo”?
4. Dump de 5 trades → entry_time, entry_price vs open[i+1]
5. Re-correr con cost={spread,commission,slippage} > 0
6. Contar cuántos trials de optimización se hicieron antes del PF reportado
7. Ver N de trades OOS y folds con PF < 1
```

Si falla el paso 3 o 4 → **no reportar edge de producción**.

---

## 4. Código SMC-SYSTEMS

Ver [06_GAP_SMC_SYSTEMS](06_GAP_SMC_SYSTEMS.md) para el mapa punto a punto.

---

## 5. En resumen

El checklist profesional es una **lista de mentiras que el backtest puede contarte**.  
Cada fila debe ser “pasamos / fallamos / documentado como theory_mode”, no “asumimos que está bien”.
