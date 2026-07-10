# Mueve el acceso directo "SMC-SYSTEMS-Sesion.lnk" fuera de la Carpeta de
# Inicio de Windows, porque arranca start_all_session.vbs (que duplica loop,
# vigilante y observador ya iniciados por start_hermes_session.ps1) y, ademas,
# su paso 5 abria un 2do Hermes. Se conserva en SMC-SYSTEMS\DisabledStartup\
# para poder revertir si hace falta.
$ws = New-Object -ComObject WScript.Shell
$startup = [Environment]::GetFolderPath('Startup')
$src = Join-Path $startup 'SMC-SYSTEMS-Sesion.lnk'
$destDir = Join-Path $PSScriptRoot 'DisabledStartup'
$dest = Join-Path $destDir 'SMC-SYSTEMS-Sesion.lnk'
if (Test-Path $src) {
    if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir | Out-Null }
    Move-Item -Path $src -Destination $dest -Force
    Write-Host "Movido: $src -> $dest"
} else {
    Write-Host "No existe en Inicio (ya estaba fuera): $src"
}
