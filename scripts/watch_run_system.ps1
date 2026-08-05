param(
    [string]$LogPath = ".\results\run_system_live.log",
    [int]$TailLines = 25,
    [int]$RefreshSeconds = 10
)

$ErrorActionPreference = "Stop"

Write-Host "Watching run_system.py status..." -ForegroundColor Cyan
Write-Host "Log: $LogPath" -ForegroundColor DarkGray
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray

while ($true) {
    Clear-Host
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$now] run_system watchdog" -ForegroundColor Cyan

    $proc = Get-CimInstance Win32_Process -Filter "name='python.exe'" |
        Where-Object { $_.CommandLine -like "*run_system.py*" } |
        Select-Object -First 1

    if ($null -ne $proc) {
        $p = Get-Process -Id $proc.ProcessId -ErrorAction SilentlyContinue
        if ($null -ne $p) {
            Write-Host "Status: RUNNING" -ForegroundColor Green
            Write-Host ("PID: {0} | CPU(s): {1:N2} | WS(MB): {2:N1}" -f $p.Id, $p.CPU, ($p.WorkingSet64 / 1MB))
        }
        else {
            Write-Host "Status: STARTED (process details unavailable)" -ForegroundColor Yellow
            Write-Host ("PID: {0}" -f $proc.ProcessId)
        }
    }
    else {
        Write-Host "Status: NOT RUNNING" -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "--- Last log lines ---" -ForegroundColor Yellow
    if (Test-Path $LogPath) {
        Get-Content $LogPath -Tail $TailLines
    }
    else {
        Write-Host "Log file not found yet. Start run_system with Tee-Object first." -ForegroundColor DarkYellow
    }

    Start-Sleep -Seconds $RefreshSeconds
}
