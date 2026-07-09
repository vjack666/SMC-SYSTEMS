# ICT — Silver Bullet (Modelo intradía / scalping)

Fuente: fluxcharts.com (ICT Silver Bullet), innercircletrader.net.

## Concepto
Modelo intradía basado en tiempo que combina **liquidez + FVG** dentro de una killzone.
Ideal para scalping (M1/M3/M5). Es el modelo más directo para operar en el día.

## Ventanas (hora ET)
| Ventana | Horario ET |
|---------|-----------|
| London Open | 03:00 – 04:00 ET |
| New York AM | 10:00 – 11:00 ET |
| New York PM | 14:00 – 15:00 ET |

## Pasos
1. Marcar BSL/SSL en el gráfico.
2. Esperar que el precio haga **sweep** de SSL (para long) o BSL (para short).
3. Tras el sweep, esperar un **FVG** rápido (desplazamiento).
4. Entrar en el retroceso al FVG.

## Gestión (1:2 mínimo, como tu regla Stellar)
- **Long:** SL bajo el FVG alcista, o en SSL; TP en BSL (1:2 o liquidez opuesta).
- **Short:** SL sobre el FVG bajista, o en BSL; TP en SSL.

## Mejora: sesgo del día
Si tu sesgo del día es alcista, solo buscas setups Silver Bullet alcistas; si bajista,
solo bajistas. Esto filtra ruido (y es justo lo que hace tu `rutina_eurusd.py`).

## Mejor TF
M1/M3/M5 (ventanas de 1h). El contexto (sesgo) se define en H4/D1.

## En SMC-SYSTEMS
- `killzones.py` (ventanas) + `fvg.py` (FVG) + `liquidity.py` (BSL/SSL) ya listos.
- La pestaña Principal puede sugerir "Silver Bullet" cuando hay sweep + FVG dentro de
  killzone y el sesgo del día coincide con la dirección.
