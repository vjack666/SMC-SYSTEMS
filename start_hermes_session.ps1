# Arranque de sesion SMC-SYSTEMS / Hermes.
# 1) Abre el terminal MT5 FundedNext y actualiza data/raw (datos EN VIVO).
# 2) Lanza el loop de analisis (observador automatico) en segundo plano.
# 3) Lanza el vigilante de riesgo (kill-switch, SOLO CIERRA) en segundo plano.
# 4) Lanza Hermes en la misma terminal interactiva.
# Reusa scripts/start_hermes_session.bat (que a su vez usa update_mt5_data.py).

$bat = Join-Path $PSScriptRoot 'scripts\start_hermes_session.bat'
Write-Host "[Hermes] Paso 1/4: abrir MT5 FundedNext + actualizar datos..."
& $bat

Write-Host "[Hermes] Paso 2/4: encendiendo loop de analisis (SIEMPRE ACTIVO, sin bot, con alertas)..."
$loopPy = Join-Path $PSScriptRoot 'scripts\loop_analisis.py'
$loopLog = Join-Path $PSScriptRoot 'logs\loop_analisis.out'
Start-Process -FilePath 'C:\Python314\python.exe' -ArgumentList $loopPy -RedirectStandardOutput $loopLog -WindowStyle Hidden
Write-Host "[Hermes] Loop encendido en segundo plano. Corre cada 5 min 24/7 (ventana trading 07:00-20:00 Ecuador). Alertas popup+sonido ON."

Write-Host "[Hermes] Paso 3/4: encendiendo VIGILANTE de riesgo (kill-switch, SOLO CIERRA al 2%/4%)..."
$vigPy = Join-Path $PSScriptRoot 'scripts\vigilante_riesgo.py'
$vigLog = Join-Path $PSScriptRoot 'logs\vigilante.out'
Start-Process -FilePath 'C:\Python314\python.exe' -ArgumentList $vigPy -RedirectStandardOutput $vigLog -WindowStyle Hidden
Write-Host "[Hermes] Vigilante encendido. Cierra TODAS las operaciones abiertas si la perdida flotante toca 2% (y 4% DLL). Nunca abre."

Write-Host "[Hermes] Paso 4/4: iniciando Hermes..."
hermes
