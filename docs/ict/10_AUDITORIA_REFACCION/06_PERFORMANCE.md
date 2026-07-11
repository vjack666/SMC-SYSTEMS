# Tema 06 — PERFORMANCE (#6, Medio)

## Hallazgo
~8 min para procesar 50k velas (un símbolo, un TF). El loop de `sequence.py`
es vela-a-vela en Python puro (sin vectorizar). La corrida Optuna con 12
trials tardó ~129 min. Si se sube a 30-60 trials o varios símbolos/TFs, el
cuello de botella se vuelve bloqueante.

## Confirmación
Ya autodetectado por el equipo ("revisar el cuello de botella de retorno al
cuadro"). Confirmado empíricamente: la fase [2/3] (run_sequence sobre 50k
velas) es la que domina el tiempo.

## Acciones (fuera de scope estricto de la auditoría, pero anotadas)
1. Cachear resultados por ventana de walk-forward (no re-calcular market
   structure en cada trial — ya se hace en `main()` de optimize.py, pero el
   `run_sequence` interno re-itera).
2. Vectorizar `_touches_zone` / `BOS_DONE` con máscaras numpy donde sea
   factible sin romper la memoria de estado.
3. Para Optuna con muchos trials: usar `n_jobs>1` (el objective es por trial,
   paralelizable).

Nota: NO se vectoriza en esta refacción (riesgo de romper la lógica
event-driven). Se documenta para la siguiente fase.
