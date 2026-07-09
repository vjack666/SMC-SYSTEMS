# Biblioteca ICT — Índice

Colección de reglas ICT (Inner Circle Trader, Michael J. Huddleston) compiladas
desde fuentes públicas especializadas para uso en SMC-SYSTEMS. Cada archivo es
un "libro" de la biblioteca; Graphify los indexa para que la app pueda citarlos.

> Nota de fuente: estos resúmenes son síntesis fiel de documentación ICT pública
> (innercircletrader.net, fluxcharts.com, fxopen.com, alchemymarkets.com, litefinance.org).
> No sustituyen el ICT Mentorship de pago; son reglas operativas verificables.

## Libros
- `01_KILLZONES.md` — Sesiones de alta actividad institucional (Asian/London/NY) y horarios.
- `02_MSS_CHOCH.md` — Market Structure Shift (MSS), Change of Character (CHoCH), Break of Structure (BOS).
- `03_FVG.md` — Fair Value Gaps (brechas de valor justo) y cómo operarlas.
- `04_ORDER_BLOCKS.md` — Order Blocks y Breaker Blocks (huellas institucionales).
- `05_LIQUIDEZ.md` — Buyside/Sellside Liquidity (BSL/SSL) y liquidity sweeps.
- `06_TURTLE_SOUP.md` — Modelo de reversión contra tendencia (sweep + MSS).
- `07_SILVER_BULLET.md` — Modelo intradía/scalping (killzone + sweep + FVG).
- `08_POWER_OF_THREE.md` — Power of Three / AMD (Accumulation-Manipulation-Distribution).

## Cómo se usa en SMC-SYSTEMS
- `detectors/` ya implementa BOS/CHOCH (bos.py, choch.py), OB (ob.py), FVG (fvg.py),
  liquidez (liquidity.py), killzones (killzones.py). Estos libros son la REFERENCIA
  de reglas que esos detectores materializan.
- La pestaña "Principal" (resumen_widget.py) cita estos libros para explicar el setup.
- El grafo Graphify (graphify-out/graph.json) indexa el CÓDIGO; estos .md indexan la
  TEORÍA. Juntos dan trazabilidad: regla -> detector -> código.
