# 02 — Modelo de tiempo y multi-timeframe

| Campo | Valor |
|-------|-------|
| **ID** | `13/02_MODELO_TIEMPO_Y_MTF` |
| **Versión** | 1.0 |
| **Fecha** | 2026-07-13 |
| **Estado** | Stable · Needs-code (HTF cerradas) |

---

## 1. Teoría

### Tres capas del reloj

| Capa | Definición en `t` |
|------|-------------------|
| **Pasado** | Toda información con `timestamp_cierre ≤ t` |
| **Presente** | La barra LTF que **acaba de cerrar** en `t` (OHLC completo de esa barra) |
| **Futuro** | Cualquier OHLC, label o path con información después de `t` |

En trading real **no existe** “ver la H4 de las 08:00 a las 09:15 con su high de las 11:40”. Eso es futuro disfrazado de contexto.

### Multi-TF: un reloj, N contextos

- **Driver (reloj):** LTF (en SMC-SYSTEMS suele ser M15; no M1 salvo que se documente).  
- **Contexto:** HTF (H4, D1) leídos en **asof**, pero solo barras **ya cerradas**.

Regla canónica (MT5, `time` = apertura de barra):

```text
htf_cerrada ⇔ htf.time_open + duration(htf) <= now
```

Equivale a usar `close_time` del HTF:

```text
última fila HTF con close_time <= now
```

### Event-driven vs vectorizado

| Estilo | Velocidad | Riesgo |
|--------|-----------|--------|
| **Event-driven** (estado + una barra) | Más lento | Menos look-ahead si el estado es honesto |
| **Vectorizado** (precomputar columnas) | Rápido | Un `shift` mal puesto destruye el estudio |

Precomputar **está permitido** si y solo si cada celda `(i, feature)` es causal.  
Precomputar **no** valida multi-TF: el merge HTF debe usar cierre, no apertura cruda.

---

## 2. Práctica del trader

1. Mirá D1 **cerrado** (o la última D1 completa).  
2. Mirá H4 **cerrada** para estructura.  
3. Esperá setup en M15 y **entrás** cuando la M15 cierra (o en el open de la siguiente).  
4. Nunca “adelantás” el bias D1 del final de la serie a todo el histórico (sesgo estático de fin de muestra).

---

## 3. Algoritmo

```python
def closed_row_at_time(htf_df, now, duration):
    """Solo barras HTF cuyo cierre ya ocurrió en `now`."""
    open_t = pd.to_datetime(htf_df["time"], utc=True)
    close_t = open_t + duration
    usable = htf_df.loc[close_t <= now]
    if usable.empty:
        return None  # sin HTF aún (warmup)
    return usable.iloc[-1]
```

**Prohibido como default de producción:**

```python
# MAL si time = open MT5
prior = times[times <= now]   # incluye H4 abierta
```

---

## 4. Código SMC-SYSTEMS

| Pieza | Ruta | Estado |
|-------|------|--------|
| Asof HTF ICT | `ict_backtest/_util.py` → `row_at_time` | 🔴 `times <= t` sin duration |
| Asof D1/H4 legacy | `trend_context.py` `merge_asof(..., backward)` | 🔴 mismo patrón |
| Loop LTF | `ict_backtest/sequence.py` | ✅ reloj LTF |
| Swings | `market_structure._swing_points` / `detectors/bos.py` | ✅ post-fix #1 |

---

## 5. Auditoría y huecos

- Cerrado: look-ahead de swings (libro `10_AUDITORIA_REFACCION/01_*`).  
- **Abierto:** HTF incompleta (crítico). Ver [06_GAP](06_GAP_SMC_SYSTEMS.md) G1.

---

## 6. Resultados

No inventar PF aquí. Tras el fix de HTF cerradas, re-medir y actualizar [METRICS_CANON](../../METRICS_CANON.md).

---

## En resumen

Multi-TF no se “ordena” corriendo tres backtests: se ordena **anclando el reloj al LTF** y leyendo HTF **solo cerradas**. Hoy el repo ancla el reloj bien y lee el HTF **demasiado pronto**.
