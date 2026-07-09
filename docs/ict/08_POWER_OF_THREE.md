# ICT — Power of Three (PO3 / AMD model)

Fuente: fxopen.com (ICT Power of 3), litefinance.org.

## Concepto
Modelo que describe el ciclo del precio en 3 fases (también llamado AMD:
Accumulation-Manipulation-Distribution). Explica POR QUÉ el precio barre liquidez
antes del movimiento real.

## Fases
1. **Accumulation (acumulación):** rango lateral de baja volatilidad cerca de soporte/
   resistencia. Se construye la liquidez (stops se apilan fuera del rango).
2. **Manipulation (manipulación / liquidity sweep):** el precio rompe el rango para
   cazar stops (stop hunt / false breakout). Cierra de vuelta dentro del rango.
   - En setup alcista: sumerge bajo el rango (barre SSL).
   - En setup bajista: dispara sobre el rango (barre BSL).
3. **Distribution (expansión):** el precio rompe la estructura y se extiende en la
   dirección real con volumen y velas fuertes. Es el movimiento que paga.

## Aplicación en intradía (workflow ICT)
1. Definir **sesgo del día** en TF mayor (H4/D1).
2. Marcar el **open del día** como nivel de referencia.
3. Identificar la **manipulación** más allá del open/rango (barrido de liquidez).
4. Confirmar entrada en TF menor (M5/M15) con **CHoCH** o ruptura de estructura.
5. Gestionar con SL por fuera del extremo de manipulación.

## Confirmación de la fase de distribución
- Velas direccionales fuertes (cuerpos grandes).
- Ruptura decisiva de la estructura del rango.
- Expansión de volumen.
- Alineación con TF mayor.

## Relación con tus otros libros
- La **manipulación** = liquidity sweep (`05_LIQUIDEZ.md`).
- La confirmación de entrada = CHoCH/MSS (`02_MSS_CHOCH.md`).
- La zona de retorno = FVG / Order Block (`03_FVG.md`, `04_ORDER_BLOCKS.md`).

## En SMC-SYSTEMS
- Tu motor ya calcula sesgo D1/H4 (`rutina_eurusd.py`) + sweep (`liquidity.py`) +
  CHoCH (`choch.py`). PO3 es el "relato" que une esos detectores.
- La pestaña Principal puede narrar: "sesgo D1 + sweep de SSL + CHoCH M15 = PO3 alcista".
