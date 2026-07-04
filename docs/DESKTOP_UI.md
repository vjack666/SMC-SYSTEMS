# Desktop UI — SMC Trading System

Interfaz gráfica completa construida con **PySide6** (Qt for Python) que conecta en tiempo real con MetaTrader 5 para monitoreo y operativa.

---

## Requisitos

- Python 3.11+
- PySide6 >= 6.6
- MetaTrader 5 terminal instalado y conectado a una cuenta (demo o real)

## Inicio rápido

```bash
python scripts/run_desktop.py
```

## Build standalone (PyInstaller)

```bash
pip install pyinstaller
pyinstaller smc_trading.spec
```

El ejecutable se genera en `dist/SMC_Trading.exe` (~480 MB). Requiere MT5 terminal en la máquina destino.

---

## Arquitectura

```
MainWindow (QMainWindow)
  ├── QTabWidget (6 tabs)
  │   ├── DashboardPanel
  │   ├── ChartWidget
  │   ├── PositionPanel
  │   ├── TradeLogPanel
  │   ├── LogPanel
  │   └── ControlPanel
  ├── QSystemTrayIcon
  └── MenuBar (File → Settings, Quit)

TradingWorker (QObject, vive en QThread)
  ├── signals: TradingWorkerSignals (10 señales)
  └── _run_loop: loop 5s por símbolo
       ├── _emit_tick(symbol)
       ├── runner._process_symbol(symbol)
       ├── _emit_positions()
       ├── _emit_governor()
       └── _emit_chart_data()
```

El `TradingWorker` corre en un `QThread` separado para no bloquear la UI. Se comunica con los paneles vía 10 señales Qt.

## Paneles

### Dashboard
- Información de cuenta (balance, equity, margin free, leverage)
- Grilla de precios en vivo con RSI y Stoch %K para cada símbolo
- Estado del Risk Governor con código de colores:
  - **NORMAL** → verde
  - **CAUTION** → amarillo
  - **DEFENSIVE** → naranja
  - **LOCKDOWN** → rojo

### Chart
- Velas japonesas (QCandlestickSeries)
- EMA20 (azul) y EMA50 (naranja)
- Stochastic %K (púrpura) y %D (amarillo punteado) — eje Y derecho
- Marcadores de señal LONG (verde) / SHORT (rojo)
- Zonas de **Order Blocks**:
  - OB alcista: rectángulo verde semitransparente
  - OB bajista: rectángulo rojo semitransparente
- Zonas de **Fair Value Gaps**:
  - FVG alcista: azul semitransparente
  - FVG bajista: naranja semitransparente
  - FVG rellenados: más transparentes (alpha 20 vs 50)
- Selector de símbolo (8 pares + XAUUSD)
- Últimas 100 velas visibles

### Positions
- Tabla de posiciones abiertas con columnas: símbolo, lado, volumen, entrada, SL, TP, P&L, pips, confianza
- P&L coloreado (verde/rojo)
- Resumen con total P&L y pips

### Trade Log
- Historial de trades cerrados
- Filtro por símbolo (QSortFilterProxyModel)
- Búsqueda por texto en cualquier columna

### Log
- Log en tiempo real con timestamps UTC
- Auto-scroll al final
- Límite de 10.000 líneas (descarta las más viejas)
- Botón Clear

### Control
- Botones: **Start** (verde), **Stop** (amarillo), **Emergency Stop** (rojo)
- Risk %: 0.1%–10% (step 0.1)
- Min Confidence: 0.10–0.99 (step 0.05)
- Symbols input: lista separada por comas
- Modo actual (PAPER/LIVE)
- Estado del governor

## Señales del Worker

| Señal | Tipo | Emitida cuando... |
|-------|------|-------------------|
| `log_message` | `str` | Mensaje de log |
| `positions_updated` | `dict` | Posiciones actualizadas |
| `trades_updated` | `list` | Trade log actualizado |
| `account_updated` | `dict` | Info de cuenta disponible |
| `governor_updated` | `str, int, float` | Estado del governor cambia |
| `tick_updated` | `str, float, float` | Nuevo tick (symbol, bid, ask) |
| `status_changed` | `str` | RUNNING / STOPPED |
| `signal_detected` | `str, int, float` | Nueva señal detectada |
| `error_occurred` | `str` | Error en el loop |
| `chart_data_updated` | `pd.DataFrame` | Nuevos datos para el chart |

## Atajos y comportamientos

- **Cerrar ventana**: minimiza a system tray (no cierra la app)
- **Double click en tray icon**: muestra/oculta la ventana
- **Menú File → Settings**: diálogo de configuración con 4 tabs (General, Risk, Pipeline, Data)
- **Emergency Stop**: cierra todas las posiciones LIVE y detiene el worker

## Temas

La UI usa el theme **Fusion** con una palette oscura personalizada. No hay soporte multi-tema por ahora.
