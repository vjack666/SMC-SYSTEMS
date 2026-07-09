# ICT — Fair Value Gaps (FVG)

Fuente: litefinance.org, fluxcharts.com, alchemymarkets.com.

## Concepto
Un **FVG** es un desequilibrio de oferta/demanda: el precio se mueve tan rápido que
deja un rango de precios "no negociado" entre 3 velas. El precio suele regresar al
FVG para reequilibrar (fill the gap).

## Formación (3 velas)
- **FVG alcista:** el high de la vela 1 queda POR DEBAJO del low de la vela 3 →
  hueco entre ellas (imbalance comprador).
- **FVG bajista:** el low de la vela 1 queda POR ENCIMA del high de la vela 3.
- Si las mechas de vela 1 y 3 se solapan → NO hay FVG.

## Por qué importa
- El desplazamiento que confirma un MSS casi siempre deja un FVG y un Order Block.
- El FVG actúa como "vacío" que atrae el precio de vuelta: zona de entrada en pullback.

## Cómo operarlo
1. Tras un sweep de liquidez, esperar FVG (desplazamiento).
2. Entrar en el retroceso al FVG (no perseguir).
3. SL: por debajo del FVG alcista / por encima del FVG bajista.
4. TP: liquidez opuesta (BSL si long / SSL si short) o 1:2 mínimo.

## FVG mitigado vs no mitigado
- **No mitigado (unfilled):** el precio aún no volvió al FVG → sigue "activo" como zona.
- **Mitigado:** el precio ya lo tocó → pierde fuerza como entrada, pero confirma la zona.

## En SMC-SYSTEMS
- `detectors/fvg.py` devuelve FVG activos. `mapa_precio.py` los pinta (alpha 0.18, verde/rojo).
- La pestaña Principal puede sugerir "Silver Bullet" cuando hay sweep + FVG en killzone.
