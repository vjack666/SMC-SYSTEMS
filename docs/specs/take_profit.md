# SDD — Plan de Take Profit (TP) en la ficha EURUSD

Convierte el veredicto (bias + zona OTE + invalidación + target) en un plan
de trade con entrada / SL / TP concretos y valida el R:R mínimo 1:2.
Reusa lo ya calculado en rutina_eurusd.py — NO agrega detectores nuevos.

---

## 1. REQUIREMENTS

**R1:** THE SYSTEM SHALL, cuando el bias sea LONG o SHORT, proponer:
- Entrada = borde de la zona OTE M15 (mid de ote_long / ote_short).
- SL = invalidación (ya calculada: zone_low para LONG, zone_high para SHORT).
- TP = target por estructura (ya calculado: zone_high para LONG, zone_low SHORT).

**R2:** THE SYSTEM SHALL calcular R:R = distancia(TP-entrada) / distancia(entrada-SL).

**R3:** IF R:R < 2.0 THE SYSTEM SHALL marcar el setup como "DESCARTAR (R:R < 1:2)".
IF R:R >= 2.0 marcar "VALIDO".

**R4:** THE SYSTEM SHALL mostrar entrada/SL/TP/RR en pips y precio en la ficha,
bajo el VEREDICTO.

**R5:** IF bias NEUTRAL THE SYSTEM SHALL no proponer plan (no hay trade).

**R6:** THE SYSTEM SHALL respetar que es un MAPA, no una orden (nota existente).

---

## 2. DESIGN

### Reuso (no duplicar)
- `build_verdict()` ya devuelve bias, invalidation (SL), target (TP), ote_long/short.
- Solo agrego `compute_trade_plan(verdict, m15)` que arma el plan y el R:R.
- Se renderiza en `render()` bajo el veredicto.

### Pips
- EURUSD: 1 pip = 0.0001. pips = abs(a-b) / 0.0001.

### Fórmula R:R
- entry = mid(OTE del lado del bias)
- risk = abs(entry - SL); reward = abs(TP - entry)
- rr = reward / risk (si risk > 0)

### Archivos
- Modifica: `scripts/rutina_eurusd.py` (+~30 líneas: compute_trade_plan + render).

---

## 3. TASKS

- [ ] T1: `compute_trade_plan(verdict, m15)` → entry, sl, tp, rr, valido.
- [ ] T2: Regla R:R >= 2.0 = VALIDO, si no DESCARTAR.
- [ ] T3: Render en la ficha (precio + pips + R:R + veredicto valido/descartar).
- [ ] T4: NEUTRAL → sin plan.
- [ ] T5: Verificar con datos reales (run rutina).
- [ ] T6: Documentar en RUTINA_EURUSD.md.

---

## 4. FUERA DE ALCANCE
- TP por ATR o R:R fijo puro (se eligió estructura + validación R:R).
- Abrir órdenes: la ficha solo sugiere; VOS operás en MT5.
- TP parciales / trailing (posible Fase 2).
