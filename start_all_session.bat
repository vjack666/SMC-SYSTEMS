@echo off
REM =====================================================================
REM  SMC-SYSTEMS — Arranque completo de sesion (TODO EN UNO)
REM  Al encender Windows, abre JUNTOS:
REM    1) Terminal MT5 (FundedNext, logueado)
REM    2) Loop de analisis EURUSD (observador 24/7, sin bot)
REM    3) Vigilante de riesgo (kill-switch, SOLO CIERRA al 2%/4%)
REM    4) App del observador (PySide6 -> pestaña Lab Setup)
REM    5) Hermes (tu asistente)  -- opcional, comentalo si no queres
REM
REM  Como usarlo:
REM    - Doble clic a este .bat, o
REM    - Acceso directo a este .bat en la carpeta INICIO de Windows:
REM      C:\Users\v_jac\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup
REM =====================================================================

set ROOT=C:\Users\v_jac\Desktop\SMC-SYSTEMS
set PY=C:\Python314\python.exe
set PYW=C:\Python314\pythonw.exe
set MT5=C:\Program Files\MetaTrader 5\terminal64.exe

cd /d "%ROOT%"

echo ====================================================================
echo  SMC-SYSTEMS — encendiendo sesion completa
echo ====================================================================

REM ---- 1) MT5 (si no esta corriendo) ----
echo [1/5] MT5 FundedNext...
tasklist | find /I "terminal64.exe" >nul 2>&1
if errorlevel 1 (
    if exist "%MT5%" (
        start "" "%MT5%"
        echo       MT5 abierto.
    ) else (
        echo       AVISO: no encontre MT5 en %MT5%
    )
) else (
    echo       MT5 ya estaba corriendo.
)

REM ---- 2) Loop de analisis (background, SIEMPRE ACTIVO 24/7) ----
echo [2/5] Loop de analisis EURUSD...
tasklist | find /I "loop_analisis.py" >nul 2>&1
if errorlevel 1 (
    start "" /min "%PY%" "%ROOT%\scripts\loop_analisis.py"
    echo       Loop encendido (cada 5 min, alertas popup+sonido).
) else (
    echo       Loop ya corria.
)

REM ---- 3) Vigilante de riesgo (background, SOLO CIERRA) ----
echo [3/5] Vigilante de riesgo...
tasklist | find /I "vigilante_riesgo.py" >nul 2>&1
if errorlevel 1 (
    start "" /min "%PY%" "%ROOT%\scripts\vigilante_riesgo.py"
    echo       Vigilante encendido (cierra TODO al 2%%/4%% flotante).
) else (
    echo       Vigilante ya corria.
)

REM ---- 4) App del observador (PySide6, sin consola negra) ----
echo [4/5] App del observador (pestaña Lab Setup)...
tasklist | find /I "run_app.py" >nul 2>&1
if errorlevel 1 (
    start "" "%PYW%" "%ROOT%\run_app.py"
    echo       App abierta.
) else (
    echo       App ya estaba abierta.
)

REM ---- 5) Hermes (tu asistente) ----
echo [5/5] Hermes...
where hermes >nul 2>&1
if not errorlevel 1 (
    start "" cmd /k "hermes"
    echo       Hermes abierto en terminal.
) else (
    echo       Hermes no disponible en PATH (lo podes abrir despues).
)

echo ====================================================================
echo  Listo. MT5 + Loop + Vigilante + App + Hermes corriendo.
echo  El loop vuelve a arrancar solo cada vez que enciendas la compu.
echo ====================================================================
pause
