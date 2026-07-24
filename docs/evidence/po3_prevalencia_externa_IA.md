# Referencia cualitativa: prevalencia del ciclo PO3 en EURUSD (análisis EXTERNO por IA)

**Fecha:** 2026-07-24
**Origen:** script generado por IA externa (`po3_analysis.py`), corriendo sobre
EURUSD H4 (6.978 velas) + M5 (325.433 velas), 2022-01-02 → 2026-06-26.
**NO es el motor PO3 de SMC-SYSTEMS.** Definiciones propias del script.

## Conteos por método (definición del script, NO del motor)
- Método A (Wick Morphology, vela H4 con mecha dominante): 700 (358 bull / 342 bear)
- Método B (Swing Sweep + confirmación M5): 460 (251 bull / 209 bear) ≈ 1.26/día
- Método C (Acumulación 3 velas + sweep + reversión): 1.638 (885 bull / 753 bear)
- Convergencia B∩C: 460 barras H4.
- Por año (B+C): ~460/año, bastante parejo (2022:470, 2023:468, 2024:450,
  2025:472, 2026:238 parcial).

## Qué SÍ prueba esto
- El ciclo PO3 es PREVALENTE y frecuente en EURUSD real (no es raro).
- Destruye la hipótesis de "muestra escasa" como explicación del 0 del motor:
  en 1.5 meses deberían haber decenas de ciclos PO3. El 0 del motor era BUG
  de detección (ver `canonical.py` desalineación H4-por-índice, commit 011806e),
  NO falta de ciclos en el mercado.

## Qué NO prueba (no usar como benchmark del motor)
1. Definiciones DISTINTAS a `ict_backtest/signals/po3.py` (A=sesgo HTF+rango,
   M=sweep contra sesgo, D=CHOCH/BOS a favor+FVG/OB, +alineación a-favor HTF).
2. No aplica filtro de alineación a-favor del HTF (cuenta también contratendencia
   = Turtle Soup en el motor).
3. No tiene killzone ni directional bias del framework.
4. Stack de TF distinto (H4+M5 vs D1/H4/H1/M15/M5/M1 del motor).

## Conclusión de uso
- Válido como evidencia CUALITATIVA de prevalencia (refuta "muestra escasa").
- INVÁLIDO como benchmark de "cuántas señales PO3 debe dar el motor".
- El número de referencia VÁLIDO para el motor es el del test slow corregido
  sobre datos completos (la ventana de 4000 M15 da solo 1 señal base → inservible
  para medir conteo PO3).
