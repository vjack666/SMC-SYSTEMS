# ICT — Market Structure Shift (MSS), Change of Character (CHoCH), Break of Structure (BOS)

Fuentes: fxopen.com (MSS), alchemymarkets.com (CHoCH), litefinance.org.

## Jerarquía de rupturas de estructura
| Patrón | Señal | Confirmación | Implicación |
|--------|-------|--------------|-------------|
| **BOS** | Continuación de tendencia | Ruptura de swing en dirección de la tendencia | La tendencia probablemente continúa |
| **CHoCH** | Aviso temprano de reversión | Ruptura del swing contrario a la tendencia (1ra vez) | La tendencia puede estar debilitándose |
| **MSS** | Reversión confirmada | Fallo de swing + ruptura decisiva + desplazamiento (displacement) | Posible reversión de tendencia formándose |

## BOS (Break of Structure)
- Precio rompe un swing reciente **en la dirección de la tendencia vigente**.
- Señal de continuación. Tu `detectors/bos.py` lo detecta (bos_dir + bos_status).

## CHoCH (Change of Character)
- Precio rompe el swing **contrario** a la tendencia por primera vez.
- Es aviso temprano, NO confirmación. En uptrend: nuevo lower low. En downtrend: nuevo higher high.
- `detectors/choch.py` lo detecta.
- **Fake-out CHoCH**: ruptura débil (mecha, sin cierre limpio, vela pequeña, bajo volumen)
  y rebote brusco — común en noticias de alto impacto. Se trata como falsa.

## MSS (Market Structure Shift)
- Reversión confirmada. Requiere: (1) fallo de estructura (LH en uptrend / HL en downtrend),
  (2) ruptura decisiva del swing contrario, (3) vela de desplazamiento fuerte (no solo mecha).
- Sin desplazamiento, es CHoCH no MSS.
- Confirmación extra: liquidity sweep previo + alineación con TF mayor.

## Regla de contexto (clave para "a favor / contra tendencia")
- CHoCH/MSS en TF menor se leen contra el contexto del TF mayor (H4/D1).
- Setup alineado con TF mayor = continuación (a favor). Setup opuesto = reversión (contra).
- CHoCH es más fiable en London/NY (participación real); fuera de sesión da falsas.

## En SMC-SYSTEMS
- `bos.py` (BOS) + `choch.py` (CHoCH) ya detectados. MSS = BOS tras CHoCH con desplazamiento.
- La pestaña Principal etiqueta "a favor / contra tendencia" comparando bos_dir M15 vs tendencia D1.
