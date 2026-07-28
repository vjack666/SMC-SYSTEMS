@echo off
REM Arranque post-reinicio: abre el dashboard SMC SYSTEMS y se limpia solo.
REM Espera a que el sistema termine de cargar (hasta 25s).
timeout /t 25 /nobreak >nul
REM Abre el dashboard oculto (sin consola negra).
start "" "C:\Users\v_jac\Desktop\SMC-SYSTEMS\start_app.vbs"
REM Borra la tarea programada para no repetir en futuros logins.
schtasks /delete /tn "OpenSMCOnBoot" /f >nul 2>&1
REM Borra este mismo script.
del "%~f0" >nul 2>&1
