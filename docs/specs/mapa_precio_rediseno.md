# SDD — Rediseño visual de mapa_precio.py (estilo ICT limpio, fondo claro)

## Objetivo (prompt de Claude, autorizado por Ruben)
Mejorar SOLO el dibujo de scripts/mapa_precio.py para que se vea limpio tipo
TradingView, igual en D1/H4/M15. Reusar detectores existentes; NO tocar lógica.

## Cambios (solo funciones de dibujo)
- `_candles`: verde bosque #1b5e3c / rojo burdeos #7a1f2b, alpha=1.0, mecha lw=1.0.
- `_zone_rect` -> `axhspan` (no rectángulo opaco), alpha 0.18, opcional borde --.
- `panel`: fondo #f5f5f5, grid punteado #e0e0e0; BSL/SSL como líneas -- (no rect);
  zona premium/discount como línea 50% punteada; killzones axvspan alpha 0.07.
- `save_tf_png`: título #2c3e50 bold; entry SL/TP con colores de velas; dpi=150.
- Capas zorder: grid 0, kz 1, zonas 2, liq 3, velas 4, trade/texto 5.

## Restricciones
- Solo matplotlib (ya instalado). Sin mplfinance.
- Firmas de _candles/_zone_rect/panel/save_tf_png se mantienen.
- No duplicar cálculo de detectores.

## Verificación
- py_compile + generar 3 PNG (D1/H4/M15) con datos reales.
- vision_analyze comparando con referencia de Claude (capturas/eurusd_h4_ict.png).
