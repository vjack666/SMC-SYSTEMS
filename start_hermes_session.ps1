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
Write-Host "[Hermes] Paso 1/4: MT5 FundedNext + datos en vivo + ficha EURUSD (se espera a que termine)..."
# pythonw.exe es un exe de subsistema Windows: con el operador & PowerShell NO espera
# a que termine y el reporte de salud corria antes de que MT5 abriera => MT5 marcado [X].
# Se lanza con Start-Process y se espera (con tope de seguridad) para que el terminal
# FundedNext ya este abierto y logueado cuando se chequea mas abajo.
$routineProc = Start-Process -FilePath 'C:\Python314\pythonw.exe' -ArgumentList $routine -PassThru -WindowStyle Hidden
try {
    $routineProc | Wait-Process -Timeout 180 -ErrorAction Stop
    Write-Host "[Hermes] Rutina de arranque terminada (MT5 + datos en vivo + ficha EURUSD listos)."
} catch {
    Write-Host "[Hermes] ADVERTENCIA: la rutina tardo >180s; se continua igual (MT5 puede seguir abriendo)." -ForegroundColor Yellow
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
# run_app.py vive en la RAIZ del repo (no en scripts/): es el launcher que setea
# sys.path a la raiz y arranca app_observador.ui.main_window. Start-BgPy asume
# scripts\, asi que se lanza directamente con su ruta absoluta.
Write-Host "[Hermes] Paso 4/4 (parte A): encendiendo app del observador (PySide6)..."
$appScript = Join-Path $PSScriptRoot 'run_app.py'
# WindowStyle Normal: la app del observador SE MUESTRA al prender Windows
# (comportamiento tipo WhatsApp: se puede ocultar a la bandeja con la X y
# volver a traerla al frente sin duplicar). Antes estaba en Hidden.
Start-Process -FilePath 'C:\Python314\pythonw.exe' -ArgumentList $appScript `
    -RedirectStandardOutput (Join-Path $PSScriptRoot 'logs\observador.out') -WindowStyle Normal
Write-Host "[Hermes] Observador encendido y VISIBLE (run_app.py en raiz)."

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
    if ($detail) { $txt += " - $detail" }
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
# git status -sb devuelve un ARRAY de lineas. Con -match en modo array NO se puebla
# $Matches (devuelve los elementos coincidentes) => "$Matches[1]" daba "matriz nula".
# Se fuerza a texto unico con Out-String y se usa [regex]::Match (puebla Groups siempre).
$sb = (& $git -C $PSScriptRoot 'status' '-sb' 2>$null) | Out-String
$mAhead  = [regex]::Match($sb, 'ahead (\d+)')
$mBehind = [regex]::Match($sb, 'behind (\d+)')
if ($mAhead.Success)  { $ahead  = [int]$mAhead.Groups[1].Value }
if ($mBehind.Success) { $behind = [int]$mBehind.Groups[1].Value }

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
