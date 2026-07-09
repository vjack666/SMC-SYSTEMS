# SDD — Vigilante de Riesgo (kill-switch de pérdida flotante)

Guardián que vigila el balance y el equity (balance flotante) de la cuenta
MT5 EN VIVO y cierra TODAS las posiciones abiertas si la pérdida diaria
flotante toca el límite. Solo CIERRA, nunca abre (respeta "sin bot").

---

## 1. REQUIREMENTS

**R1:** THE SYSTEM SHALL leer el balance de la cuenta MT5 al iniciar el día
(`mt5.account_info().balance`) como referencia de apertura.

**R2:** EVERY `CHECK_SECONDS` (15s) THE SYSTEM SHALL leer el equity flotante
(`mt5.account_info().equity`) = balance + PnL de posiciones abiertas.

**R3:** IF la pérdida diaria flotante >= `SOFT_PCT` (2%) del balance de
apertura, THE SYSTEM SHALL cerrar TODAS las posiciones abiertas
(`mt5.positions_get` + `close_position` de risk/sizer.py) y alertar con
popup rojo.

**R4:** IF la pérdida >= `HARD_PCT` (4% = DLL FundedNext) THE SYSTEM SHALL
también cerrar todo (segundo freno redundante, por si el suave falla).

**R5:** THE SYSTEM SHALL alertar por popup + sonido + log en `logs/vigilante.log`
cada cierre, con el % de pérdida alcanzado.

**R6:** THE SYSTEM SHALL poder desactivarse con `--no-close` (solo avisa, no
cierra) para pruebas.

**R7:** THE SYSTEM SHALL respetar "sin bot": NUNCA abre órdenes, solo cierra.

**R8:** THE SYSTEM SHALL correr como proceso aparte (segundo plano), encendido
con Windows junto al loop (start_hermes_session.ps1).

---

## 2. DESIGN

### Reuso (no duplicar)
- `risk/sizer.py`: `close_position(ticket, symbol, volume, position_type)` —
  cierre real de MT5 ya implementado y verificado.
- `mt5.account_info()` / `mt5.positions_get()` — conexión MT5 ya usada en el repo.
- `scripts/alertas.py`: `alertar()` para popup + sonido.

### Archivos
- Nuevo: `scripts/vigilante_riesgo.py` (~90 líneas)
- Modifica: `start_hermes_session.ps1` (enciende el vigilante)
- Salida: `logs/vigilante.log`

### Parámetros (configurables arriba del script)
- SOFT_PCT = 2.0   # freno suave: cierra todo al 2% pérdida diaria flotante
- HARD_PCT = 4.0   # freno duro: DLL FundedNext (redundante)
- CHECK_SECONDS = 15

### Lógica
1. mt5.initialize() (reusa patrón de scripts/check_mt5.py)
2. balance0 = account_info().balance  (referencia de apertura)
3. bucle:
   - equity = account_info().equity
   - loss_pct = (balance0 - equity) / balance0 * 100
   - si loss_pct >= SOFT_PCT: cerrar_todo(); alertar; (continúa vigilando)
   - si loss_pct >= HARD_PCT: cerrar_todo(); alertar
   - sleep(CHECK_SECONDS)

---

## 3. TASKS

- [ ] T1: Crear `scripts/vigilante_riesgo.py` (init MT5, loop 15s).
- [ ] T2: Leer balance0 al inicio; equity cada ciclo.
- [ ] T3: Al >=2% pérdida: cerrar TODAS las posiciones (close_position).
- [ ] T4: Al >=4% (DLL): cerrar todo (segundo freno).
- [ ] T5: Alertar popup+sonido+log en cada cierre.
- [ ] T6: Flag `--no-close` para pruebas (solo avisa).
- [ ] T7: Enchufar en `start_hermes_session.ps1` (arranca con Windows).
- [ ] T8: Documentar en RUTINA_EURUSD.md sección "Vigilante de riesgo".

---

## 4. FUERA DE ALCANCE
- Abrir órdenes: el vigilante SOLO CIERRA.
- Calculadora de lotes: ya existe en `risk/sizer.py` (compute_lot), se deja.
