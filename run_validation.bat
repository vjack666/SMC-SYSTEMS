@echo off
REM =====================================================================
REM  PRUEBA DE FUEGO (A12) - SMC-SYSTEMS
REM  Walk-forward OOS de la celda ganadora no_session x XAUUSD
REM  Con barra de progreso en vivo + log con timestamp.
REM
REM  Doble-clic en este archivo. Requiere MT5 abierto y logueado
REM  SOLO si queres bajar mas datos (--download-years). Si no, la
REM  prueba usa los datos que ya estan en data/raw.
REM =====================================================================

SETLOCAL ENABLEDELAYEDEXPANSION
title SMC-SYSTEMS - Prueba de Fuego (A12)

REM --- Python: usar el del repo o el del PATH ---
IF EXIST "C:\Python314\python.exe" (
    SET PY=C:\Python314\python.exe
) ELSE (
    SET PY=python
)

SET ROOT=%~dp0
SET LOG=%ROOT%results\walkforward\walkforward.log

echo.
echo  ============================================================
echo   SMC-SYSTEMS - PRUEBA DE FUEGO (A12 Walk-Forward OOS)
echo   Celda ganadora: no_session x XAUUSD
echo  ============================================================
echo.
echo   [1/2] Verificando Python...
"%PY%" --version
IF ERRORLEVEL 1 (
    echo   ERROR: no se encontro Python. Instalalo o ajusta PY en este .bat
    pause
    EXIT /B 1
)

echo.
echo   [2/2] Lanzando validacion (barra de progreso abajo)...
echo   Log: %LOG%
echo.

REM --- La barra de progreso vive en la consola (progress.json + walkforward.log) ---
"%PY%" "%ROOT%scripts\run_walkforward_validation.py" %*

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
