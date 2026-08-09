@echo off
REM Arranca la app del observador SMC-SYSTEMS con doble clic.
REM Usa pythonw (sin ventana de consola negra). Si hay error, queda en
REM data\blackbox\app_stderr.log para diagnosticar. El path lo setea run_app.py.
cd /d "C:\Users\v_jac\Desktop\SMC-SYSTEMS"
"C:\Python314\pythonw.exe" run_app.py 2>> "C:\Users\v_jac\Desktop\SMC-SYSTEMS\data\blackbox\app_stderr.log"
