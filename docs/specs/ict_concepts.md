# SDD — ICT Concepts (port de LuxAlgo a Python para el mapa de imágenes)

## Objetivo
Pintar en `mapa_precio.py` (imagen para Ruben, NO para el loop) los conceptos ICT que
LuxAlgo dibuja en TradingView, usando LOS MISMOS DATOS REALES de MT5 (.parquet).

## Qué YA existe en el repo (REUSAR, no duplicar)
- detectors/bos.py      -> BOS, swing points (MSS es BOS implícito)
- detectors/ob.py       -> Order Blocks (bull/bear, breaker)
- detectors/fvg.py      -> Fair Value Gaps
- detectors/choch.py    -> CHoCH
- detectors/zones.py    -> premium/discount (swing range)
- detectors/trend.py    -> tendencia
- detectors/displacement.py -> displacement (ya existe)

## Qué NO existe (PORtar del Pine Script de LuxAlgo)
1. Liquidez (Buyside/Sellside): clusters de swings en rango ATR/a alrededor de máx/min.
2. Killzones: sesiones NY 07-09, London Open 07-10, London Close 15-17, Asian 10-14 (horario del símbolo).
3. NWOG/NDOG: gaps de viernes->lunes y día->día (cajas de sesión).
4. Fibonacci: niveles entre 2 puntos (0.236..1.618) para el último FVG/OB/Liq.

## Archivos nuevos
- detectors/liquidity.py  -> detect_liquidity(frame, atr_mult) -> df con bsl/ssl
- detectors/killzones.py  -> detect_killzones(frame) -> columna kz (NY/LDN/ASIA)
- detectors/gaps.py       -> detect_nwog_ndog(frame) -> cajas de sesión
- detectors/fib.py        -> fib_levels(y0, y1) -> dict niveles

## Modificaciones
- scripts/mapa_precio.py: importar los nuevos y pintar:
  * OB verde/rojo (ya hace), FVG azul (ya hace)
  * Liquidez: cajas naranja (BSL) / celeste (SSL)
  * Killzones: banda de fondo tenue por sesión
  * NWOG/NDOG: caja punteada
  * Fib: líneas entre último FVG

## No objetivo
- NO tocar el loop (Ruben: "no lo integres al loop"). Solo mapa_precio.py.
- NO cambiar la lógica de trading existente, solo visualización.

## Verificación
- py_compile de cada módulo nuevo + mapa_precio.py
- Generar PNG y validar visualmente (vision) que aparecen las zonas.
