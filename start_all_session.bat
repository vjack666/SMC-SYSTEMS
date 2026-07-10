@echo off
REM =====================================================================
REM  SMC-SYSTEMS - Arranque completo de sesion (SILENCIOSO, sin consola)
REM  Al encender Windows, abre JUNTOS (todo oculto, sin pantalla negra):
REM    1) Terminal MT5 (FundedNext, logueado)
REM    2) Loop de analisis EURUSD (observador 24/7, sin bot)
REM    3) Vigilante de riesgo (kill-switch, SOLO CIERRA al 2%/4%)
REM    4) App del observador (PySide6 -> pestaña Lab Setup)
REM    5) Hermes (tu asistente) - opcional
REM
REM  Nota: este .bat corre OCULTO via el .vbs de Inicio, asi no salta
REM  la ventana de consola. No uses doble-clic directo si queres silencio.
REM =====================================================================

set ROOT=C:\Users\v_jac\Desktop\SMC-SYSTEMS
set PY=C:\Python314\python.exe
set PYW=C:\Python314\pythonw.exe
set MT5=C:\Program Files\FundedNext MT5 Terminal\terminal64.exe

cd /d "%ROOT%"

REM ---- 1) MT5 (si no esta corriendo) ----
tasklist | find /I "terminal64.exe" >nul 2>&1
if errorlevel 1 (
    if exist "%MT5%" (start "" "%MT5%")
)

REM ---- 2) Loop de analisis (SIEMPRE ACTIVO 24/7) ----
REM Usa pythonw.exe (sin consola) para que NO salte ventana negra.
tasklist | find /I "loop_analisis.py" >nul 2>&1
if errorlevel 1 (
    start "" /min "%PYW%" "%ROOT%\scripts\loop_analisis.py"
)

REM ---- 3) Vigilante de riesgo (SOLO CIERRA) ----
REM Usa pythonw.exe (sin consola) para que NO salte ventana negra.
tasklist | find /I "vigilante_riesgo.py" >nul 2>&1
if errorlevel 1 (
    start "" /min "%PYW%" "%ROOT%\scripts\vigilante_riesgo.py"
)

REM ---- 4) App del observador (sin consola negra) ----
tasklist | find /I "run_app.py" >nul 2>&1
if errorlevel 1 (
    start "" "%PYW%" "%ROOT%\run_app.py"
)

REM ---- 5) Hermes (DESACTIVADO AQUI: evita 2da ventana de Hermes) ----
REM  El Hermes se prende en start_hermes_session.ps1 (unico punto de inicio),
REM  con un lapse de 3 min antes de iniciarlo. Si lo queres tambien por aca,
REM  quita el REM de las siguientes lineas:
REM
REM  tasklist /V /FI "IMAGENAME eq cmd.exe" 2>nul | find /I "HermesSMC" >nul 2>&1
REM  if errorlevel 1 (
REM      where hermes >nul 2>&1
REM      if not errorlevel 1 (
REM          start "HermesSMC" cmd /min /k "hermes"
REM      )
REM  )

exit /b
