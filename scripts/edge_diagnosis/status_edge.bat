@echo off
REM Medidor de progreso del Edge Diagnosis (no interfiere con el driver en background)
"C:\Users\v_jac\smc_probe\Scripts\python.exe" -u "C:\Users\v_jac\Desktop\SMC-SYSTEMS\scripts\edge_diagnosis\run.py" --status
echo.
pause
