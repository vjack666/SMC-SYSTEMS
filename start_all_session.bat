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
set MT5=C:\Program Files\MetaTrader 5\terminal64.exe

cd /d "%ROOT%"

REM ---- 1) MT5 (si no esta corriendo) ----
tasklist | find /I "terminal64.exe" >nul 2>&1
if errorlevel 1 (
    if exist "%MT5%" (start "" "%MT5%")
)

REM ---- 2) Loop de analisis (SIEMPRE ACTIVO 24/7) ----
tasklist | find /I "loop_analisis.py" >nul 2>&1
if errorlevel 1 (
    start "" /min "%PY%" "%ROOT%\scripts\loop_analisis.py"
)

REM ---- 3) Vigilante de riesgo (SOLO CIERRA) ----
tasklist | find /I "vigilante_riesgo.py" >nul 2>&1
if errorlevel 1 (
    start "" /min "%PY%" "%ROOT%\scripts\vigilante_riesgo.py"
)

REM ---- 4) App del observador (sin consola negra) ----
tasklist | find /I "run_app.py" >nul 2>&1
if errorlevel 1 (
    start "" "%PYW%" "%ROOT%\run_app.py"
)

REM ---- 5) Hermes (opcional, comenta si no queres) ----
REM  Solo abre Hermes si NO hay ya una ventana Hermes abierta.
REM  Se identifica por el titulo unico "HermesSMC" de la ventana cmd.
tasklist /V /FI "IMAGENAME eq cmd.exe" 2>nul | find /I "HermesSMC" >nul 2>&1
if errorlevel 1 (
    where hermes >nul 2>&1
    if not errorlevel 1 (
        start "HermesSMC" cmd /min /k "hermes"
    )
)

exit /b
