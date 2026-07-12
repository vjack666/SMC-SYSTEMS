@echo off
REM =====================================================================
REM  Compara filtro choch_bos_confirm (libro 02 §3.1) CON vs SIN
REM  Motor VIVO (signals/pipeline.py). No usa optimize.py.
REM  Datos ya estan en disco (data/mt5/*.parquet) -> no hace falta
REM  mercado abierto ni dia laboral.
REM =====================================================================
SETLOCAL
SET PY=C:\Python314\python.exe
SET REPO=C:\Users\v_jac\Desktop\SMC-SYSTEMS

echo ===================================================
echo  INICIO: %date% %time%
echo  (carga parquet + barrido CON/SIN filtro)
echo ===================================================

cd /d "%REPO%"
"%PY%" "%REPO%\scripts\compare_choch_bos_confirm.py"

echo ===================================================
echo  FIN: %date% %time%
echo ===================================================
pause
ENDLOCAL
