# SDD — Alertas locales (Windows) para la rutina EURUSD

El loop ya corre y te da el mapa. Esto agrega AVISOS que se disparan solos
cuando hay algo que mirar, para que no tengas que estar clavado en la pantalla.

---

## 1. REQUIREMENTS

**R1:** WHEN el semáforo pase a VERDE, THE SYSTEM SHALL mostrar un popup de
Windows + sonido, con el sesgo del día.

**R2:** IF aparece una NOTICIA ROJA (evento High USD/EUR en ventana), THE
SYSTEM SHALL alertar inmediatamente (popup + sonido), incluso fuera de que el
semáforo esté VERDE.

**R3:** WHEN el precio toque una zona de entrada (OB o FVG relevante del D1/H4/
M15), THE SYSTEM SHALL alertar "precio en zona X" (popup + sonido).

**R4:** THE SYSTEM SHALL usar SOLO notificación local de Windows (popup +
beep). NO requiere Telegram, tokens, ni instalación de paquetes.

**R5:** THE SYSTEM SHALL evitar spam: una misma condición no alerta más de 1 vez
por ciclo (cada 5 min máx 1 popup por tipo).

**R6:** THE SYSTEM SHALL respetar la ventana de trading. Fuera de ella, NO alerta
(excepto noticia roja, que es 24h).

**R7:** THE SYSTEM SHALL poder desactivarse con flag --no-alert si el trader no
quiere popups.

---

## 2. DESIGN

### Mecanismo (cero dependencias)
- Popup: `powershell` llama a un message box .NET (System.Windows.Forms) — viene
  con Windows, no se instala nada.
- Sonido: beep vía `[console]::beep` (PowerShell) o `winsound.Beep` (Python).
- Fallback: si el popup falla, escribe la alerta en `logs/alertas.log`.

### Integración en el loop
`loop_analisis.py` tras cada `run_cycle()` evalúa:
- veredicto del semáforo (ya lo extrae) → si VERDE, alerta.
- noticia roja (del informe) → si hay, alerta.
- precio actual vs zonas OB/FVG de la ficha → si dentro, alerta.

Se guarda estado por ciclo para no repetir (R5).

### Ventana
Se propone cambiar inicio de 08:00 a 07:00 Ecuador (el trader opera desde las 7).
Confirmar.

### Archivos
- Nuevo: `scripts/alertas.py` (funciones `popup(titulo, msg)`, `beep()`).
- Modifica: `loop_analisis.py` (llama alertas tras ciclo).
- Salida: `logs/alertas.log`.

---

## 3. TASKS

- [x] T1: Crear `scripts/alertas.py` con `popup()` y `beep()` (sin deps).
- [x] T2: En `loop_analisis.py`, tras ciclo, evaluar VERDE / roja / precio-en-zona.
- [x] T3: Evitar spam (AMARILLO solo log, VERDE/roja popup 1 vez por ciclo).
- [x] T4: Flag `--no-alert` para desactivar.
- [x] T5: Fuera de ventana: solo alerta roja (R6).
- [x] T6: Ventana ajustada a 07:00-20:00 Ecuador (siempre activo, sin dormir).
- [x] T7: Probar popup real en Windows + sonido.
- [x] T8: Documentar en RUTINA_EURUSD.md sección "Alertas".
- [x] T9: Loop arranca con Windows (Startup via start_hermes_session.ps1).

---

## 4. FUERA DE ALCANCE
- Telegram / Discord (se puede añadir después con token, pero hoy local).
- Ejecución de órdenes: la alerta NO opera, solo avisa.
