# Arranque de sesion SMC-SYSTEMS / Hermes.
# UNICO punto de inicio del sistema (el acceso directo Hermes.lnk en la
# Carpeta de Inicio de Windows apunta a este archivo).
#
# 1) Abre el terminal MT5 FundedNext (si no esta corriendo) y actualiza
#    data/raw con datos EN VIVO (lo primero que hace Hermes).
# 2) Lanza el loop de analisis (observador automatico) en segundo plano.
# 3) Lanza el vigilante de riesgo (kill-switch, SOLO CIERRA) en segundo plano.
# 4) Lanza la app del observador (PySide6) en segundo plano (sin consola negra).
# 5) Imprime un REPORTE de salud (procesos vivos + estado git) en la ventana.
# 6) Lanza Hermes en ESTA MISMA ventana (sin espera previa).
#
# Nota: start_all_session.bat YA NO prende Hermes ni corre la rutina (evita
# dos ventanas de Hermes / duplicar procesos). El .ps1 es el unico punto.
#
# Rutina de arranque: scripts/hermes_startup_routine.py (MT5 + datos + ficha EURUSD).
# Corre con pythonw.exe => SIN ventana negra.

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

# ---- 1) MT5 + datos EN VIVO + ficha EURUSD (rutina de arranque automatica) ----
# hermes_startup_routine.py hace TODO en orden con SIN ventana negra:
#   a) abre MT5 FundedNext (si no esta), b) baja datos en vivo, c) arma ficha EURUSD.
# Reemplaza el viejo .bat (que solo bajaba datos y dejaba la ficha a mano).
$routine = Join-Path $PSScriptRoot 'scripts\hermes_startup_routine.py'
Write-Host "[Hermes] Paso 1/4: MT5 FundedNext + datos en vivo + ficha EURUSD..."
& 'C:\Python314\pythonw.exe' $routine
if ($LASTEXITCODE -ne 0) {
    Write-Host "[Hermes] ADVERTENCIA: la rutina de arranque fallo (MT5 cerrado o sin login?). Se continua igual." -ForegroundColor Yellow
}

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

# ---- 5) Reporte de salud + actualizaciones (en esta misma ventana) ----
# Verifica que los procesos quedaron VIVOS y revisa el estado del repo (git).
# Solo INFORMA; no hace pull ni cierra nada. Asi no hay espera ciega ni riesgo.
function Test-ProcRunning($pattern) {
    return [bool](Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$pattern*" })
}
function Write-Status($label, $ok, $detail = '') {
    $color = if ($ok) { 'Green' } else { 'Red' }
    $mark  = if ($ok) { 'OK ' } else { 'X  ' }
    $txt   = "[$mark] $label"
    if ($detail) { $txt += " — $detail" }
    Write-Host $txt -ForegroundColor $color
}

Write-Host ""
Write-Host "==================== REPORTE DE ARRANQUE ====================" -ForegroundColor Cyan
Write-Status 'Loop de analisis'       (Test-ProcRunning 'loop_analisis.py')
Write-Status 'Vigilante de riesgo'    (Test-ProcRunning 'vigilante_riesgo.py')
Write-Status 'Observador (PySide6)'   (Test-ProcRunning 'run_app.py')
$mt5 = [bool](Get-Process -Name 'terminal64' -ErrorAction SilentlyContinue)
Write-Status 'MT5 FundedNext abierto' $mt5

# Actualizaciones del CODIGO (solo informar, NO bajar):
#  - cambios sin guardar (working tree sucio)
#  - commits locales sin pushear (ahead) o nuevos en el remoto (behind)
$git = 'git'
$dirty = & $git -C $PSScriptRoot 'status' '--short' 2>$null
$ahead = 0; $behind = 0
$sb = & $git -C $PSScriptRoot 'status' '-sb' 2>$null
if ($sb -match 'ahead (\d+)')  { $ahead  = [int]$Matches[1] }
if ($sb -match 'behind (\d+)') { $behind = [int]$Matches[1] }

if ($dirty) {
    $n = ($dirty | Where-Object { $_ } | Measure-Object).Count
    Write-Status 'Cambios sin guardar' $false "$n archivo(s) sin commitear"
} else {
    Write-Status 'Cambios sin guardar' $true 'working tree limpio'
}
if ($ahead -gt 0) {
    Write-Status 'Commits sin pushear' $false "$ahead commit(s) locales sin subir"
} elseif ($behind -gt 0) {
    Write-Status 'Actualizaciones en remoto' $false "$behind commit(s) nuevos para bajar"
} else {
    Write-Status 'Estado del repo' $true 'sincronizado con el remoto'
}
Write-Host "============================================================" -ForegroundColor Cyan

# ---- 6) Hermes (sin espera previa, luego del reporte) ----
Write-Host "[Hermes] Iniciando Hermes en esta misma ventana..."
hermes
