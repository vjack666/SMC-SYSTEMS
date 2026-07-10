# Rutina EURUSD — Manual de uso diario (SMC-SYSTEMS)

Rutina de análisis top-down para EURUSD, orientada a scalping/inter-intradía
en cuentas FundedNext. Usa los detectores deterministas de SMC-SYSTEMS
(BOS, OB, FVG, zonas, tendencia, CHOCH) sobre datos REALES del MT5.
No estima a ojo: todo sale del código.

---

## 1. Qué hace

Lee EURUSD en D1 / H4 / M15, corre los detectores y arma una ficha con:

- **Contexto grande** (D1, H4): la "marea" — bias, estructura, zonas.
- **Ejecución** (M15): el timing — OB, FVG, BOS, CHOCH, liquidez.
- **Veredicto operativo**: sesgo del día (LONG / SHORT / NEUTRAL) con votos
  y razones, zona de interés, invalidación y objetivo.

La ficha es el MAPA, no una orden de entrada. Confirmás en tu ejecución.

---

## 2. Arranque automático (lo primero cada día)

Al iniciar Hermes se ejecuta `start_hermes_session.ps1`, que:
1. Abre el terminal MT5 de FundedNext (si no está corriendo).
2. Actualiza `data/raw/` con datos EN VIVO (EURUSD D1/H4/M15).
3. Lanza Hermes.

Si el terminal no está logueado, la actualización avisa con ADVERTENCIA
pero no bloquea. Logueá tu cuenta en el terminal FundedNext primero.

> Hoy (fase de prueba) se usa la cuenta demo MetaQuotes. Cuando actives la
> cuenta real de FundedNext, solo logueala en ese terminal: el script la toma
> solo, no hay que cambiar código.

---

## 3. Uso manual

Desde la carpeta del proyecto (`C:\Users\v_jac\Desktop\SMC-SYSTEMS`):

```bat
C:\Python314\python.exe scripts\rutina_eurusd.py
```

Ver la ficha y guardarla al diario:

```bat
C:\Python314\python.exe scripts\rutina_eurusd.py --save
```

El diario se guarda en `docs/diario/EURUSD_<fecha>.md`.

> Usá SIEMPRE `C:\Python314\python.exe` (tiene MetaTrader5 real). El venv
> `smc_probe` solo tiene un stub de MT5 y sirve para backtests offline.

### Informe combinado (técnico + fundamental)

Para un análisis completo con noticias, usá el informe:

```bat
C:\Python314\python.exe scripts\informe_eurusd.py --save
```

Une la ficha técnica con el contexto de noticias (RSS ForexFactory en vivo)
y dice si ambos empujan la MISMA dirección o se CONTRADICEN. Guarda en
`docs/diario/INFORME_EURUSD_<fecha>.md`.

---

## 4. Cómo leer la ficha

```
[D1]  Bias/Tendencia : BAJISTA  | ultimo swing: LL
      Zona precio    : DISCOUNT  (rango 1.13240 - 1.16222)
      OB activo      : bullish  [1.13616 - 1.14232]
```

- **Bias/Tendencia**: BULLISH / BEARISH / RANGING. El "viento" de esa temporalidad.
- **Swing**: HH/HL (máximo/mínimo más alto) o LH/LL (más bajo) — la estructura.
- **Zona precio**: PREMIUM (caro, buscar ventas) o DISCOUNT (barato, buscar compras).
  El rango es el canal calculado por el detector.
- **OB activo**: Order Block. Los corchetes son los BORDES EXACTOS
  [ob_bottom - ob_top]. Es tu zona de entrada potencial.
- **FVG**: Fair Value Gap. `bullish_unfilled` / `bearish_unfilled` = hueco sin
  rellenar (zona de imán). `none` = no hay.
- **BOS**: Break of Structure. dir=1 alcista, dir=-1 bajista, dir=0 neutro.
- **CHOCH**: Change of Character (cambio de carácter de la estructura).
- **Liquidez**: barrido_arriba / barrido_abajo = caza de stops reciente.

### Veredicto

```
SESGO DEL DIA  : NEUTRAL (esperar)   (votos L:0 / S:1)
```

- LONG / SHORT: hay confluencia a favor.
- NEUTRAL (esperar): temporalidades en conflicto. NO inventa señal — esperá.
- Votos L:S = cuántas temporalidades/factores empujan cada lado.

---

## 5. Regla de oro para FundedNext

La rutina te da el mapa; VOS gestionás el riesgo. Recordá las reglas del
Stellar Lite $5K (en `tools/fundednext_compliance.py`):

- Pérdida diaria máxima (DLL): 4%
- Pérdida total máxima (MLL): 8%
- Riesgo por operación: hasta 3% (recomendado 0.5–1% para sobrevivir el DLL)
- Drawdown estático (piso sobre el balance inicial)

Nunca operes un setup cuyo riesgo proyectado supere tu DLL del día.

---

## 6. Semáforo FundedNext (la regla de oro automática)

Después de leer la ficha, corré el semáforo. Cruza tu sesgo técnico con la
presencia de noticias rojas y te da un veredicto de disciplina:

```bat
C:\Python314\python.exe scripts\semaforo_fundednext.py --save
```

| Color | Significado | Qué hacés |
|---|---|---|
| 🟢 VERDE | Estructura clara, sin noticia roja en ventana | Operá con tu plan habitual |
| 🟡 AMARILLO | Estructura clara PERO hay noticia roja, o sesgo NEUTRAL | Solo con setup claro y size reducido (0.5%) |
| 🔴 ROJO | Sesgo NEUTRAL + noticia roja (o sin confirmación) | NO operes hoy |

El semáforo SIEMPRE recuerda los límites del challenge:
DLL 4% | MLL 8% | riesgo ≤ 3% por trade.

> Las noticias vienen del RSS oficial de ForexFactory
> (`nfs.faireconomy.media/ff_calendar_thisweek.xml`), la MISMA fuente que
> FundedNext muestra en fundednext.com/economic-calendar. Por eso no duplicamos:
> una sola fuente, la original. El semáforo marca "noticia roja" = evento
> High de USD/EUR en tu ventana 8–11 AM Ecuador (13–17 UTC).

---

## 7. Archivos

| Archivo | Rol |
|---|---|
| `scripts/rutina_eurusd.py` | La rutina (ficha EURUSD) |
| `scripts/informe_eurusd.py` | Informe combinado técnico + noticias |
| `scripts/news_report.py` | Noticias EUR/USD (RSS ForexFactory en vivo + cache) |
| `scripts/semaforo_fundednext.py` | Semáforo VERDE/AMARILLO/ROJO (regla de oro) |
| `scripts/update_mt5_data.py` | Actualiza `data/raw` desde MT5 FundedNext |
| `scripts/start_hermes_session.bat` | Abre MT5 + actualiza data |
| `start_hermes_session.ps1` | Arranque Hermes (corre el .bat y lanza Hermes) |
| `data/raw/EURUSD_*.parquet` | Datos en vivo bajados del MT5 |
| `data/news_cache.json` | Cache del RSS de noticias (por día) |
| `docs/diario/` | Tu diario (`--save`) y semáforo |
| `tools/fundednext_compliance.py` | Reglas de cumplimiento FundedNext |

---

## 10. Arranque automático (todo operativo al prender la compu)

El acceso directo de Startup (`Hermes.lnk`, en
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`) apunta a
`start_hermes_session.ps1` y se ejecuta **oculto** al iniciar sesión
(política `-ExecutionPolicy Bypass -NoProfile`). El `.ps1` hace 4 pasos:

1. Abre el terminal MT5 FundedNext + actualiza `data/raw` (datos en vivo).
2. Enciende el **loop de análisis** en segundo plano (SIEMPRE ACTIVO, sin bot, con alertas).
3. Enciende el **vigilante de riesgo** (kill-switch, SOLO CIERRA al 2%/4%).
4. Enciende la **app del observador** (PySide6) + reporte de salud; luego lanza Hermes.

**Protección anti-duplicados:** `loop_analisis.py`, `vigilante_riesgo.py` y
`run_app.py` usan un mutex de Windows (`scripts/_single_instance.py`). Si por
cualquier razón el arranque se dispara dos veces (doble login, reinicio de
sesión), la 2ª instancia se auto-cierra en vez de duplicar procesos.

Resultado: apenas iniciás sesión en Windows ya estás operativo. El loop corre
cada 5 min las 24h (ventana trading marcada 07:00-20:00 Ecuador) y te avisa con
popup+sonido cuando hay que mirar. No hace falta correr nada a mano.

> Si el loop no aparece: revisá `logs/loop_analisis.out`.
> Para pararlo: desde el Administrador de tareas (proceso `pythonw.exe` que
> corrió `loop_analisis.py`) o pedime "para el loop".
> El acceso directo de escritorio `SMC SYSTEMS.lnk` es SOLO la app del
> observador (no arranca el sistema); el auto-arranque es solo vía `Hermes.lnk`.

---

## 9. Loop automático (observador, sin operar, SIEMPRE ACTIVO)

Para no correr los scripts a mano, tenés un loop que corre solo cada 5 min:

```bat
C:\Python314\python.exe scripts\loop_analisis.py
```

- **SIEMPRE ACTIVO**: corre cada 5 min las 24h (no duerme).
- **Fin de semana**: se APAGA el viernes a las 15:00 Ecuador y no corre sábado
  ni domingo. Reanuda solo al prender la compu el lunes (arranque con Windows).
- Ventana de trading marcada: **07:00-20:00 Ecuador** (el log dice DENTRO/FUERA).
- Cada ciclo: actualiza MT5, regenera ficha + informe + semáforo.
- Guarda traza en `docs/diario/loop_<fecha>.log`.
- **Nunca abre órdenes**: es un observador, VOS decidís si operás.
- Lo parás con **Ctrl+C** (salida limpia) o pedímelo a mí.

Otras opciones:

```bat
C:\Python314\python.exe scripts\loop_analisis.py --once       # 1 ciclo y sale
C:\Python314\python.exe scripts\loop_analisis.py --no-alert   # sin popups
```

> Si el terminal MT5 no está logueado, el loop avisa (ADVERTENCIA) y usa la
> última data cacheada — no se rompe. Logueá tu cuenta en el terminal primero.

> Fase 2 (futuro): paper híbrido / shadow mode — si no operás un setup, el
> loop lo sigue en papel y etiqueta el resultado para entrenar el ML sin
> riesgo. Ver `docs/specs/loop_analisis.md` sección 5.

---

## 11. Alertas locales (Windows)

El loop te avisa SOLO cuando hay algo que mirar. Popup de Windows + sonido.
Cero instalación, cero Telegram.

Dispara en:
- **VERDE**: semáforo verde (sesgo claro, sin roja) → "operá con tu plan".
- **NOTICIA ROJA**: evento High USD/EUR en ventana → "no operes" (regla FundedNext).
- **AMARILLO**: NO popup (solo queda en el log) para no molestar.

Registro en `logs/alertas.log`. Para probarlas:
`C:\Python314\python.exe scripts\alertas.py`

> Fuera de la ventana de trading solo alerta roja (las demás son ruido).
> Si no querés popups: `loop_analisis.py --no-alert`.

---

## 12. Plan de Take Profit (TP) en la ficha

Cuando el sesgo es LONG o SHORT, la ficha propone un plan de trade concreto:

- **Entrada**: punto medio de la zona OTE M15 (donde ICT busca entrar).
- **Stop Loss**: la invalidación (si el precio pasa, el sesgo se cae).
- **Take Profit**: la siguiente liquidez por estructura (próxima zona del rango).
- **Ratio R:R**: reward ÷ risk. Si es **1:2 o mejor → VÁLIDO**; si no → DESCARTAR.

Así solo operás cuando la estructura Y el riesgo:beneficio están a favor.
Si el TP por estructura no da 1:2, la ficha te dice "mejor esperar otro setup".

> Configurable arriba de `scripts/rutina_eurusd.py`: `RR_MIN=2.0` (bajalo a 1.5
> si querés setups más fáciles, subilo a 3.0 si querés más ambiciosos).
> Con sesgo NEUTRAL no hay plan (no hay trade).

---

## 13. Vigilante de riesgo (kill-switch, SOLO CIERRA)

Protección automática de tu cuenta FundedNext. Vigila el balance y el equity
(balance flotante = balance + PnL de operaciones abiertas) EN VIVO.

- Revisa cada **15 segundos** el equity de la cuenta MT5.
- Si la pérdida diaria flotante llega al **2%** del balance de apertura →
  **CIERRA TODAS las operaciones abiertas** y te avisa con popup rojo.
- Segundo freno redundante al **4%** (DLL de FundedNext): también cierra todo.
- **NUNCA abre órdenes**: solo cierra. Respeta "sin bot".

Arranca solo con Windows (Paso 3/4 de `start_hermes_session.ps1`). Log en
`logs/vigilante.log`. Para probarlo sin cerrar: `vigilante_riesgo.py --no-close`.

> Parámetros editables arriba del script: `SOFT_PCT=2.0`, `HARD_PCT=4.0`,
> `CHECK_SECONDS=15`. Podés bajar SOFT_PCT a 1.0 si querés más estricto.

> La calculadora de lotes (cuánto operar) YA existe en `risk/sizer.py`
> (`compute_lot`). El vigilante es el freno de pérdida, no el tamaño.

---
