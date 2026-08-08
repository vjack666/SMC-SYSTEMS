# MDS_D1_OTE.md — OTE 62-79% (D1)

- **Clasificación**: OBLIGATORIO · Fase D1 · **Estado: ✅ HECHO (en motor)**
- **SDD-first**: refleja `engine/dealing_range.py` (OTE_MIN_RETRACE / OTE_MAX_RETRACE).

## Propósito
Definir la zona de entrada óptima (Optimal Trade Entry) como el retroceso del
62% al 79% del rango de la estructura (deal­ing range). La tesis (libro 18) usa
el 62-79% como el "discount" donde el precio regresa antes de continuar.

## Por qué importa (geometría)
El OTE es pura proporción de rango (Fibonacci 0.618-0.79 aplicado a la extensión
del swing). No usa ningún indicador: solo high/low del rango y el precio actual.
El humano entra en el retorno al 62-79% del rango, no en cualquier parte.

## Entradas (geometría + volumen)
- Rango de la estructura (high/low del swing).
- Precio actual (retorno).
- VOLUMEN: el agotamiento del retorno en la zona OTE se confirma con volumen
  (dato de mercado, no indicador).

## Lógica (engine/dealing_range)
`OTE_MIN_RETRACE = 0.62`, `OTE_MAX_RETRACE = 0.79`. El precio entra en zona OTE
si `0.62 <= (range_high - price) / (range_high - range_low) <= 0.79` (long) o
espejo para short. Usado por `is_ote_entry` en el backtest y por el motor para
anotar calidad del entry.

## Salidas
Bool `is_ote` + nivel OTE (precio del 62-79%).

## Integración
Vive en `engine/dealing_range.py` (permanente). Consumido por
`ict_backtest/canonical.is_ote_entry` y por el motor en la capa de ejecución.
Ley: engine/ no importa ict_backtest.

## Verificación
Tests de dealing_range en `tests/test_engine_dealing_range.py` (rangos sintéticos
62-79% → True; fuera → False).
