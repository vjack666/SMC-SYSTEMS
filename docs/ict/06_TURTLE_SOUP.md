# ICT — Turtle Soup (Reversión contra tendencia)

Fuente: fluxcharts.com (ICT Turtle Soup).

## Concepto
Estrategia de **reversión** que aprovecha falsas rupturas en zonas de liquidez de
TF mayor. Es el modelo clásico de **CONTRA TENDENCIA** en ICT.

## Pasos
1. En TF mayor marca BSL y SSL (máximos/mínimos recientes, prev day/week high/low).
2. En TF menor (M15/M5) esperar **sweep** de esa liquidez.
3. Tras el sweep, esperar un **MSS** (market structure shift) en la dirección opuesta.
4. Entrar tras el MSS (o en el retroceso a OB/FVG).

## Setups
- **Turtle Soup alcista:** marca SSL en TF mayor → en menor, sweep de SSL + MSS alcista
  → long. SL bajo el SSL; TP en el BSL más cercano de TF mayor.
- **Turtle Soup bajista:** marca BSL en TF mayor → en menor, sweep de BSL + MSS bajista
  → short. SL sobre el BSL; TP en el SSL más cercano.

## Tipos
- **External Range:** precio sale del rango y revierte hacia el lado opuesto (reversión).
- **Internal Range:** el mercado ya tiende y hace pullback (continuación, a favor).

## No es obligatorio esperar MSS
Se puede entrar en el retroceso a OB/FVG tras el sweep, sin esperar MSS confirmado.

## TF recomendados
- Si operas ≤ M15: usa H1 para marcar liquidez.
- Si operas H1: usa H4+.

## En SMC-SYSTEMS (aplicación a tu pregunta "contra tendencia")
- Tu `bos.py`/`choch.py` detectan el MSS/CHoCH; `liquidity.py` el BSL/SSL.
- La pestaña Principal etiqueta "CONTRA TENDENCIA (Turtle Soup)" cuando:
  bos_dir M15 es opuesto a la tendencia D1 Y hay sweep de la liquidez opuesta.
- TP sugerido = liquidez opuesta (ya calculada en `liquidity.py`).
