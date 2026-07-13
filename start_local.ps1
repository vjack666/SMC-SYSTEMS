# Arranque LOCAL de SMC-SYSTEMS (adaptado a esta maquina).
# Usa Python 3.11 del usuario Eva (no C:\Python314 ni rutas de v_jac).
# Modo observador: vigilante + app PySide6. NO abre ordenes.
# En ESTA maquina NO se usa el loop_analisis (24/7). Solo UI + vigilante.

$ErrorActionPreference = 'Continue'
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ROOT

$PY  = 'C:\Users\Eva\AppData\Local\Programs\Python\Python311\python.exe'
$PYW = 'C:\Users\Eva\AppData\Local\Programs\Python\Python311\pythonw.exe'
if (-not (Test-Path $PY)) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $PY = $cmd.Source }
}
if (-not (Test-Path $PYW)) {
    $cmdw = Get-Command pythonw -ErrorAction SilentlyContinue
    if ($cmdw) { $PYW = $cmdw.Source } else { $PYW = $PY }
}

New-Item -ItemType Directory -Force -Path (Join-Path $ROOT 'logs') | Out-Null

function Write-Status($label, $ok, $detail = '') {
    $color = if ($ok) { 'Green' } else { 'Yellow' }
    $mark  = if ($ok) { 'OK ' } else { '-- ' }
    $txt   = "[$mark] $label"
    if ($detail) { $txt += " - $detail" }
    Write-Host $txt -ForegroundColor $color
}

function Test-ProcRunning($pattern) {
    return [bool](Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$pattern*" })
}

Write-Host ""
Write-Host "========== SMC-SYSTEMS arranque local (Eva) ==========" -ForegroundColor Cyan
Write-Host "ROOT: $ROOT"
Write-Host "PY:   $PY"
Write-Host ""

# ---- 1) MT5 (si existe) ----
$mt5Candidates = @(
    'C:\Program Files\FundedNext MT5 Terminal\terminal64.exe',
    'C:\Program Files\MetaTrader 5\terminal64.exe',
    'C:\Program Files (x86)\MetaTrader 5\terminal64.exe'
)
$mt5 = $mt5Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
$mt5Running = [bool](Get-Process -Name 'terminal64' -ErrorAction SilentlyContinue)
if ($mt5Running) {
    Write-Status 'MT5' $true 'ya estaba abierto'
} elseif ($mt5) {
    Write-Host "Abriendo MT5: $mt5"
    Start-Process -FilePath $mt5
    Start-Sleep -Seconds 3
    $mt5Running = [bool](Get-Process -Name 'terminal64' -ErrorAction SilentlyContinue)
    Write-Status 'MT5' $mt5Running $mt5
} else {
    Write-Status 'MT5' $false 'no instalado en rutas conocidas'
}

# ---- 2) Loop de analisis: DESACTIVADO en esta maquina ----
# Si por algun motivo quedo corriendo (arranque viejo), se apaga.
Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*loop_analisis.py*' } |
    ForEach-Object {
        Write-Host "Apagando loop residual PID $($_.ProcessId)..."
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
Write-Status 'Loop de analisis' $true 'DESACTIVADO en esta maquina (no se usa)'

# ---- 3) Vigilante de riesgo (SOLO CIERRA) ----
if (Test-ProcRunning 'vigilante_riesgo.py') {
    Write-Status 'Vigilante de riesgo' $true 'ya corria'
} else {
    $out = Join-Path $ROOT 'logs\vigilante.out'
    $err = Join-Path $ROOT 'logs\vigilante.err'
    Start-Process -FilePath $PYW -ArgumentList (Join-Path $ROOT 'scripts\vigilante_riesgo.py') `
        -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Hidden
    Start-Sleep -Seconds 1
    Write-Status 'Vigilante de riesgo' (Test-ProcRunning 'vigilante_riesgo.py') 'scripts\vigilante_riesgo.py'
}

# ---- 4) App del observador ----
if (Test-ProcRunning 'run_app.py') {
    Write-Status 'Observador UI' $true 'ya corria'
} else {
    $out = Join-Path $ROOT 'logs\observador.out'
    $err = Join-Path $ROOT 'logs\observador.err'
    Start-Process -FilePath $PYW -ArgumentList (Join-Path $ROOT 'run_app.py') `
        -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Hidden
    Start-Sleep -Seconds 2
    Write-Status 'Observador UI' (Test-ProcRunning 'run_app.py') 'run_app.py (PySide6)'
}

Write-Host ""
Write-Host "==================== REPORTE DE ARRANQUE ====================" -ForegroundColor Cyan
Write-Status 'Loop de analisis'     (-not (Test-ProcRunning 'loop_analisis.py')) 'apagado a proposito'
Write-Status 'Vigilante de riesgo'  (Test-ProcRunning 'vigilante_riesgo.py')
Write-Status 'Observador (PySide6)' (Test-ProcRunning 'run_app.py')
Write-Status 'MT5 terminal64'       ([bool](Get-Process -Name 'terminal64' -ErrorAction SilentlyContinue))
Write-Host "Logs: $ROOT\logs\" -ForegroundColor DarkGray
Write-Host "Modo: OBSERVADOR local - sin loop, no abre ordenes." -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

