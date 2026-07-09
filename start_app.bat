@echo off
REM Arranca la app del observador SMC-SYSTEMS con doble clic.
REM No requiere terminal: abre la ventana sola.
cd /d "C:\Users\v_jac\Desktop\SMC-SYSTEMS"
set PYTHONPATH=C:\Users\v_jac\Desktop\SMC-SYSTEMS
"C:\Python314\python.exe" app_observador\main.py
if errorlevel 1 (
    echo.
    echo La app termino con error. Revisa data\blackbox\app.log
    pause
)
