# ICT — Liquidez (Buyside / Sellside) y Liquidity Sweeps

Fuente: litefinance.org, fluxcharts.com, fxopen.com.

## Concepto
El mercado se mueve buscando liquidez. La "liquidez" son las órdenes agrupadas
(stops de unos y otros) en niveles clave.

- **BSL (Buyside Liquidity):** niveles donde los cortos tienen sus stop loss
  (típicamente por encima de máximos: swing highs, prev day high, equal highs).
- **SSL (Sellside Liquidity):** niveles donde los largos tienen sus stop loss
  (típicamente por debajo de mínimos: swing lows, prev day low, equal lows).

## Liquidity Sweep (barrido de liquidez)
- **Sweep de SSL:** el precio baja a un nivel SSL, lo rompe por debajo y sube de vuelta.
  (Atrapa cortos débiles, toma stops de largos.)
- **Sweep de BSL:** el precio sube a un nivel BSL, lo rompe por encima y baja de vuelta.

El sweep es la fase de **manipulación** (ver PO3, `08_POWER_OF_THREE.md`): crea la
mueva falsa para luego entregar el movimiento real en dirección opuesta.

## Por qué es el corazón de ICT
Casi todo setup ICT empieza con un sweep:
- Turtle Soup: sweep de SSL + MSS alcista (reversión).
- Silver Bullet: sweep de SSL + FVG alcista (intradía).
- PO3: manipulación barre el open del día, luego expansión.

## Cómo operarlo
- Marcar BSL/SSL en TF mayor (H1/H4) como objetivos de TP y zonas de sweep.
- Tras el sweep, esperar confirmación (MSS/CHoCH + FVG) antes de entrar.
- NO entrar contra el sweep (no "pescar el cuchillo"); esperar el retorno.

## En SMC-SYSTEMS
- `detectors/liquidity.py` calcula BSL/SSL. `mapa_precio.py` los pinta como líneas
  discontinuas (rojo BSL / naranja SSL).
- La pestaña Principal usa BSL/SSL como TP sugerido del setup intradía.
