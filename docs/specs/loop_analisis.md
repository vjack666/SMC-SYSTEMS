# SDD — Loop de Análisis EURUSD (sin operar)

Rutina automática de análisis técnico + noticias + semáforo FundedNext.
NO ejecuta trades: solo entrega el mapa al trader cada 5 minutos en horario
de trading. Es un "observador", no un bot.

---

## 1. REQUIREMENTS (qué debe hacer — EARS)

**R1:** WHEN la hora local sea >= 08:00 Ecuador (13:00 UTC) y < 11:00 Ecuador
(16:00 UTC) de un día de trading, THE SYSTEM SHALL correr el ciclo de análisis.

**R2:** IF la hora está fuera de la ventana THE SYSTEM SHALL permanecer inactivo
y no consumir datos (solo esperar hasta el próximo día).

**R3:** DURANTE la ventana, EVERY 5 minutos THE SYSTEM SHALL:
  (a) actualizar datos MT5 en vivo (EURUSD D1/H4/M15);
  (b) regenerar la ficha técnica (rutina_eurusd.py);
  (c) regenerar el informe combinado (informe_eurusd.py);
  (d) regenerar el semáforo (semaforo_fundednext.py).

**R4:** THE SYSTEM SHALL guardar cada ciclo en docs/diario/ con timestamp,
para revisión del trader.

**R5:** THE SYSTEM SHALL mostrar en consola el semáforo (VERDE/AMARILLO/ROJO)
y el sesgo del día en cada ciclo, como resumen rápido.

**R6:** IF la actualización MT5 falla (terminal no logueado) THE SYSTEM SHALL
usar la última data cacheada y marcar el ciclo con ADVERTENCIA, sin detener el loop.

**R7:** IF el RSS de noticias da error (429/sin red) THE SYSTEM SHALL usar el
cache local de noticias y continuar.

**R8:** THE SYSTEM SHALL poder detenerse con Ctrl+C o señal, cerrando limpio.

**R9:** THE SYSTEM SHALL correr con C:\Python314\python.exe (MT5 real), no el
venv smc_probe (stub MT5).

**R10:** THE SYSTEM SHALL respetar los límites FundedNext (DLL 4% / MLL 8% /
riesgo ≤3%) mostrados en el semáforo; en ningún caso sugiere tamaño de lote
mayor a riesgo 1% por defecto.

**R11:** THE SYSTEM SHALL apagarse solo los fines de semana: viernes desde las
15:00 Ecuador, todo sábado y todo domingo. No corre ni aunque la compu esté
prendida. Reanuda al prender la compu el lunes (arranque con Windows vía
start_hermes_session.ps1).

---

## 2. DESIGN (cómo hacerlo)

### Arquitectura
Un orquestador `scripts/loop_analisis.py` que:

1. Calcula la ventana local (Ecuador = UTC-5). Usa `datetime` + `zoneinfo`
   (Python 3.14 trae zonas; o `pytz` si hace falta).
2. Bucle principal `while True`:
   - Si fuera de ventana: `sleep` hasta las 08:00 del próximo día, informa.
   - Si en ventana: corre un ciclo, luego `sleep(300)` (5 min).
3. Cada ciclo llama, en orden:
   - `update_mt5_data.py --symbols EURUSD --tfs D1,H4,M15` (actualiza data/raw)
   - `rutina_eurusd.py --save`
   - `informe_eurusd.py --save`
   - `semaforo_fundednext.py`  (imprime el veredicto)
4. Captura excepciones por paso (R6, R7): si un paso falla, lo marca y sigue.

### Reuso (tu regla: no duplicar)
- NO se crea nuevo detector: se llaman los scripts ya existentes y verificados.
- NO se crea nuevo fetcher de noticias: news_report.py ya usa el RSS oficial.
- El semáforo ya existe y se invoca directo.

### Archivos
- Nuevo: `scripts/loop_analisis.py` (orquestador, ~120 líneas)
- Reusados: update_mt5_data.py, rutina_eurusd.py, informe_eurusd.py,
  semaforo_fundednext.py, news_report.py
- Salida: docs/diario/ (ya existe)

### Zona horaria
Ecuador = UTC-5 (sin DST). 08:00 Ecuador = 13:00 UTC. El loop calcula
`now_ecuador` y compara con 8 y 11.

### Señal de parada
`try/except KeyboardInterrupt` → imprime "Loop detenido" y sale con 0.

---

## 3. TASKS (checklist)

- [x] T1: Crear `scripts/loop_analisis.py` con cálculo de ventana Ecuador.
- [x] T2: Bucle principal con sleep(300) y espera fuera de ventana.
- [x] T3: Función `run_cycle()` que invoca los 4 scripts en orden.
- [x] T4: Captura de errores por paso (MT5 caído → cache; RSS 429 → cache).
- [x] T5: Imprimir semáforo + sesgo como resumen por ciclo.
- [x] T6: Guardar cada ciclo en docs/diario/ con timestamp.
- [x] T7: Manejo de Ctrl+C (parada limpia).
- [x] T8: Usar C:\Python314\python.exe (verificar shebang / documentar).
- [x] T9: Probar 1 ciclo manual (fuera de ventana y dentro si es horario).
- [x] T10: Documentar en RUTINA_EURUSD.md la sección "Loop automático".

### Criterio de done
El loop corre dentro de la ventana 8–11 Ecuador, cada 5 min, actualiza MT5,
regenera ficha+informe+semáforo, guarda en diario, y se detiene con Ctrl+C
sin errores. Verificado con al menos 1 ciclo real en horario (o simulado).

---

## 5. FUTURO (Fase 2): Paper Híbrido / Shadow Mode — entrenamiento ML

Acordado con el trader: el loop puede evolucionar a un "modo sombra" que
alimenta el filtro ML sin riesgo real.

### Concepto (palabras simples)
El loop muestra el setup (ficha + semáforo). El trader decide operar o no.
Si NO opera (o no está), el sistema SIGUE la operación en papel: anota qué
hubiera pasado con ese setup a los N minutos. Ese resultado se guarda como
muestra etiquetada (features del setup → ganó/perdió).

### Por qué importa
El filtro ML actual tiene AUC ~0.55 (casi azar) por falta de datos etiquetados
(91 trades). El shadow mode genera miles de muestras reales "setup → resultado"
sin tocar dinero real. Con semanas de datos se reentrena el filtro.

### Reglas del shadow mode
- NUNCA abre órdenes en MT5 real (respeta "sin bot").
- Guarda snapshot de detectores en el momento del setup (features).
- Revisa el resultado N minutos/barras después y etiqueta.
- Acumula dataset en data/shadow/ para reentrenamiento futuro.

### Fuera de alcance de la Fase 1
Se implementa solo después de que el loop A+C esté estable y el trader lo
apruebe. Los detalles (N minutos, qué features, cómo reentrenar) se discuten
en su momento.
