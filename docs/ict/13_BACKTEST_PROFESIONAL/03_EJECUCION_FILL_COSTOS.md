# 03 — Ejecución, fill y costos

| Campo | Valor |
|-------|-------|
| **ID** | `13/03_EJECUCION_FILL_COSTOS` |
| **Versión** | 1.0 |
| **Fecha** | 2026-07-13 |
| **Estado** | Stable · Needs-code (next-open default) |

---

## 1. Teoría

El edge de un sistema se come en tres sitios: **fill**, **fricción** y **path de precio**.  
Un PF calculado con fill mágico al close y spread 0 no es comparable a un challenge de prop firm.

### Modelo de fill profesional (barra)

| Modelo | Cuándo usarlo |
|--------|----------------|
| **Signal @ close → fill @ next open** | Default bar-based (recomendado industria) |
| Signal @ close → fill @ same close | Solo si el sistema live puede actuar **en el cierre** con latencia ~0 (raro en FX retail) |
| Tick / M1 path | Scalping fino; más caro de simular |

### Costos mínimos

| Costo | Notas FX/metales |
|-------|------------------|
| **Spread** | Variable por sesión (Asia vs NY); XAU ≠ EUR |
| **Commission** | Round-turn (ida+vuelta) |
| **Slippage** | Adverso; mayor en news y en XAU |
| **Swap** | Si `max_hold` cruza rollover / fin de semana |
| **Gap** | Lunes / post-news: SL no se llena en el nivel, se llena en el open |

### Path OHLC (ambigüedad intra-barra)

En una sola barra, high y low **no** revelan el orden.  
Regla profesional pesimista (conservadora):

- Long: si `low <= SL` y `high >= TP` en la misma barra → **cuenta SL** (o split 50/50 solo en análisis de sensibilidad).  
- El repo prioriza SL: correcto como default.

---

## 2. Práctica

1. Decidir en el close de M15 (checklist listo).  
2. Orden market en el open de la siguiente M15 (o limit en zona con reglas de fill).  
3. SL/TP en el servidor (broker / EA), no “wishful” mid-bar.  
4. Reportar resultados **siempre** con el pack de costos del símbolo.

---

## 3. Algoritmo (referencia)

```text
on bar i close:
  if signal(i):
    entry_bar = i + 1
    entry_price = open[entry_bar] +/- slip +/- spread/2
    risk = |entry - sl|
    for j = entry_bar .. entry_bar + max_hold:
      apply gap rules on open[j]
      check SL/TP with pessimistic path
      subtract commission on exit
```

---

## 4. Código SMC-SYSTEMS

| Pieza | Ruta | Estado |
|-------|------|--------|
| Entry = close señal | `ict_backtest/engine.py`, `sequence.py` | ⚠️ optimista |
| Sim desde `idx+1` | `simulate_trade` | ✅ no reusa barra señal para path |
| Cost opcional | `simulate_trade(..., cost=)` | ⚠️ no default en todas las corridas |
| Legacy fill | `legacy/backtest/engine.py` | ⚠️ close, sin cost pack |

Gate documental: [METRICS_CANON §1](../../METRICS_CANON.md) — costos cableados, no siempre activos.

---

## 5. Huecos abiertos

| ID | Hueco | Prioridad |
|----|-------|-----------|
| G2 | Default `fill_mode=next_open` | Alta |
| G3 | Cost pack por símbolo (EUR vs XAU) | Alta |
| G4 | Gaps de sesión / weekend | Media |
| G5 | Swap si hold multi-día | Baja (si max_hold corto) |

---

## En resumen

**Close-to-close sin fricción** es un laboratorio.  
**Next-open + costos + path pesimista** es lo que un fondo o prop te exige antes de creerte el PF.
