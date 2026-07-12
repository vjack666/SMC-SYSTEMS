# 11 — Sweep + OTE: Manual vs Automático (y nuestro sistema híbrido)

> Investigación de campo (internet, 2026-07-12) sobre cómo usan el sweep de
> liquidez + OTE los **traders manuales** vs los **sistemas automáticos (EA/MQL5)**,
> y cómo se compara con SMC-SYSTEMS. Contexto: Ruben opera MANUAL hoy, pero la
> dirección del proyecto es **100% AUTOMÁTICO a futuro**. Por eso el sistema se
> diseña *automation-ready* (señal lista para ejecutar, no solo una alarma).

---

## 1. Trader MANUAL (fuentes: dailypriceaction / arongroups)

Justin Bennett (trader desde 2002) describe su rutina real de reversión por sweep:

1. **Contexto HTF primero.** Arranca en H1 solo para ver tendencia: "si operás
   M15 sin saber qué hace H1/H4, operás a ciegas". HTF = dirección, LTF = entrada.
2. **OTE 62-79%.** Del swing externo alto→bajo traza Fibonacci y se enfoca en la
   zona 62-79% (discount para compras, premium para ventas). Si el precio NO está
   en OTE, "no me interesa la reversión".
3. **Sweep + ESPERAR.** Ve el sweep (rompe swing, lame stops) y ESPERA confirmación
   de vela; no entra contra el sweep.
4. **Drop a M15 para la entrada.** Recién ahí busca el entry conconfirmación de
   cierre.
5. **Gestión a ojo.** SL atrás del sweep, TP en la liquidez opuesta, va ajustando
   según lee el mercado.

**Fortalezas manual:** control total, adapta a lo inesperado por intuición/experiencia.
**Debilidades manual:** emoción (miedo a holdear pérdida, codicia a cerrar ganancia
prematura), limitado por horas frente a pantalla, se pierde lo que no ve.

---

## 2. Sistema AUTOMÁTICO / EA (fuente: MQL5 "ICT EA", Silver Bullet, $2000)

EA profesional para NASDAQ/Gold. Hace la MISMA secuencia que el manual, pero
programada paso a paso ("only acts when every condition lines up"):

1. **H1 Bias** — lee dirección H1 (EMA + precio); solo longs si H1 bullish.
2. **Liquidity Sweep** — espera que raide un nivel: swing reciente, PDH/PDL, o
   high/low de Asia. "Ahí descansa la liquidez."
3. **MSS** — requiere un cierre que rompa estructura corta en dirección opuesta.
   "Confirmación en close, no adivinar."
4. **Displacement** — la vela que rompe debe ser impulsiva (cuerpo > N×ATR).
5. **FVG Entry** — espera retroceso al FVG dejado por el displacement (entry mejor,
   SL más ajustado).
6. **Liquidity Target** — TP en la liquidez opuesta (PDH/PDL, EQH/EQL). Si no hay,
   cae a RR configurable.
7. **Gestión automática** — tamaño por % cuenta, SL estructural + buffer ATR, cierre
   parcial 50% en 1R, breakeven, máx barras en trade, 1 trade a la vez.

**Fortalezas auto:** 24/7, sin emoción, backtesting, gestión idéntica siempre,
múltiples pares a la vez.
**Debilidades auto:** un bug ejecuta un mal trade solo; no adapta a lo inesperado;
requiere validación walk-forward rigurosa para no sobreajustar.

---

## 3. Pros/Contras (fuente: avatrade)

- **Automático:** cobertura 24/7, sin emoción, backtesting, gestión consistente.
- **Manual:** control y adaptación por intuición; limitado por tiempo y emoción.
- **No son excluyentes:** el enfoque *híbrido* (automatizar la detección + retener
  control de ejecución en casos borrosos) es lo recomendado por la fuente.

---

## 4. Comparación con SMC-SYSTEMS (lo que YA tenemos)

Nuestro sistema es **HÍBRIDO** y su "cerebro" es casi idéntico al EA profesional:

| Paso ICT | EA MQL5 | SMC-SYSTEMS |
|---|---|---|
| H1/H4 Bias | H1 EMA + precio | `macro_direction` (merge D1/H4) |
| Liquidity Sweep | raid a swing/PDH/PDL/Asia | `filter_sweep` (66% activo en M15) |
| MSS | cierre rompe estructura | CHOCH/BOS por **cuerpo** (sin look-ahead) |
| Displacement | cuerpo > N×ATR | `detect_displacement` |
| FVG Entry | retroceso al FVG | `filter_ob_fvg` |
| Secuencia | sweep→MSS→displacement→FVG | `sequence.py`: SWEEP→DISPLACE→BOS/CHOCH→ENTRY |
| Confluencia | "espera que todo se alinee" | `confluence_score` (pesos rulebook) |
| Gestión | % cuenta, SL+ATR, 1R, BE | `risk/sizer.py` (tamaño), SL estructural |

**La diferencia hoy:** el EA EJECUTA el trade solo. Nosotros detectamos + alertamos
(`rutina_eurusd.py` → popup + sonido) y **vos ejecutás manualmente**. Eso nos da lo
mejor de ambos: disciplina algorítmica sin la emoción de decidir el setup, pero con
control de ejecución (y sin riesgo de que un bug abra un trade malo).

---

## 5. Qué falta para el futuro 100% AUTOMÁTICO

Para cerrar la brecha manual→auto (verificado en el repo el 2026-07-12):

1. **Ejecutor MT5 (NO existe).** No hay `OrderSend`/`trade.Buy`/`positions.Open`
   ni clase `Executor` en el repo (solo `risk/sizer.py` y `scripts/first_live_test.py`).
   Hay que construir un módulo que reciba `ScalpingSignal` (entry/SL/TP ya calculados)
   y lo envíe a MT5 vía `MetaTrader5` Python API. El `ScalpingSignal` YA trae
   `entry`/`stop_loss`/`take_profit` → es *automation-ready* por diseño.
2. **TP a liquidez opuesta (gap de calidad).** Hoy `build_scalping_signals`
   pone TP a **2×ATR fijo** (línea ~362). El EA pro apunta el TP a la liquidez
   opuesta (PDH/PDL, EQH/EQL). Nuestro TP es genérico; apuntar a liquidez real
   mejoraría el RR medido. Hallazgo a cerrar (item_D / mejora futura).
3. **Gestión automática.** El EA hace cierre parcial 50% en 1R + breakeven + máx
   barras. Hoy eso lo hacés vos manualmente. Hay que programarlo en el ejecutor.
4. **Walk-forward OOS antes de soltarlo.** Cualquier cambio de pesos/sweep/ote/TP
   se decide en train-fold y se evalúa SOLO en OOS (PurgedKFold). Criterio: no
   degradar WR/PF OOS.

---

## 6. Conclusión

El sweep + OTE es el mismo juego para manual y auto; la diferencia es quién aprieta
el botón. Nuestro "cerebro" ya juega como un EA de $2000. Para el futuro 100%
automático solo falta el **brazo ejecutor (MT5)** + afinar **TP a liquidez** +
**gestión automática**. Mientras tanto, el modo híbrido (alerta + ejecución tuya) es
exactamente lo que recomiendan las fuentes para no perder el control ni la disciplina.

---

## 7. Fuentes

- dailypriceaction.com — "How To Trade Liquidity Sweep Reversals (15-Minute Strategy)" (Bennett, 2026).
- arongroups.co — "Optimal Trade Entry Techniques for ICT Traders" (Cofnas, 2026).
- mql5.com/market/product/183690 — "ICT EA" (Silver Bullet, NASDAQ/Gold, 2026).
- avatrade.com — "Auto-Trading vs. Manual Trading" (2026).

> Nota: estas fuentes son públicas y complementan la biblioteca; no son ICT
> Mentorship de pago. Los detalles de código (tabla §4, gaps §5) son del repo real
> verificado el 2026-07-12.
