@echo off
REM ============================================================
REM  CAPA 3 - OPTIMIZADOR BAYESIANO (Optuna + Walk-Forward)
REM  SMC-SYSTEMS / ict_backtest
REM
REM  EJECUTAR: doble-clic en este .bat.
REM  Abre una ventana de PowerShell con -NoExit => NO se cierra sola.
REM  Ves el progreso EN VIVO (barra + "falta ~X min") y se guarda
REM  el log en docs/ict/logs/CAPA3_OPTUNA_WF.log.
REM  Para salir: cerrar la ventana o Ctrl+C al terminar.
REM ============================================================
SETLOCAL
cd /d "%~dp0"

REM --- Detectar python (doble-clic usa PATH distinto al de la terminal) ---
SET "PYTHON="
where python >nul 2>&1
IF %ERRORLEVEL%==0 (
    SET "PYTHON=python"
) ELSE (
    IF EXIST "C:\Users\v_jac\AppData\Local\Programs\Python\Python314\python.exe" (
        SET "PYTHON=C:\Users\v_jac\AppData\Local\Programs\Python\Python314\python.exe"
    ) ELSE (
        echo [ERROR] No encontre python en el PATH ni en la ruta comun.
        echo Instala Python o ajusta la variable PYTHON en este .bat.
        pause
        EXIT /B 1
    )
)

echo ============================================================
echo  CAPA 3 - OPTIMIZADOR BAYESIANO (Optuna + Walk-Forward)
echo  Ventana PowerShell (-NoExit): NO se cierra sola.
echo  Progreso EN VIVO + log en docs/ict/logs/CAPA3_OPTUNA_WF.log
echo  TOTAL ESTIMADO: 30-60 min.
echo ============================================================
echo.

REM --- Lanzar en PowerShell con -NoExit (ventana persistente) ---
powershell -NoExit -Command "& '%PYTHON%' 'ict_backtest\optimize.py' --symbol EURUSD --ltf M15 --trials 12 --n-windows 2 --max-hold 96 | Tee-Object -FilePath 'docs\ict\logs\CAPA3_OPTUNA_WF.log'"

ENDLOCAL
