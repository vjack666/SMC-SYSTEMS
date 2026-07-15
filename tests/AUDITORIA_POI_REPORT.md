# AUDITORÍA POI HTF — Resultado empírico (caso por caso)

Fecha: 2026-07-14
Símbolo: EURUSD H4->M15, 50.000 velas M15
Método: scripts/auditoria_poi.py — registra (sin bloquear) cada POI HTF
que el filtro hubiera exigido, y clasifica si tiene narrativa ICT detrás
(BOS en la dirección del trade en las últimas 40 velas H4).

## Números medidos
  Total de zonas LTF evaluadas contra el filtro POI HTF: 10.669
    - Por tipo:  FVG 9.682 (90.8%)  |  OB 987 (9.2%)
    - CON narrativa HTF (BOS en dirección en 40 velas H4): 0   → 0.0%
    - SIN narrativa HTF: 10.669  → 100.0%
    - Edad mediana del POI aceptado: 6 velas H4 (~1.5 días)

## Ejemplos crudos (primeros 20 de tests/auditoria_poi.json)
  TODOS "OB bearish @ 1.08337", edad 7-14 velas H4, narrativa_HTF=False.
  El MISMO OB (htf_idx 7032) se reusa como "POI" para 20 zonas LTF
  distintas a lo largo de 25 horas. Geometría suelta, no POI de narrativa.

## Veredicto empírico (responde a la orden del usuario)
  El sistema NO detecta "el POI de una narrativa". Detecta "cualquier
  FVG/OB que exista en una ventana de 20 velas H4". Como casi siempre hay
  uno, el filtro es casi siempre True (A'' apenas descartó 6 señales de 37)
  PERO esas "coincidencias" no tienen relación con la historia del precio.

  Concretamente: 100% de los POI aceptados carecen de un BOS/desplazamiento
  estructural en el HTF que los respalde. Es "todo FVG/OB H4 = POI".

  ESTO NO prueba que la teoría POI HTF esté equivocada. Prueba que la
  IMPLEMENTACIÓN marca geometría suelta, no POI de narrativa. Las 5
  opciones del usuario siguen abiertas; la más probable es la 3/4/5:
  el POI correcto existe pero se detecta mal / se usa en el momento
  equivocado / no está anclado a una narrativa.

## Por qué A'' dio PF 0.9 (causa raíz real)
  El filtro duro exigía "hay POI en ventana". Como el 100% de los POI del
  sistema son ruido, el filtro dejaba pasar las señales cuyo "POI" era más
  ruido y descartaba las pocas que no tenían ni eso. Un filtro que premia
  el ruido destruye el edge. No es "el POI no sirve": es "el POI se mide
  mal".

## Conexión con la ontología
  Falta la regla: "Este POI pertenece a ESTA narrativa". Hoy MarketObject
  tiene role=POI pero NADIE lo liga a un BOS/swing previo. El POI vive
  suelto. Esa es la brecha real entre código y biblioteca ICT.

## Decisión (NO apresurada, sale de la auditoría)
  El POI HTF debe implementarse COMO NODO DE NARRATIVA: solo cuenta si
  está anclado a un desplazamiento estructural HTF (BOS/CHOCH previo en
  esa dirección), no por existir como FVG/OB aislado. Recién entonces se
  decide su rol (filtro duro / bonus / peso / quality_score) con un nuevo
  backtest A'''. Hasta ahí: POI HTF DESACTIVADO por defecto.
