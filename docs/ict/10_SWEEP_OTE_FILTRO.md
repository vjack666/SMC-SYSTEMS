# 10 — Sweep + OTE como filtros de señal (Ítem D)

| Campo | Valor |
|-------|-------|
| **ID** | `10_SWEEP_OTE_FILTRO.md` |
| **Versión** | 2.0 (10/10) |
| **Fecha** | 2026-07-12 |
| **Estándar** | ADR-021 |
| **Estado** | Stable (docs) · Needs-code (OTE) |
| **Métricas** | [METRICS_CANON](../METRICS_CANON.md) §6 |
| **Relacionados** | `05_LIQUIDEZ`, `03_FVG`, `04_ORDER_BLOCKS` |

---

## 0. Contrato operativo

| # | Condición | Obligatorio |
|---|-----------|:-----------:|
| 1 | Sweep = ruptura de swing + cierre adentro (misma def. que libro 05) | Sí |
| 2 | `recent_liquidity_sweep` en ventana `sweep_lookback` (default 8) | Sí (si filtro ON) |
| 3 | OTE = precio en zona 62–79% del swing (discount long / premium short) **si el filtro OTE está activo** | Condicional |
| 4 | Pesos en confluencia documentados y medidos | Sí |
| 5 | Si OTE prevalece &lt;5% en el TF, peso OTE se trata como **no-op** hasta recalibrar | Sí (honestidad) |

---

## 1. Teoría

- **Sweep:** manipulación de liquidez antes de reversión/continuación de calidad.  
- **OTE (Optimal Trade Entry):** retroceso 62–79% del rango del impulso (Fibonacci institucional simplificado).  
- Son **filtros de calidad**, no triggers únicos.

---

## 2. Práctica

1. No entrar reversión sin sweep (regla dura de muchos operadores).  
2. Preferir entradas en OTE/discount-premium.  
3. Si el mercado nunca entra en banda OTE del detector → el filtro no aporta.

---

## 3. Algoritmo

```
filter_sweep = recent_sweep if enable_sweep_filter else True
filter_ote   = in_ote_zone    if enable_ote_filter else True
score += filter_sweep * w_sweep + filter_ote * w_ote
```

Default documentado: `w_sweep=2.0`, `w_ote=1.0`.

---

## 4. Código SMC-SYSTEMS

| Pieza | Ruta | Rol |
|-------|------|-----|
| Pipeline | `signals/pipeline.py` | Ítem D fusionado (`ScalpingConfig`) |
| Zonas | `compute_zones` / premium-discount | OTE |
| Sweep | flags en contexto scalping | |

> `docs/proposals/item_D.md` puede decir “no aplicado”: **histórico**. El código ya fusiona Ítem D.

---

## 5. Auditoría y huecos

| Hallazgo | Estado |
|----------|--------|
| Sweep ~66% activo EURUSD M15 | Útil |
| OTE ~1% | 🔴 **no-op práctico** → R3: recalibrar bandas o peso 0 |
| WF del test OTE | 🔴 pendiente |

---

## 6. Resultados

[METRICS_CANON §6](../METRICS_CANON.md#6-ítem-d--sweep--ote-prevalencia-eurusd-m15).

---

## 7. Checklist de aplicación

- [ ] Decisión: fix OTE vs desactivar peso  
- [ ] Walk-forward del cambio  
- [ ] Actualizar METRICS_CANON  

---

## En resumen

Sweep está vivo y pesa; OTE en M15 actual casi no dispara. Un sistema 10/10 **no miente**: o se arregla OTE o se apaga el peso hasta nueva evidencia.
