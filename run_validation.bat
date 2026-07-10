@echo off
REM =====================================================================
REM  PRUEBA DE FUEGO (A12) - SMC-SYSTEMS
REM  Walk-forward OOS de la celda ganadora no_session x XAUUSD
REM  Con barra de progreso en vivo + log con timestamp.
REM
REM  Doble-clic en este archivo. La validacion corre en su PROPIA
REM  ventana (independiente): podeis cerrar ESTA ventana y el pipeline
REM  sigue hasta terminar y escribir el reporte. No se muere al cerrar.
REM
REM  Requiere MT5 abierto y logueado SOLO si pasas --download-years.
REM  Sin ese flag usa los datos que ya estan en data/raw.
REM =====================================================================

SETLOCAL ENABLEDELAYEDEXPANSION
SET ROOT=%~dp0

REM --- Python: usar el del repo o el del PATH ---
IF EXIST "C:\Python314\python.exe" (
    SET PY=C:\Python314\python.exe
) ELSE (
    SET PY=python
)

echo.
echo  ============================================================
echo   SMC-SYSTEMS - PRUEBA DE FUEGO (A12 Walk-Forward OOS)
echo   Celda ganadora: no_session x XAUUSD
echo  ============================================================
echo.
echo   Verificando Python...
"%PY%" --version
IF ERRORLEVEL 1 (
    echo   ERROR: no se encontro Python. Instalalo o ajusta PY en este .bat
    pause
    EXIT /B 1
)

echo.
echo   Lanzando validacion en ventana propia (barra + log)...
echo   Log: %ROOT%results\walkforward\walkforward.log
echo   Podas cerrar esta ventana; el pipeline sigue hasta el reporte.
echo.

REM --- start "" abre el pipeline en su propia ventana, INDEPENDIENTE.
REM     /WAIT hace que este .bat espere y luego reporte el veredicto.
start "" /WAIT "%PY%" "%ROOT%scripts\run_walkforward_validation.py" %*

SET RC=%ERRORLEVEL%
echo.
IF %RC%==0 (
    echo   VERDICTO: PASS - el edge aguanta validacion seria.
) ELSE (
    echo   VERDICTO: FAIL / ERROR (codigo %RC%) - revisar results\walkforward\walkforward.log
)
echo.
echo   Reporte completo en: results\walkforward\WALKFORWARD_REPORT.json
echo   Presiona una tecla para cerrar.
pause
ENDLOCAL
