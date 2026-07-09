# SDD — App Observador SMC-SYSTEMS (carrocería real, sin bot)

**Fecha:** 2026-07-09
**Autor:** Hermes (Ruben pidió app nueva 100% funcional, no mock)
**Estado:** PROPUESTA — requiere visto bueno de Ruben antes de codear.

---

## 0. Contexto y alcance

Ruben usa hoy un **observador** (loop + semáforo + alertas + vigilante), NO un bot.
El `desktop/` actual es la "carrocería del piloto automático" (bot): muestra RSI/Stoch,
Positions, Trade Log y botones START/STOP/EMERGENCY del bot. Para el observador NO
tiene sentido. Se elimina `desktop/` y se construye UNA APP NUEVA del observador.

**Reglas duras de Ruben:**
- 100% funcional, SIN mock ni humo. Consume datos reales (MT5 demo + scripts reales).
- App en forma de programa (ventana), no PNG suelto.
- Caja negra para análisis de errores (black-box logging).
- Retención de datos: 3 meses (90 días), luego borrado automático.

---

## 1. Investigación previa (internet, 2026-07-09)

- **UI desktop Python + trading:** PySide6 (Qt) es el estándar; embeber matplotlib en
  PySide6 vía `FigureCanvasQTAgg` es el patrón documentado y robusto
  (pythonguis.com/tutorials/pyside6-plotting-matplotlib). El repo YA tiene PySide6
  instalado y `desktop/chart_widget.py` como referencia reutilizable.
- **Black-box logging:** logging estructurado JSON + rotación. Stdlib
  `logging.TimedRotatingFileHandler` cubre retención por tiempo (uptimerobot/dash0).
  Loguru es alternativa pero requiere dependencia nueva → se usa stdlib para no
  instalar nada sin autorización.
- **Rotación + retención 90 días:** `TimedRotatingFileHandler(when="midnight",
  backupCount=90)` + un `cleanup_old()` que borra archivos >90 días. Esto cumple
  "guarda 3 meses, después borra".

---

## 2. Arquitectura de la app

```
app_observador/                      (nueva carpeta, reemplaza desktop/)
├── main.py                         # entrypoint: arranca QApplication + MainWindow
├── ui/
│   ├── main_window.py              # QMainWindow, layout de paneles (reusa patrón existente)
│   ├── semaforo_widget.py         # semáforo VERDE/AMARILLO/ROJO grande + motivo
│   ├── mapa_widget.py             # embebe matplotlib: carga EURUSD_D1/H4/M15.png O genera al vuelo
│   ├── sesgo_widget.py            # sesgo del día + alineación Wyckoff D1/H4/M15
│   ├── noticias_widget.py         # noticias rojas del día (news_report)
│   └── estado_widget.py           # loop ON/OFF, vigilante ON/OFF, cuenta MT5, equity
├── core/
│   ├── engine.py                  # orquesta: corre ciclo de análisis real (reusa scripts)
│   ├── blackbox.py                # logger estructurado JSON + rotación + cleanup 90d
│   └── data_retention.py          # borra black-box y cache >90 días
└── config.py                      # rutas, symbol, TFs, umbrales
```

**NO se duplica lógica:** la app LLAMA tus scripts existentes como funciones:
- `rutina_eurusd.analyze_timeframe()` + `build_verdict()` → sesgo + veredicto
- `semaforo_fundednext.evaluate()` → color del semáforo
- `news_report.load_events()` → noticias rojas
- `fase_wyckoff_m15.fase_actual()` → fase Wyckoff M15 (ya en rutina)
- `mapa_precio.save_tf_png()` → genera/actualiza los PNG de los mapas
- `update_mt5_data.main()` (o su lógica) → datos frescos
- `vigilante_riesgo` → se consulta su estado (PID/equity) para el panel de estado

---

## 3. La ventana (lo que Ruben ve)

Layout de una sola pantalla, legible, sin pestañas de bot:

```
┌──────────────────────────────────────────────────────────────┐
│  SMC OBSERVADOR — EURUSD        [loop ● ON] [vigilante ● ON]  │
├───────────────────────┬──────────────────────────────────────┤
│  SEMÁFORO             │  SESGO DEL DÍA + ALINEACIÓN WYCKOFF    │
│   🟡 AMARILLO         │  D1: MARKDOWN  H4: INDEF  M15: MARKUP │
│   (motivo: noticia..) │  → EN CONFLICTO                        │
├───────────────────────┴──────────────────────────────────────┤
│  MAPA ICT (D1 | H4 | M15)  — matplotlib embebido, real        │
│  [ Order Blocks / FVG / Liquidez / Killzones pintados ]       │
├──────────────────────────────────────────────────────────────┤
│  NOTICIAS ROJAS HOY:  USD CPI 08:30 (alta) — NO OPERAR        │
│  CUENTA MT5: demo 10011586708  Equity $4,978.56  Flotante -0.3%│
└──────────────────────────────────────────────────────────────┘
```

- Refresco: timer cada 5 min (igual que el loop) o al hacer clic "Actualizar".
- Sin botones de operar. Solo "Actualizar ahora" y "Abrir mapa grande".

---

## 4. Caja negra (black-box) — análisis de errores

`core/blackbox.py`:
- Logger stdlib con `TimedRotatingFileHandler` → `data/blackbox/app_YYYY-MM-DD.log`
- Formato **JSON estructurado**: `{ts, level, module, event, symbol, tf, data, error}`.
- Niveles: INFO (ciclo OK), WARNING (MT5 cache usada), ERROR (excepción con traceback).
- Cada evento del ciclo se registra: qué corrió, qué devolvió, cuánto tardó, si falló.
- `data_retention.py`: al arrancar, borra logs/cache con mtime > 90 días.
- `backupCount=90` en el handler como red de seguridad.

Esto permite a Ruben (o a mí) abrir el log y ver QUÉ pasó en cualquier ciclo de los
últimos 3 meses, y por qué el semáforo salió como salió.

---

## 5. Retención de datos (3 meses)

- `data/blackbox/` → logs JSON, rotación diaria, cleanup >90 días.
- `data/raw/` (parquet MT5) → ya está en .gitignore; la app NO lo toca (es del loop).
- `docs/diario/` → historial de fichas; la app puede limpiar >90 días también.
- Script `data_retention.py` corre al arranque y vía timer semanal.

---

## 6. Eliminación de lo viejo

Paso 0 de la implementación: `git rm -r desktop/` y sus refs en `run_desktop.py`,
`README.md` (sección Desktop UI), `DESKTOP_UI.md`. Se reemplaza por `app_observador/`.
El bot heredado (signals/agents/ml/backtest) queda en el repo pero FUERA de la app
(etiquetado como no activo, como acordamos en la auditoría).

---

## 7. Verificación (sin humo)

- `py_compile` de todos los módulos nuevos.
- La app arranca con `python app_observador/main.py` y muestra datos REALES
  (semáforo AMARILLO/VERDE/ROJO coherente con `semaforo_fundednext`, mapa con
  velas reales de `data/raw/EURUSD_*.parquet`).
- Black-box escribe un JSON válido por ciclo; `data_retention.py` borra un archivo
  de prueba >90 días en un test controlado.
- NO se admite UI que muestre "---" o placeholders: todo viene de datos reales o
  dice explícitamente "sin datos MT5" si la terminal no está conectada.

---

## 8. Riesgos / dependencias

- PySide6 ya instalado (del desktop viejo). Si no está en tu máquina, requiere
  `pip install PySide6` (1 dependencia, autorizar).
- matplotlib ya instalado (3.11.0).
- NO se agregan otras deps sin tu autorización.

---

## 9. Plan de implementación (una variable a la vez)

1. `git rm -r desktop/` + limpiar refs.
2. `app_observador/config.py` + `core/blackbox.py` (base, testeable solo).
3. `core/data_retention.py` (cleanup 90d).
4. `core/engine.py` (orquesta scripts reales, escribe black-box).
5. `ui/` widgets (semaforo, mapa, sesgo, noticias, estado).
6. `ui/main_window.py` + `main.py` (ensambla).
7. Verificación end-to-end con datos reales.
8. Commit + push.

---

*SDD preparado por Hermes tras investigación internet (PySide6+matplotlib embed,
stdlib JSON logging + TimedRotating 90d) y auditoría del proyecto (sin duplicar
scripts existentes). Espera visto bueno de Ruben para codear.*
