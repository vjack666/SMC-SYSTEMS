# FASE 5 — VALIDACIÓN + FALSACIÓN Arquitectura A (HYP-002)

Símbolo EURUSD M15 | 60000 velas | setups=10 | ~1 min (GitHub Actions run 31504921344)

## A. Regla 7 — pruebas estructurales (sobre setups reales)
- IDs únicos en todo el run: True (40 ids, 40 unicos)
- IDENTITY OK: 10/10 | fallos=0
- LINK OK (parent resoluble + anterior): 10/10 | fallos=0
- CAUSALITY OK (parent declarado == id padre): 10/10 | fallos=0
- Cadena RETURN->SWEEP recorrible: 10/10
- Ciclos detectados: 0

## B. Regla 8 — casos adversariales (modelo)
- Parent FUTURO (idx 5 < 10) rechazado por guarda advance: SI
  mensaje: Expediente.advance: idx=5 < último idx registrado 10 (anti-look-ahead / no reescritura del pasado)
- Parent INEXISTENTE (GHOST): auditor marca CHILD_MISSING (no crashea)
- invalidate() corta el estado: SI (outcome=INVALID)
- Dos expedientes NO comparten identidad: SI

## C. Falsación de A (regla 9 separa I/L/C)
Si LINK/CAUSALITY muestra fallos en setups reales => A FALSADA por trazabilidad.
Si solo IDENTITY falla pero LINK/CAUSALITY OK => A PARCIAL (naming, no linaje).

**VEREDICTO:** A VALIDADA (sobre muestra real): linaje demostrable sin reconstrucción por proximidad.

## D. Qué NO se modificó
- Lógica de decisión: _has_sweep/_has_displacement/_has_bos, thresholds, secuencia, filtros.
- Detectores (detectors/*). Sin ATR/RSI/EMA. Macro/News no usado como filtro.
- Sin WR/PF/edge. Compatibilidad run_sequence_traced: firma intacta (3er elem = expedientes).
