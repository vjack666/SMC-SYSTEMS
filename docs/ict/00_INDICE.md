# Biblioteca ICT — Índice

Colección de reglas ICT (Inner Circle Trader, Michael J. Huddleston) compiladas
desde fuentes públicas especializadas para uso en SMC-SYSTEMS. Cada archivo es
un "libro" de la biblioteca; Graphify los indexa para que la app pueda citarlos.

> Nota de fuente: estos resúmenes son síntesis fiel de documentación ICT pública
> (innercircletrader.net, fluxcharts.com, fxopen.com, alchemymarkets.com, litefinance.org).
> No sustituyen el ICT Mentorship de pago; son reglas operativas verificables.

## Libros
- `01_KILLZONES.md` — Sesiones de alta actividad institucional (Asian/London/NY) y horarios.
- `02_MSS_CHOCH.md` — Market Structure Shift (MSS), Change of Character (CHoCH), Break of Structure (BOS). **Extendido 2026-07-11:** cómo lo usan traders en la práctica (entrada/gestión, MTF, sesiones), cómo lo calculan apps automáticas (MQL5 Sentinel/USA, XGBoost+SMC de MetaQuotes), y el impacto de **Chart Shift** + **profundidad de histórico** + **look-ahead** (conectado a la auditoría #1/#2).
- `03_FVG.md` — Fair Value Gaps. **Extendido 2026-07-12:** teoría (3 velas, mitigado/no mitigado) → práctica (sweep + retroceso, multi-TF, killzone) → algoritmo (shift(2), sin look-ahead, Chart Shift + profundidad) → código (`detectors/fvg.py`, `signals/pipeline.py`, `ict_backtest/`) → auditoría (#1 look-ahead NO aplica al FVG; #6 performance) → resultados (PF 2.003→1.548, OOS 3.389±2.303).
- `04_ORDER_BLOCKS.md` — Order Blocks y Breaker Blocks. **Extendido 2026-07-12:** teoría (OB válido, breaker) → práctica (retroceso, confluencia OB+FVG+CHoCH, multi-TF) → algoritmo (cuerpo grande + followthrough, riesgo shift(-1)) → código (`detectors/ob.py` Item E validación, `signals/pipeline.py`, `ict_backtest/`) → auditoría (#1 look-ahead en followthrough, #2 CHOCH real = breaker) → resultados medidos.
- `05_LIQUIDEZ.md` — Buyside/Sellside Liquidity (BSL/SSL) y liquidity sweeps. **Extendido 2026-07-12:** teoría (BSL/SSL, sweep como manipulación) → práctica (sweep + esperar confirmación, no entrar contra) → algoritmo (cluster atr/margin, sweep por ruptura+reversión) → código (`detectors/liquidity.py` solo pinta; `detectors/bos.py` + `signals/pipeline.py` filtran sweep) → HUECO REAL: liquidez decorativa desacoplada del sweep de señal → resultados medidos.
- `06_TURTLE_SOUP.md` — Turtle Soup (reversión contra tendencia). **Extendido 2026-07-12:** teoría (sweep + MSS opuesto) → práctica (SSL/BSL en HTF, entrada en retorno) → código (`ict_backtest/rules.py` checklist intradia contra tendencia: sweep M15 + FVG M1/M5 + SL FVG/OB + RR 1:2) → auditoría (#1 look-ahead en MSS, #2 CHOCH real) → resultados medidos.
- `07_SILVER_BULLET.md` — Silver Bullet (intradía/scalping). **Extendido 2026-07-12:** teoría (sweep + FVG en killzone) → práctica (sesgo del día, 1:2 Stellar) → código (`detectors/killzones.py` horas broker vs ET del mentorsip; `fvg.py`; `rutina_eurusd.py`) → salvedad de zona horaria + auditoría → resultados medidos.
- `08_POWER_OF_THREE.md` — Power of Three / AMD. **Extendido 2026-07-12:** teoría (acumulación→manipulación→distribución) → práctica (sesgo D1, open del día, CHoCH) → código (PO3 = unión sweep+CHoCH+zonas+sesgo en `rules.py` intradia) → auditoría (#1/#2/#5) → resultados medidos.
- `09_OPTIMIZADOR_BAYESIANO.md` — Optimizador bayesiano para el backtest (Capa 3): qué es, overfitting, walk-forward, Optuna. [No es regla ICT; es algoritmo de validación del backtest.]
- `10_SWEEP_OTE_FILTRO.md` — Sweep de liquidez + OTE como filtros de señal (Ítem D). **Creado 2026-07-12:** teoría ICT (caza de BSL/SSL + OTE 62-79%) → código (`detectors/liquidity.py` + `signals/pipeline.py` ya cableados con pesos sweep=2.0/ote=1.0) → evidencia medida EURUSD M15 (sweep 66% activo, OTE 1% no-op) → HUECO REAL: bandas OTE inalcanzables en M15 (fix propuesto, pendiente walk-forward OOS).
- `11_SWEEP_OTE_MANUAL_VS_AUTO.md` — Sweep + OTE: Manual vs Automático vs nuestro híbrido. **Creado 2026-07-12 (investigación internet):** manual (Bennett/arongroups: HTF→OTE 62-79%→sweep+esperar→M15) vs EA MQL5 "ICT EA" (H1 bias→sweep→MSS→displacement→FVG→liquidez target) vs SMC-SYSTEMS (tabla cerebro idéntico al EA) → GAP futuro 100% auto: no hay ejecutor MT5 en repo + TP 2×ATR fijo (no liquidez opuesta).

## Cómo se usa en SMC-SYSTEMS
- `detectors/` ya implementa BOS/CHOCH (bos.py, choch.py), OB (ob.py), FVG (fvg.py),
  liquidez (liquidity.py), killzones (killzones.py). Estos libros son la REFERENCIA
  de reglas que esos detectores materializan.
- La pestaña "Principal" (resumen_widget.py) cita estos libros para explicar el setup.
- El grafo Graphify (graphify-out/graph.json) indexa el CÓDIGO; estos .md indexan la
  TEORÍA. Juntos dan trazabilidad: regla -> detector -> código.
