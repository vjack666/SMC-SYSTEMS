# ICT — Order Blocks y Breaker Blocks

Fuente: litefinance.org, fxopen.com, alchemymarkets.com.

## Order Block (OB)
Zona donde los grandes jugadores acumulan posición sin mover el precio bruscamente.
Deja una "huella" justo antes de un movimiento fuerte.

- **OB alcista:** la ÚLTIMA vela bajista antes de un movimiento fuerte al alza.
  Actúa como soporte.
- **OB bajista:** la ÚLTIMA vela alcista antes de un movimiento fuerte a la baja.
  Actúa como resistencia.

### Características de un OB válido
1. **Liquidity sweep:** la vela barre liquidez (rompe el low anterior en OB alcista /
   el high anterior en OB bajista).
2. **Imbalance:** tras el OB el precio se aleja rápido, dejando FVG.
3. **Unmitigated:** el precio aún no volvió a la zona → órdenes "activas".

## Breaker Block
Si el precio rompe el OB y este se convierte en soporte/resistencia en sentido
contrario, el OB se vuelve **breaker block** (confirmación de cambio de estructura).

## Cómo operarlo
- Esperar retroceso al OB (o al FVG que dejó el desplazamiento).
- Entrada en la zona; SL por fuera del OB.
- Confluencia: OB + FVG + CHoCH = setup de alta probabilidad.

## En SMC-SYSTEMS
- `detectors/ob.py` detecta Order Blocks. `mapa_precio.py` los pinta (verde/rojo, alpha 0.18).
- La pestaña Principal lista OB alcista/bajista por TF con su rango real.
