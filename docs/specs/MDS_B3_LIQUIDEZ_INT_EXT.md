# MDS_B3_LIQUIDEZ_INT_EXT.md — Liquidez internal / external (B3)

- **Clasificación**: OBLIGATORIO · Fase B3 · **Estado: 🔲 NO INICIADO (solo diseño)**
- **SDD-first**: diseño a implementar en `engine/liquidity_zones.py` (respetando
  que `engine/liquidity_levels.py` ya tiene BSL/SSL básicos).

## Propósito
Distinguir liquidez INTERNA (máximos/mínimos de swings menores dentro de un rango)
de liquidez EXTERNA (máximos/mínimos que el precio busca barrer más allá del rango).
La tesis ICT: el precio primero barre la liquidez interna (stop hunts menores) y
luego la externa (objetivo real).

## Por qué importa (geometría)
Sin esta distinción el motor no sabe si un sweep es "ruido interno" o "objetivo
externo". Es geometría pura: posición del swing relativo al rango + barrido de
mecas. Cero indicadores. VOLUMEN: el barrido de liquidez externa con volumen alto
confirma convicción (dato, no indicador).

## Entradas (geometría + volumen)
- OHLC por TF, swings (pivotes), BSL/SSL ya detectados.
- VOLUMEN: tick volume por vela para confirmar el barrido.

## Lógica (geometría pura, diseño)
1. Marcar swings como internal si están DENTRO del dealing range; external si son
   extremos del rango o breakouts previos.
2. Un sweep de external liquidity = objetivo de la estructura (TP del motor).
3. Un sweep de internal = retroceso esperado antes de continuar.

## Salidas
`{"internal_liq": [...], "external_liq": [...], "target": external_level}`.

## Integración
Nuevo módulo `engine/liquidity_zones.py` (permanente). Consumido por backtest.
Ley: engine/ no importa ict_backtest.

## Verificación (pendiente)
pytest con swings sintéticos internal/external.
