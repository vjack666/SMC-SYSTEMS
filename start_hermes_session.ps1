# Arranque de sesion SMC-SYSTEMS / Hermes.
# UNICO punto de inicio del sistema (el acceso directo Hermes.lnk en la
# Carpeta de Inicio de Windows apunta a este archivo).
#
# 1) Abre el terminal MT5 FundedNext (si no esta corriendo) y actualiza
#    data/raw con datos EN VIVO (lo primero que hace Hermes).
# 2) Lanza el loop de analisis (observador automatico) en segundo plano.
# 3) Lanza el vigilante de riesgo (kill-switch, SOLO CIERRA) en segundo plano.
# 4) Lanza la app del observador (PySide6) en segundo plano (sin consola negra).
# 5) ESPERA 3 MINUTOS y luego lanza Hermes en ESTA MISMA ventana.
#
# Nota: start_all_session.bat YA NO prende Hermes (para evitar dos ventanas
# de Hermes). El .ps1 es el unico que lo hace.
#
# Reusa scripts/start_hermes_session.bat (que a su vez usa update_mt5_data.py).

$ErrorActionPreference = 'Continue'

# ---- 0) Ayudantes ----
function Start-BgPy($scriptName, $logName) {
    # pythonw.exe = Python SIN ventana de consola. Loop y vigilante corren asi
    # (sus alertas popup+sonido usan System.Windows.Forms, que no necesita consola).
    $pyw    = 'C:\Python314\pythonw.exe'
    $script = Join-Path $PSScriptRoot "scripts\$scriptName"
    $log    = Join-Path $PSScriptRoot "logs\$logName"
    Start-Process -FilePath $pyw -ArgumentList $script -RedirectStandardOutput $log -WindowStyle Hidden
}

# ---- 1) MT5 + datos EN VIVO ----
$bat = Join-Path $PSScriptRoot 'scripts\start_hermes_session.bat'
Write-Host "[Hermes] Paso 1/4: abrir MT5 FundedNext + actualizar datos..."
& $bat

# ---- 2) Loop de analisis (SIEMPRE ACTIVO 24/7) ----
Write-Host "[Hermes] Paso 2/4: encendiendo loop de analisis (SIEMPRE ACTIVO, sin bot, con alertas)..."
Start-BgPy 'loop_analisis.py' 'loop_analisis.out'
Write-Host "[Hermes] Loop encendido en segundo plano. Corre cada 5 min 24/7 (ventana trading 07:00-20:00 Ecuador). Alertas popup+sonido ON."

# ---- 3) Vigilante de riesgo (kill-switch, SOLO CIERRA) ----
Write-Host "[Hermes] Paso 3/4: encendiendo VIGILANTE de riesgo (kill-switch, SOLO CIERRA al 2%/4%)..."
Start-BgPy 'vigilante_riesgo.py' 'vigilante.out'
Write-Host "[Hermes] Vigilante encendido. Cierra TODAS las operaciones abiertas si la perdida flotante toca 2% (y 4% DLL). Nunca abre."

# ---- 4) App del observador (Lab Setup / Principal) ----
Write-Host "[Hermes] Paso 4/4 (parte A): encendiendo app del observador (PySide6)..."
Start-BgPy 'run_app.py' 'observador.out'
Write-Host "[Hermes] Observador encendido en segundo plano."

# ---- 5) Hermes, con lapse de 3 minutos de espera ----
$lapseSec = 180
Write-Host ("[Hermes] Paso 4/4 (parte B): esperando " + $lapseSec + " s (3 min) para que se asienten MT5/loop/vigilante/observador antes de iniciar Hermes...")
$dots = 0
for ($i = $lapseSec; $i -gt 0; $i--) {
    Start-Sleep -Seconds 1
    # Imprime un punto cada 6s (10 puntos = 3 min) sin llenar la pantalla.
    if (($lapseSec - $i) % 6 -eq 0) { Write-Host -NoNewline "."; $dots++ }
}
Write-Host ""
Write-Host "[Hermes] Lapse cumplido. Iniciando Hermes en esta misma ventana..."
hermes
