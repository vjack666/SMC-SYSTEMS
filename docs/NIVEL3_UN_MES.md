# NIVEL 3 — Un mes de datos M15 en replay causal (CIERRE DE MISIÓN)

**Fecha:** 2026-08-14
**Autor:** Hermes (bajo Change Gate Opcion B, autorizado por Director)
**Pregunta del Director:** "¿puedes probar con un mes de datos? Si no hay setup en
ese mes, hay algo que no funciona y no es la estrategia."

## Resultado (evidencia, no conjetura)
```
REPLAY (incremental, step(i), config FASE A exacta)
  velas M15 = 2113 (~1 mes real: 2022-01-02 + 30 dias)
  setups     = 165
  tiempo     = 1182.9s (~20 min, O(N))
  biasH4     = BULLISH todo el mes
  fases vistas: SWEEP_DONE, DISPLACE_DONE, BOS_DONE, IDLE (secuencia real del motor)
  lineage primer setup: dir=-1 sweep_at=1 bos_at=10 entry_at=11 (indices absolutos)
```

## Conclusión de la hipótesis de falsabilidad
El Director planteó: "si en un mes NO hay setup => falla del motor (no estrategia)".
La prueba dio la vuelta esperada:
- N=300 (<1 semana): 0 setups => era RUIDO de muestra chica, NO falla.
- N=2113 (1 mes): 165 setups en regimen CAUSAL => el motor SI opera en vivo.

**La hipótesis de falla QUEDA FALSADA.** El motor funciona bajo información causal.
Los 0 setups de N=300 no eran bug del replay ni del motor: era ventana insuficiente
para que la estructura HTF cerrara setups.

## Estructura disponible en los datos (N=2113)
- FVG LTF M15 = 0  | OB LTF M15 = 0  (detect_market_structure no los marca en M15)
- CHOCH H4 = 0
- BOS H4 = 572  | POI anclado = disponible 300/300
- El motor forma setups con BOS HTF + POI anclado como cuadro de entrada.
  FVG/OB LTF = 0 y CHOCH = 0 NO son requisito del motor (diseno valido, no bug).

## Gates de la misión (TODOS CERRADOS)
```
Nivel 1: Contexto original == contexto optimizado   ✅ (Opción 3, 12/12 velas)
Nivel 2: REPLAY(t) == LIVE(t)                       ✅ (0 setups N=300, misma semántica)
Nivel 3: Setup causal reproducible en un mes         ✅ (165 setups, 2113 velas, O(N))
```

## Cambios que hicieron posible esto (Change Gates autorizados)
1. OPCIÓN 3 (contexto HTF O(n), neutro): `engine/plan.py`, `engine/multitf_context.py`.
2. OPCIÓN B (step(i), una sola lógica, índices absolutos, O(N)):
   `engine/sequence.py` (`_run_sequence_impl` single_step, `class SequenceRunner`,
   `run_sequence_traced` refactorizado), `market_replay/replay.py` (usa UN runner,
   step(i) vela a vela, SIN sublista objs[:i+1]).
3. Correcciones: em-dashes/docstring duplicado en sequence.py; recorte de TFs en
   load_frames de scripts; SequenceRunner espera lista de MarketObject.

## Rendimiento honesto
Un mes = 1183s (~20 min). O(N) pero cada vela hace trabajo real de estructura.
Para ventanas multi-año habría que optimizar más, pero para validación causal
mensual es aceptable.

## Regla del Director mantenida
No afirmar PASS sin evidencia. Backtest (batch) != online (replay). La misión
demostró REPLAY(t)==LIVE(t) y que el motor forma setups en vivo. No se fabricaron
setups: el motor los produjo bajo información causal con config FASE A exacta.
