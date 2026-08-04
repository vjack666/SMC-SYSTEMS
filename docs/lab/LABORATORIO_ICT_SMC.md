# Laboratorio de Verificación Estructural ICT/SMC

## 1. Qué es

Es un entorno de falsificación empírica del motor SMC-SYSTEMS. No es un backtest comercial ni un optimizador. Es un laboratorio: carga datos reales, corre el motor vela a vela, mide outcomes y registra evidencias. Su única función es responder: **¿el motor hace lo que la tesis dicta?**

---

## 2. Por qué se escribió

### 2.1 Problema original
El motor (`engine/`) implementa la tesis ICT/SMC en código, pero no tenía un entorno desechable que la midiera sin lógica propia. Los primeros backtests (R6) usaban una versión simplificada del motor: solo 2 TFs reales, POI anclado desactivado, sin dealing range ni filtro de régimen. Esos números negativos no probaban que la tesis no tenga edge; probaban que el motor backtesteado era incompleto.

### 2.2 Solución
Crear un laboratorio separado, desechable, que:
- No tenga lógica de decisión ni detección propia.
- Solo haga de reloj vela a vela, llame al motor y mida resultados.
- Permita agregar nuevas mediciones sin tocar el motor.
- Se pueda borrar sin perder nada del motor (`engine/`).

### 2.3 Principio rector
> **El motor es el reflejo de la tesis hecho código. El backtest existe solo para probar el motor.**
> - `engine/` nunca importa `ict_backtest/` ni el laboratorio.
> - El laboratorio puede importar `engine/`.
> - Si el motor tiene todos sus módulos, el laboratorio se borra sin pérdida.

---

## 3. Qué mide

### 3.1 Medición actual: efectividad predictiva BOS/CHOCH (T10)
- **Pregunta**: cuando el motor detecta un BOS/CHOCH, ¿el precio confirma esa ruptura en las próximas `k` velas?
- **Métrica**: `against_hit_pct` = % de eventos contra el sesgo HTF mayor que son confirmados por precio.
- **Baseline**: permutación aleatoria de direcciones (50 permutaciones por TF) para separar señal de ruido browniano.
- **Segmentación**: aligned/against según `compute_htf_bias_series()`.

### 3.2 Medición previa: sesgo HTF (T1-T8)
- **Pregunta**: ¿qué tan disponible está el filtro D1→H4→H1 en datos reales?
- **Métrica**: `aligned_hit_pct` = % de velas donde D1=H4=H1=BULLISH/BEARISH.
- **Hallazgo duro**: en EURUSD 113k M15, `aligned_hit = 0%`. No es bug, es un hecho de este dataset/tramo.

### 3.3 Medición futura
- Sensibilidad a `swing_lookback` y `k`.
- Otros símbolos/tramos donde sí exista alineación.
- Integración con pipeline de sesgo para evaluar BOS/CHOCH bajo bias HTF.

---

## 4. Arquitectura del laboratorio

### 4.1 Directorios
```
C:\Users\v_jac\Desktop\SMC-SYSTEMS/
├── engine/                    # MOTOR — única fuente de decisión
│   ├── bias/
│   │   ├── __init__.py        # expone compute_htf_bias_series()
│   │   └── narrative.py       # HtfBias, compute_htf_bias(), compute_htf_bias_series()
│   └── bos/
│       └── structure.py       # detect_market_structure(), MarketStructure
├── scripts/
│   └── measure_structure_effectiveness.py   # RUNNER del laboratorio
├── tests/                     # Tests unitarios del motor
│   ├── test_engine_bias.py
│   ├── test_engine_bos.py
│   ├── test_sesgo_cable_bias.py
│   ├── test_structure_medicion.py
│   └── test_structure_run.py
├── data/exports/              # Resultados del laboratorio
│   └── effectiveness_113k.json
└── docs/tesis/
    └── HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md  # Documentación de hallazgos
```

### 4.2 Flujo de ejecución
1. **Carga de datos**: el runner carga M15 desde disco y resamplea a H1/H4/D1.
2. **Cálculo de bias**: llama a `compute_htf_bias_series(d1, h4, h1, m15)` del motor.
3. **Detección estructural**: para cada TF, llama a `detect_market_structure(frame, config)` del motor.
4. **Medición**: compara cada BOS/CHOCH contra `bos_level` del motor, no contra high/low del evento.
5. **Baseline**: genera 50 permutaciones de direcciones para estimar ruido.
6. **Salida**: JSON con métricas por TF, baseline, bias_coverage.

### 4.3 Componentes desechables
- `scripts/measure_structure_effectiveness.py`: se puede borrar sin afectar el motor.
- `data/exports/`: resultados, se puede regenerar.
- `docs/tesis/HALLAZGOS_*.md`: documentación de hallazgos.

### 4.4 Componentes NO desechables
- `engine/bias/narrative.py`: motor de sesgo HTF.
- `engine/bos/structure.py`: motor de detección BOS/CHOCH.
- `tests/`: tests unitarios del motor.

---

## 5. Herramientas

### 5.1 Motor
| Archivo | Función |
|---------|---------|
| `engine/bias/narrative.py` | `compute_htf_bias()` / `compute_htf_bias_series()` — calcula bias D1/H4/H1 y lo propaga a H1/M15 |
| `engine/bos/structure.py` | `detect_market_structure()` — detecta BOS/CHOCH, emite `bos_discard_reason`/`choch_discard_reason` |

### 5.2 Runner
| Archivo | Función |
|---------|---------|
| `scripts/measure_structure_effectiveness.py` | Carga datos, resamplea, llama motor, mide outcomes, baseline, imprime JSON |

### 5.3 Tests
| Archivo | Función |
|---------|---------|
| `tests/test_engine_bias.py` | 12 tests — bias HTF, propagación ffill, desempate por tramo |
| `tests/test_engine_bos.py` | 14 tests — BOS/CHOCH, MSS, discard reasons |
| `tests/test_sesgo_cable_bias.py` | 4 tests — cable bias HTF multi-TF |
| `tests/test_structure_medicion.py` | 3 tests — medición de efectividad |
| `tests/test_structure_run.py` | 3 tests — runner end-to-end |

### 5.4 Datos
| Dataset | Barras | Periodo | Uso |
|---------|--------|---------|-----|
| EURUSD M15 | 113.123 | 2022-01 a 2026-07 | Corrida principal 113k |
| EURUSD M15 | 30.000 | subconjunto | Corrida comparativa 30k |

---

## 6. Configuración de la corrida actual

```bash
SMCS_EFFECTIVENESS_MAX_BARS=113123
SMCS_EFFECTIVENESS_K=5
SMCS_EFFECTIVENESS_SWING_LOOKBACK=5
SMCS_EFFECTIVENESS_CONFIRM_BARS=2
PYTHONPATH=. python scripts/measure_structure_effectiveness.py
```

**Parámetros:**
- `k=5`: ventana de confirmación para BOS.
- `swing_lookback=5`: delay mínimo para swings.
- `confirm_bars=2`: cuerpo de confirmación para BOS/CHOCH.
- Dataset: EURUSD M15, ~4.5 años.

---

## 7. Hallazgos actuales

### 7.1 Alineación D1→H4→H1
- `aligned_hit = 0%` en D1/H4/H1/M15 en ambas corridas (30k y 113k).
- **Interpretación**: no es bug, es un hecho de este dataset. EURUSD en este tramo no presenta alineación exacta D1=H4=H1=BULLISH/BEARISH.
- **Causa raíz**: el gate actual exige match exacto de strings; cualquier divergencia cierra el filtro.
- **Implicación**: sin alineación, el filtro HTF no aporta señales `aligned`; todos los eventos caen en `against_hit`.

### 7.2 Efectividad BOS/CHOCH
- **BOS against_hit**: 72-75% en 113k. Estable al escalar de 30k a 113k.
- **CHOCH**: 100% confirmed_against en 113k, sin invalidados. Coincide con baseline aleatorio (1.0).
- **MSS**: reduce eventos (M15 29438→11649) pero 100% en `against`; no genera señales `aligned`.

### 7.3 Baseline
- CHOCH baseline contra = 1.0: el 100% observado no es edge, es ruido permutado.
- BOS baseline contra ≈ 0.72-0.77: comparable al observed, sugiere que el ~72-75% puede ser comportamiento browniano del tramo.

---

## 8. Cómo extender el laboratorio

### 8.1 Agregar un nuevo símbolo
1. Colocar el CSV de M15 en `data/` con columnas `timestamp, open, high, low, close, volume`.
2. Ejecutar:
   ```bash
   SMCS_EFFECTIVENESS_SYMBOL=GBPUSD SMCS_EFFECTIVENESS_MAX_BARS=113123 \
   PYTHONPATH=. python scripts/measure_structure_effectiveness.py
   ```
3. Comparar `aligned_hit_pct` y `against_hit_pct` con EURUSD.

### 8.2 Agregar una nueva métrica
1. Agregar columna en `MarketStructure.frame` desde el motor si es necesario.
2. Modificar `_measure_timeframe()` en el runner para calcularla.
3. Agregar test en `tests/test_structure_medicion.py` o `tests/test_structure_run.py`.

### 8.3 Cambiar parámetros del motor
1. Modificar `StructureConfig` en `engine/bos/structure.py`.
2. Actualizar tests en `tests/test_engine_bos.py`.
3. Ejecutar `pytest` para verificar.
4. Correr laboratorio con nuevos parámetros.

---

## 9. Restricciones y reglas

### 9.1 Separación motor/laboratorio
- **PROHIBIDO**: poner lógica de detección o decisión en el laboratorio.
- **PROHIBIDO**: que `engine/` importe `scripts/` o `ict_backtest/`.
- **OBLIGATORIO**: toda lógica de estrategia vive en `engine/`.

### 9.2 Sin indicadores
- El motor usa solo matemáticas y geometría del mercado.
- Cualquier indicador/EMA/RSI/ATR en el motor es sospechoso y debe justificarse contra la tesis.

### 9.3 Datos
- Usar solo datos proporcionados o descargados por el flujo definido en el repo.
- No hardcodear rutas absolutas.

### 9.4 Tests
- Todos los tests deben pasar antes de declarar tarea completada.
- Tests unitarios del motor: 36/36 verde.

---

## 10. Estado actual (2026-08-04)

| Componente | Estado |
|------------|--------|
| Motor bias HTF | ✅ M1-M2-M7 cerrados |
| Motor BOS/CHOCH | ✅ M3-M6 cerrados |
| Runner efectividad | ✅ M4-M5-M6 cerrados |
| Tests motor | ✅ 36/36 passed |
| Corrida 30k M15 | ✅ Completada |
| Corrida 113k M15 | ✅ Completada |
| Documentación | ✅ Actualizada |
| Commit | ✅ `2799254` |

---

## 11. Próximos pasos

1. **Relajar definición de alineación** en `engine/bias/narrative.py`:
   - Actual: `aligned = d1 == h4 == h1 and d1 != NEUTRAL`
   - Propuesta: `aligned = al menos 2/3 TFs no NEUTRAL y sin contradicción`
   - Objetivo: activar el filtro HTF en datasets donde D1/H4/H1 no son exactamente iguales pero no se contradicen.

2. **Probar con otro símbolo** donde sí exista alineación (ej: GBPUSD en tramo tendencial).

3. **Evaluar sensibilidad** a `swing_lookback` y `k` con dataset completo.

4. **Integrar medición** en flujo de backtest del sesgo para evaluar BOS/CHOCH bajo bias HTF.

---

## 12. Cómo citar este documento

```
SMC-SYSTEMS (2026). Laboratorio de Verificación Estructural ICT/SMC.
docs/lab/LABORATORIO_ICT_SMC.md. Repositorio: C:\Users\v_jac\Desktop\SMC-SYSTEMS
```
