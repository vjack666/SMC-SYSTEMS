# Agente Trader Humano — Filosofía del sistema

## 1. Cambio de paradigma

El sistema dejó de ser una máquina que busca señales.
Ahora es un **modelo cognitivo** que construye, evalúa y destruye hipótesis.

No piensa:
> "Voy a comprar EURUSD."

Piensa:
> "Creo que EURUSD podría rebotar desde este POI."

Esa frase es una **hipótesis**.
Tiene un ciclo de vida.
Tiene evidencia a favor y en contra.
Puede nacer, madurar, fortalecerse, invalidarse o archivarse.

El objetivo del sistema es construir, fortalecer o invalidar hipótesis de trading hasta que exista evidencia suficiente para tomar una decisión o descartarla.

---

## 2. El protagonista

Antes el protagonista era el par (EURUSD).
Después fue el activo.
Ahora el protagonista es la **hipótesis**.

Una hipótesis no es una orden pendiente.
Es una creencia provisional sobre el comportamiento del precio.
Vive mientras hay evidencia que la sostenga.
Muere cuando la evidencia la contradice.

Ejemplo:
- Nace: "El precio respetará este FVG."
- Madura: "El precio entró al POI y respetó el 50%."
- Se fortalece: "Se formó un BOS en H1 en la dirección esperada."
- Se invalida: "El precio cerró por debajo del POI sin reacción."
- Muere: se ARCHIVA y se genera una nueva hipótesis.

---

## 3. Arquitectura cognitiva

El sistema se organiza como una empresa, no como una máquina de señales.

### 3.1 Roles

| Rol | Responsabilidad | Analogía humana |
|-----|----------------|-----------------|
| Administrador | Crea el expediente, asigna recursos, define alcance | Gerente de proyecto |
| Vigilantes | Observan un aspecto específico y emiten veredicto | Analistas especialistas |
| Orquestador | Integra todos los veredictos, calcula confianza, decide | Trader principal |
| Expediente | Almacena la historia completa de la hipótesis | Archivo de caso |

### 3.2 Pisos

Cada piso responde una pregunta diferente.
No agrega condiciones arbitrarias; agrega **evidencia**.

| Piso | Pregunta | Tipo de evidencia |
|------|----------|-------------------|
| 1 | ¿Existe una zona válida? | Existencia / geometría |
| 2 | ¿Llegó el precio a la zona? | Proximidad / tiempo |
| 3 | ¿La está respetando? | Comportamiento / reacción |
| 4 | ¿Existe intención de giro? | Estructura / momentum |
| 5 | ¿Ese giro tiene calidad? | Confluencia / contexto |
| 6 | ¿El precio confirmó la intención? | Ejecución / resultado |

Cada vigilante emite:
- **SI**: evidencia positiva
- **NO**: evidencia negativa
- **SIGUE**: evidencia insuficiente, necesita más tiempo
- **RETROCEDE**: evidencia previa ahora es negativa

El orquestador no suma votos.
Evalúa si la evidencia acumulada es suficiente.

---

## 4. Ciclo de vida de la hipótesis

### 4.1 Estados

| Estado | Significado | Acción |
|--------|-------------|--------|
| VIVA | Acaba de nacer, esperando primeros datos | Asignar vigilantes |
| MADURANDO | Tiene evidencia parcial, está en observación | Continuar recolección |
| FORTALECIDA | Evidencia positiva supera umbral | Preparar decisión |
| INVALIDADA | Evidencia negativa supera umbral | Cerrar, no operar |
| CONTRATADA | Hay evidencia conflictiva que anula la hipótesis | Evaluar nueva hipótesis |
| ARCHIVADA | Ciclo terminado, se aprendió algo | Guardar en historial |

### 4.2 Transiciones

```
NACE → VIVA
  ↓
MADURANDO
  ↓
FORTALECIDA ←→ CONTRATADA
  ↓
INVALIDADA
  ↓
ARCHIVADA
```

Una hipótesis puede saltar de MADURANDO a INVALIDADA directamente.
No tiene que pasar por todos los estados.
El sistema no fuerza permanencia; fuerza honestidad epistémica.

### 4.3 Ejemplo práctico

```
Hipótesis #381 | CALL | POI FVG H4 | Estado: VIVA
  ↓
Piso 2: SIGUE → precio no ha llegado aún
  ↓
Piso 2: SI → precio entró al POI
  ↓
Piso 3: SIGUE → esperando reacción
  ↓
Piso 3: SI → respetó el 50%
  ↓
Piso 4: SI → BOS alcista en H1
  ↓
Estado: FORTALECIDA
  ↓
Piso 5: NO → divergencia bajista en RSI
  ↓
Estado: CONTRATADA
  ↓
Piso 6: NO → precio cerró fuera del POI
  ↓
Estado: INVALIDADA
  ↓
ARCHIVADA → nueva hipótesis: "Rebote desde este otro POI"
```

---

## 5. Confianza dinámica

### 5.1 Problema de la confianza fija

Un valor como `confidence = 0.65` es estático.
No refleja cómo razona un trader humano.

Un humano no dice:
> "Tengo 65% de confianza y lo mantengo durante 2 horas."

Un humano dice:
> "Al principio era 40%, pero el BOS me subió a 70%. Después la divergencia me bajó a 50%. Finalmente el cierre fuera del POI me llevó a 0%."

### 5.2 Solución: confianza dinámica

La confianza **nunca es fija**.
Cada vigilante aporta evidencia positiva o negativa.
El orquestador recalcula continuamente la confianza de la hipótesis.

```
Confianza = f(evidencia_positiva, evidencia_negativa, contexto)
```

No es un promedio simple.
Es una función que considera:
- Peso del vigilante (no todos los pisos valen igual)
- Frescura de la evidencia (la evidencia reciente pesa más)
- Consistencia (una evidencia que se repite vale más)

### 5.3 Ejemplo de evolución

| Momento | Vigilante | Veredicto | Confianza |
|---------|-----------|-----------|-----------|
| 10:00 | Piso 2 | SIGUE | 40% |
| 10:15 | Piso 2 | SI | 55% |
| 10:30 | Piso 3 | SI | 70% |
| 10:45 | Piso 4 | SI | 80% |
| 11:00 | Piso 5 | NO | 60% |
| 11:15 | Piso 6 | NO | 30% |
| 11:30 | Piso 3 | RETROCEDE | 10% |
| 11:45 | — | INVALIDADA | 0% |

---

## 6. El expediente

### 6.1 Estructura

El expediente no almacena indicadores.
Almacena **evidencia acumulada**.

```
Hipótesis #381
  ├── timestamp_creacion: 2026-08-04T10:00:00Z
  ├── estado: VIVA → MADURANDO → FORTALECIDA → INVALIDADA → ARCHIVADA
  ├── símbolo: EURUSD
  ├── dirección: CALL
  ├── ancla: FVG H4 [1.0850-1.0870]
  ├── vigilantes:
  │   ├── Piso 2: SI @ 10:15 (entrada al POI)
  │   ├── Piso 3: SI @ 10:30 (respeto 50%)
  │   ├── Piso 4: SI @ 10:45 (BOS H1)
  │   ├── Piso 5: NO @ 11:00 (divergencia RSI)
  │   └── Piso 6: NO @ 11:15 (cierre fuera)
  ├── confianza_historial: [0.40, 0.55, 0.70, 0.80, 0.60, 0.30, 0.10, 0.00]
  ├── motivo_invalidez: "Piso 5 y 6 reportaron evidencia negativa"
  └── leccion: "En tendencia fuerte, divergencias en H1 tienen más peso que estructura H4"
```

### 6.2 Propósito

1. **Entrenamiento ML**: el modelo entrena sobre la evolución de la hipótesis, no sobre snapshots estáticos.
2. **Auditoría**: se puede reconstruir cualquier decisión.
3. **Mejora continua**: cada hipótesis archivada deja una lección.

---

## 7. Filosofía principal

> Cada piso no agrega una condición; agrega evidencia a favor o en contra de una hipótesis.
> El expediente no almacena indicadores, almacena evidencia acumulada.
> El orquestador no busca una señal perfecta; evalúa si la evidencia reunida es suficiente para actuar.

### 7.1 Implicaciones

- **No existe la señal perfecta**. Solo existe evidencia suficiente.
- **No existe el 100% de confianza**. Solo existe confianza por encima del umbral operativo.
- **No existe la hipótesis eterna**. Toda hipótesis muere; lo importante es qué aprendimos de ella.
- **No existe el trading sin pérdida de hipótesis**. Un trader profesional invalida muchas más hipótesis de las que opera.

### 7.2 Diferencia con enfoques clásicos

| Enfoque clásico | Este sistema |
|-----------------|--------------|
| Busca señal perfecta | Evalúa evidencia acumulada |
| Confianza fija | Confianza dinámica |
| Orden pendiente | Hipótesis viva |
| Acierto/error | Construcción/Destrucción de conocimiento |
| Snapshots estáticos | Evolución temporal |

---

## 8. Para qué sirve este documento

1. **Para la IA**: define la ontología del sistema (qué es una hipótesis, qué es evidencia, qué es un expediente).
2. **Para el desarrollador**: guía de diseño cognitivo, no solo técnico.
3. **Para el trader**: especificación del comportamiento esperado del sistema.
4. **Para el ML**: define el formato de entrada (evidencia temporal, no vectores estáticos).

---

## 9. Estado actual

| Concepto | Estado |
|----------|--------|
| Hipótesis como protagonista | ✅ Filosofía definida |
| Ciclo de vida | ✅ Estados y transiciones documentados |
| Confianza dinámica | ✅ Principio definido, pendiente implementación |
| Expediente | ✅ Estructura documentada, pendiente implementación |
| Pisos como evidencia | ✅ Filosofía definida, implementación parcial |
| Orquestador como evaluador | ✅ Filosofía definida, implementación parcial |

---

## 10. Próximos pasos

1. Implementar estados de hipótesis en el motor.
2. Implementar confianza dinámica con pesos por vigilante y frescura temporal.
3. Implementar expediente completo con historial de veredictos.
4. Entrenar modelo ML sobre secuencias de evidencia, no snapshots.
5. Documentar lecciones aprendidas de cada hipótesis archivada.
