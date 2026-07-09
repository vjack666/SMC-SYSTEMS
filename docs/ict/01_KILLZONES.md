# ICT — Killzones (Sesiones de actividad institucional)

Fuente: innercircletrader.net (ICT Killzones), howtotrade.com, litefinance.org.

## Concepto
Una **killzone** es una ventana de tiempo donde los grandes operadores están más
activos. En ICT el trading intradía se concentra en estas ventanas; fuera de ellas
los setups son menos fiables (más falsas rupturas, CHoCH débiles).

## Horarios (hora local New York / ET)
| Killzone | Horario ET | Notas |
|----------|-----------|-------|
| Asian | 20:00 – 23:00 ET (invierno) | Baja volatilidad, define rango del día. |
| London Open | 02:00 – 05:00 ET | Primera ventana fuerte; solapa con apertura Europa. |
| New York AM | 08:30 – 11:00 ET | La más líquida; solapa Londres 08:30–11:00. |
| New York PM | 13:00 – 16:00 ET | Segunda ventana; cierre de posiciones. |

> En verano (DST) los horarios ET se adelantan 1h respecto a estándar. Tu
> `killzones.py` ya pinta Asian/London/NY sobre el gráfico.

## Uso operativo
- Marcar el rango de la sesión Asian (su high/low) como zona de liquidez del día.
- Esperar el setup (sweep + FVG / MSS) DENTRO de London o NY AM, no fuera.
- Si no hay setup en London, esperar NY AM (regla ICT estándar).

## En SMC-SYSTEMS
- `detectors/killzones.py` define las bandas. `mapa_precio.py` las pinta (alpha 0.07).
- La pestaña Principal puede advertir: "setup fuera de killzone = menor confianza".
