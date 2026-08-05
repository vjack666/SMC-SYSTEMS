#Requires -RunAsAdministrator

Write-Host "Instalando OpenSSH Server..."
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0

Write-Host "Configurando servicio..."
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic

Write-Host "Configurando firewall..."
if (-not (Get-NetFirewallRule -DisplayName "OpenSSH SSH Server" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "OpenSSH SSH Server" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow
}

Write-Host "Verificando..."
Get-Service sshd | Select-Object Name, Status, StartType

Write-Host ""
Write-Host "===== LISTO ====="
Write-Host "IP local: $(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch 'Loopback|Virtual|Bluetooth' } | Select-Object -First 1 -ExpandProperty IPAddress)"
Write-Host "Usuario: $env:USERNAME"
Write-Host "Conectate con: ssh $env:USERNAME@<IP>"
