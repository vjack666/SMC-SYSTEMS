# Avances ICT Backtest — 2026-07-10

Proyecto: SMC-SYSTEMS. Módulo nuevo: `ict_backtest/`. Objetivo: validación de
estrategia ICT desde cero (SIN ML en la regla; ML solo en Capa 3 para ajustar
parámetros). Todo verificado con datos reales XAUUSD (MT5 FundedNext).

## Contexto de datos (MT5 FundedNext)
- XAUUSD_H4.parquet: 10.066 velas, 2020 → 2026 (~6.5 años). Local.
- XAUUSD_D1.parquet: disponible, mismo rango.
- XAUUSD_M15: solo ~50k velas desde 2024 (2 años) — insuficiente para muestra grande.
- `ict_backtest/data_feed.py` carga parquet y corre detectores (bos, choch,
  displacement, fvg, liquidity, order_blocks, trend) produciendo las columnas
  que el motor consume.

## Capas construidas
- PARTE 1: `ict_backtest/structure.py` — clasificación BULLISH/BEARISH/RANGING.
- PARTE 2: `ict_backtest/rules.py` (mini-check del dashboard rescatado,
  parametrizado por TF) + `ict_backtest/engine.py` (simulación vela a vela).
- PARTE 2.1: 4 variantes a-favor / contratendencia (V1..V4). Ninguna robusta.
- `ict_backtest/market_structure.py`: reglas BOS/CHOCH canónicas con memoria
  de estado (activo/invalidado/envejecido). Corrige el CHOCH viejo (que usaba
  medias 20/50 y casi no disparaba).
- `ict_backtest/sequence.py`: CAPA 2 — motor EVENT-SEQUENCE (ver abajo).
- `ict_backtest/run_backtest.py`: runner con --engine sequence y --sweep.

## Hallazgos clave (empíricos, no opiniones)
1. Bug raíz diagnosticado por el usuario: el mini-check evaluaba sweep+BOS+
   displacement en la MISMA vela ("todo de golpe"). En ICT los eventos ocurren
   en SECUENCIA y el mercado se revela en cascada D1→H4→M15.
2. Sesgo del CHOCH viejo (evidencia en `_cmp_bos.py`): el viejo `detectors/
   choch.py` usa medias móviles 20/50 → solo 346 CHOCH / 10k velas H4 (34/mil).
   El nuevo (ruptura de swing opuesto) da 2547 (253/mil) — 7.4x más. El BOS
   quedó idéntico (4152 en ambos). Este sesgo mataba la contratendencia.
3. FVG en bots automatizados (investigado en web): NO entran cuando aparece el
   FVG. Detectan el FVG, trazan el CUADRO (rango alto→bajo / 50% fill) y ESPERAN
   el retorno (mitigation). Fuentes: TradingView, crosstrade.io, Ziad Francis.
   Nuestro `sequence.py` original exigía FVG en la misma ventana → 0 entradas.
   Corregido: tras el BOS se traza el cuadro (FVG > OB > BOS±ATR) y la entrada
   es cuando la vela RETORNA al cuadro.

## Resultados reales (XAUUSD, backtest end-to-end)
- PARTE 2 checklist (D1→H4, a-favor, TP 2R): PF 0.734, WR 28%, 171 trades, -32.5 R.
- PARTE 2.1 V1 AT fixed2r:    PF 0.73,  WR 28%,  171t, -32.5R
- PARTE 2.1 V2 AT liq+disp:   PF 0.83,  WR 25%,    4t,  -0.4R
- PARTE 2.1 V3 CT liq+disp:    PF 1.41,  WR 33%,    3t,  +0.6R (ruido: 3 trades)
- PARTE 2.1 V4 CT fixed2r:     PF 0.79,  WR 29%,   69t, -10.2R
- CAPA 2 sequence (D1→H4, a-favor, retorno al cuadro): PF 1.132, WR 36.4%,
  11 trades, +0.8 R  ← PRIMER PF>1 del proyecto.

Conclusión: al esperar la secuencia (no todo de golpe) el PF pasa de 0.73 a
1.13. La DIRECCIÓN es correcta; falta VOLUMEN (11 trades es poco concluyente).

## Notas de diseño acordadas con el usuario
- Top-down fractal: D1 marca rango/liquidez → H4 define zona/sesgo → M15 entrada.
- Contratendencia = operar la reversión contra el HTF (CHOCH/BOS opuesto).
- "Memoria" = estado secuencial del motor + (Capa 3) HMM/LSTM sobre la secuencia
  de estados. QUANTUM COMPUTING DESCARTADO: no es viable en 2026 para uso local
  (CNBC: advantage ~2028-2029; HSBC/IBM corrió offline y sin tocar trading vivo).
- ML = optimizador bayesiano (optuna/scikit-optimize) sobre hiperparámetros del
  backtest + walk-forward anti-overfit (Capa 3). NO clasificador sobre señales
  (frágil, pocas muestras M15).

## Commit más reciente (pusheado a origin/main)
`4c0a2a7 feat(ict_backtest): Capa 2 - motor EVENT-SEQUENCE (espera sucesos en orden)`
Rama: main == origin/main (sincronizado).

## PRÓXIMO PASO (decisión pendiente del usuario)
- (A) Correr Capa 2 en M15 para ganar volumen (~50k velas = muchas más
  secuencias) y confirmar que PF>1 aguanta con muestra grande. RECOMENDADO:
  sin volumen, el optimizador ML de Capa 3 sobre-ajustaría a 11 trades.
- (B) Meter Capa 3 (optimizador bayesiano) sobre H4 para ajustar gaps/parámetros
  de la secuencia (displace_gap, bos_gap, require_displacement, tp_mode).

Decidido al cierre: PENDIENTE. Retomar mañana con (A) si no hay contraindicación.

## Cómo correr mañana (recordatorio)
- Backtest Capa 2:  `PYTHONPATH=. python ict_backtest/run_backtest.py --symbol XAUUSD --htf D1 --ltf H4 --engine sequence --max-hold 16`
- Diagnóstico de fases: `PYTHONPATH=. python ict_backtest/sequence.py`
- Comparación CHOCH: `PYTHONPATH=. python ict_backtest/_cmp_bos.py`
- NOTA: los scripts dentro de ict_backtest/ requieren `PYTHONPATH=.` desde la
  raíz del repo (no se instalan como paquete). El runner principal ya añade ROOT
  al sys.path, pero _cmp_bos.py y sequence.py (__main__) necesitan PYTHONPATH=.
