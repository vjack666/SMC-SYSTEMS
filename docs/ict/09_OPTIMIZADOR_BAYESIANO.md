# 09 — Optimizador Bayesiano (para el backtest ICT)

Libro de referencia del proyecto SMC-SYSTEMS. Explica qué es el optimizador
bayesiano, por qué se usa en el backtest, el riesgo de overfitting y cómo se
aplica en nuestra Capa 3 (ict_backtest). Fundamentado en investigación web
(ver Fuentes al final) y contrastado con las decisiones de diseño ya acordadas
en `docs/AVANCES_ICT_BACKTEST_2026-07-10.md`.

---

## 0. Índice de este libro

1. El problema: encontrar la mejor configuración de parámetros
2. Las malas soluciones: Grid Search y Random Search
3. Qué es el optimizador bayesiano (en simple)
4. Cómo funciona por dentro (el modelo surrogate)
5. Por qué sirve para trading (funciones caras, ruidosas, no-convexas)
6. El riesgo central: OVERFITTING
7. La defensa estándar: WALK-FORWARD OPTIMIZATION
8. Librerías: Optuna vs scikit-optimize
9. Aplicación en SMC-SYSTEMS (nuestra Capa 3)
10. Por qué la opción (A) viene antes que la (B)
11. Glosario
12. Fuentes

---

## 1. El problema: encontrar la mejor configuración

Nuestro motor de la Capa 2 (`ict_backtest/sequence.py`) tiene parámetros de
ajuste que hoy están puestos a mano (criterio propio):

- `displace_gap`     → cuántas velas de separación exige entre el displacement
                       y el BOS.
- `bos_gap`          → separación entre el sweep de liquidez y el BOS.
- `require_displacement` → si exige displacement confirmatorio o no.
- `tp_mode`          → cómo calcula el take profit (2R fijo, al swing, etc.).

La pregunta es: ¿CUÁL es la combinación de esos valores que da el mejor
Profit Factor (PF)?

Probar combinaciones a ojo es lento y no garantiza el óptimo. Por eso existe
la optimización de hiperparámetros.

---

## 2. Las malas soluciones: Grid Search y Random Search

**Grid Search (búsqueda en rejilla):** probar TODAS las combinaciones posibles.
Si cada parámetro tiene 10 opciones y tenemos 4 parámetros → 10^4 = 10.000
backtests. Con miles de velas cada uno, esto tarda horrores y quema CPU.

**Random Search (búsqueda aleatoria):** muestrear combinaciones al azar.
Más eficiente que Grid en espacios grandes, pero NO aprende de los resultados:
trata cada backtest como un evento independiente. Pura suerte.

Fuentes coinciden: ambos son "ciegos" — no usan la información de los backtests
ya hechos para elegir el siguiente.

---

## 3. Qué es el optimizador bayesiano (en simple)

Es una forma INTELIGENTE y EFICIENTE de encontrar la mejor configuración de
parámetros SIN probar todas las combinaciones, aprendiendo de cada prueba.

Analogía: buscar el mejor café de una ciudad. En vez de probar todos los
locales (Grid) o locales al azar (Random), vas afinando por dónde huele bien.
Usa teoría de Bayes para actualizar tu "creencia" con cada prueba.

En nuestro caso: afinar la Capa 2 para que el PF>1 sea REAL y no suerte de
pocas muestras.

---

## 4. Cómo funciona por dentro (el modelo surrogate)

El optimizador bayesiano itera y refina su entendimiento de la función objetivo:

1. **Muestras iniciales:** prueba unas pocas combinaciones al azar (backtests).
2. **Modelo surrogate (sustituto):** construye un modelo PROBABILÍSTICO que
   aproxima la función real "parámetros → Profit Factor". Este modelo da una
   PREDICCIÓN y una INCERTIDUMBRE (qué tan seguro está).
   - El método clásico usa un Gaussian Process (GP) como surrogate.
3. **Función de adquisición:** decide la SIGUIENTE combinación equilibrando:
   - *Exploitation* (probar donde el modelo predice alto PF) y
   - *Exploration* (probar donde hay mucha incertidumbre, por si hay un óptimo
     mejor escondido).
4. **Repite** ~50–200 veces en vez de 10.000.

Resultado: llega al óptimo con muchísimas menos evaluaciones caras.

---

## 5. Por qué sirve para trading

La literatura lo justifica: el optimizador bayesiano es ideal para funciones
que son:

- **Caras de evaluar:** correr un backtest completo puede tardar segundos,
  minutos u horas (sobre todo con estrategias complejas o datasets grandes).
- **Ruidosas:** los mercados financieros son inherentemente ruidosos; el PF de
  una configuración puede variar un poco entre corridas.
- **No-convexas:** la relación entre parámetros y rendimiento rara vez es una
  curva suave; hay múltiples óptimos locales, difíciles de encontrar.

El bayesiano está diseñado exactamente para "cajas negras" caras, ruidosas y
no-convexas — que es precisamente lo que es un backtest.

---

## 6. El riesgo central: OVERFITTING

Todas las fuentes coinciden en esto. Si optimás los parámetros SOBRE los mismos
datos con los que luego medís el resultado, el optimizador "memoriza" esos
datos y te entrega una configuración que parece perfecta (PF alto) pero NO
funciona en datos nuevos. Eso es overfitting (sobre-ajuste).

En nuestro proyecto esto es crítico: con solo 11 trades (los que tiene hoy la
Capa 2 en H4), un optimizador bayesiano sobre-ajustaría al instante y nos daría
un PF falso. Por eso el volumen de muestras es requisito previo.

---

## 7. La defensa estándar: WALK-FORWARD OPTIMIZATION

La industria (QuantInsti y otras) usa Walk-Forward Optimization (WFO) para
evitar el overfit:

- En vez de un solo split optimizar→validar, WFO hace ciclos ROLLING:
  1. Optimizás los parámetros en una ventana IN-SAMPLE (ej. 5 años).
  2. Aplicás esos parámetros a la ventana OUT-OF-SAMPLE siguiente (ej. 1 año)
     y registrás el rendimiento REAL en datos nunca vistos.
  3. Corrés la ventana un paso y repetís.
- Así la estrategia se valida en datos verdaderamente nuevos, no en los que se
  optimizó. Refleja mejor el trading real (donde el mercado cambia).

En SMC-SYSTEMS YA TENEMOS la base: `ml/walk_forward.py` existe en el repo.
La Capa 3 debe usar WFO sobre sequence.py para validar sin overfit.

---

## 8. Librerías: Optuna vs scikit-optimize

- **Optuna** (RECOMENDADA, estándar 2025/26):
  - `pip install optuna`.
  - Usa TPE sampler (Tree-structured Parzen Estimator) + pruning (corta trials
    que van mal para ahorrar tiempo).
  - API simple: `study = optuna.create_study(direction="maximize")`,
    `study.optimize(objective, n_trials=N)`. El `objective(trial)` encapsula el
    backtest y devuelve el PF.
  - Madura, activamente mantenida, bien documentada.
- **scikit-optimize** (bayes-opt, Gaussian Process):
  - Más simple conceptualmente, pero MENOS mantenida que Optuna.
  - Útil si se quiere el GP "puro", pero Optuna es la opción segura hoy.

Decisión del proyecto: usar **Optuna** para la Capa 3.

---

## 9. Aplicación en SMC-SYSTEMS (nuestra Capa 3)

Flujo propuesto (a implementar DESPUÉS de la opción A):

```
objective(trial):
    displace_gap       = trial.suggest_int("displace_gap", 1, 10)
    bos_gap            = trial.suggest_int("bos_gap", 1, 10)
    require_displacement = trial.suggest_categorical(..., [True, False])
    tp_mode            = trial.suggest_categorical(..., ["2r", "swing", ...])
    # backtest de sequence.py con esos parámetros
    pf = run_sequence_backtest(params)
    return pf   # Optuna maximiza

study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=100)
# Validación: walk-forward con ml/walk_forward.py sobre ventanas rolling
```

Esto CONFIRMA (no contradice) lo acordado ayer:
"ML = optimizador bayesiano + walk-forward anti-overfit. NO clasificador sobre
señales (frágil, pocas muestras M15)."

---

## 10. Por qué la opción (A) viene antes que la (B)

Orden correcto según la evidencia:

- **(A) Capa 2 en M15:** ganar volumen. M15 tiene ~50k velas (2 años) → cientos
  de secuencias/trades, suficientes para que el optimizador aprenda algo que
  GENERALICE.
- **(B) Capa 3 (Optuna + walk-forward):** solo cuando ya hay volumen. Si la
  metemos sobre 11 trades H4, el bayesiano sobre-ajusta (overfit) y el PF es
  falso.

La web lo dice textual: el overfitting ocurre al optimizar sobre pocas muestras.

---

## 11. Glosario

- **Profit Factor (PF):** ratio ingresos / pérdidas. PF>1 = rentable.
- **Overfitting:** el modelo "memoriza" los datos de entrenamiento y falla con
  datos nuevos.
- **In-sample / Out-of-sample:** datos donde optimizás / datos donde validás.
- **Walk-forward:** validación rolling in-sample→out-of-sample.
- **Surrogate model:** modelo aproximado de la función real, barato de evaluar.
- **Gaussian Process (GP):** modelo probabilístico clásico del surrogate.
- **TPE:** Tree-structured Parzen Estimator, el sampler que usa Optuna.
- **Pruning:** cortar trials que van mal para ahorrar tiempo de cómputo.

---

## 12. Fuentes

- Onepagecode — "Optimizing Trading Strategies with Bayesian Optimization"
  (substack, feb 2026). Explicación de Grid/Random vs Bayes, modelo surrogate,
  riesgo de overfitting.
- QuantInsti (Ajay Pawar) — "Walk-Forward Optimization: How It Works, Its
  Limitations, and Backtesting Implementation" (2025). Base de WFO anti-overfit.
- MachineLearningMastery (Iván Palomares) — "Hyperparameter Optimization with
  Optuna" (abril 2025). API de Optuna, `objective(trial)`, `study.optimize`.

---

> Nota de trazabilidad: este libro se generó a partir de la investigación web
> pedida por Ruben el 2026-07-11, previo a cualquier cambio de código en la
> Capa 3. Estado del repo al escribirlo: main == origin/main (commit 7f06f48),
> ict_backtest/ con Capa 2 (PF 1.132, 11 trades H4). Aún no se implementa
> código de Capa 3.
