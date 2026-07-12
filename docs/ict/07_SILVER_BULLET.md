# ICT — Silver Bullet (Modelo intradía / scalping)

> Tesis (RFC-001 / ADR-021): Teoría → Práctica del trader → Algoritmo →
> Código SMC-SYSTEMS → Auditoría → Resultados medidos. Fuente de verdad: el
> código y las auditorías del repo.

## 1. Teoría
Modelo intradía basado en TIEMPO que combina **liquidez + FVG dentro de una
killzone**. Es el setup más directo para operar en el día; ideal para scalping
(M1/M3/M5). El precio debe: barrer liquidez → dejar FVG → ofrecer entrada en el
retroceso, todo DENTRO de la ventana horaria.

## 2. Práctica del trader (uso real)
1. Marcar BSL/SSL en el gráfico.
2. Esperar **sweep** de SSL (long) o BSL (short) dentro de la killzone.
3. Tras el sweep, esperar un **FVG** rápido (desplazamiento).
4. Entrar en el retroceso al FVG.

**Gestión (1:2 mínimo, regla Stellar Lite $5K):**
- **Long:** SL bajo el FVG alcista o en SSL; TP en BSL (1:2 o liquidez opuesta).
- **Short:** SL sobre el FVG bajista o en BSL; TP en SSL.

**Sesgo del día (filtro de ruido):** si el sesgo D1/H4 es alcista, solo buscar
setups alcistas; si bajista, solo bajistas. Es justo lo que hace
`rutina_eurusd.py`.

**Mejor TF:** M1/M3/M5 (ventanas de 1h). El contexto (sesgo) se define en H4/D1.

## 3. Algoritmo (detección automática)
- El sweep se detecta como en `05_LIQUIDEZ` (ruptura + reversión).
- El FVG como en `03_FVG` (`shift(2)` sobre velas cerradas, sin look-ahead).
- La killzone es una máscara horaria sobre la columna `time` del frame.
- Riesgo: las horas de la killzone deben coincidir con la zona horaria del
  broker/MT5; un desfase de zona cambia qué velas entran en la ventana.

## 4. Código SMC-SYSTEMS (implementación real)
- **Killzones:** `detectors/killzones.py` → `detect_killzones()`
  - Sesiones (horas LOCALES del chart, asumiendo `time` ya en zona broker):
    NY 07:00-09:00, LDN_OPEN 07:00-10:00, LDN_CLOSE 15:00-17:00, ASIA 10:00-14:00.
  - Agrega columna `kz` (etiqueta de sesión por vela) para pintar la banda de
    fondo. **Nota:** estas horas locales difieren de las "ET" del mentorsip
    (London 03:00-04:00 ET, NY AM 10:00-11:00 ET); el código usa la zona del
    broker, no ET. Ver Sección 5.
- **FVG:** `detectors/fvg.py`. **Liquidez:** `detectors/liquidity.py`.
- **Señal en vivo:** la pestaña Principal sugiere "Silver Bullet" cuando hay
  sweep + FVG dentro de killzone y el sesgo del día coincide con la dirección.
- **Rutina:** `scripts/rutina_eurusd.py` aplica el sesgo del día para filtrar el
  lado (solo long si sesgo alcista).

## 5. Auditoría (cómo los hallazgos afectaron la implementación)
- **Zona horaria (hallazgo de implementación):** el libro base cita horas ET del
  mentorsip; el código usa horas locales del broker (MT5). No es un bug de
  lógica, pero el operador debe saber que la "killzone" que pinta el sistema es
  la del broker, no la ET. Documentado para evitar confusión al leer señales.
- **#1 Look-ahead:** el FVG del Silver Bullet se calcula sin fuga (`shift(2)`);
  el sweep usa close ya cerrado. El único cuidado es no marcar la entrada en la
  misma vela del sweep (esperar el FVG posterior).
- **#2 CHOCH real:** el Silver Bullet a veces se apoya en CHoCH para confirmar;
  al corregir CHOCH, la dirección es genuina.

## 6. Resultados medidos
- PF Capa 2: **2.003 → 1.548** tras #1/#2. Silver Bullet participa de la cadena
  (sweep → FVG → entrada).
- Walk-forward OOS (4 folds, EURUSD M15, SIN costos): PF prom **3.389 ± 2.303**,
  21 trades OOS. El modelo intradía (que incluye Silver Bullet vía killzone+FVG)
  está en la cadena; falta aislar su contribución con costos (fix #4 `--cost`, no
  aplicado).

## En resumen
Silver Bullet es el setup intradía: sweep de liquidez + FVG, dentro de killzone,
alineado al sesgo del día. En SMC-SYSTEMS `killzones.py` marca la ventana (horas
broker), `fvg.py` el desplazamiento y `rutina_eurusd.py` filtra por sesgo. La
única salvedad documentada es que las horas del sistema son locales del broker,
no ET del mentorsip.
