param(
    [string]$PythonExe = ".venv/Scripts/python.exe",
    [string]$TerminalPath = "C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe",
    [int]$Years = 50,
    [string[]]$Symbols = @("EURUSD", "GBPUSD", "XAUUSD"),
    [string[]]$Timeframes = @("M15", "H1", "H4", "D1")
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$global:ScriptStart = Get-Date
$global:RunLog = ".\results\_run_log.txt"
New-Item -ItemType Directory -Force -Path ".\results" | Out-Null
"[$(Get-Date -Format s)] START run_full_mt5_max.ps1" | Out-File -FilePath $global:RunLog -Encoding utf8

$global:Mt5Log = ".\results\mt5_download_live.log"
$global:RetrainLog = ".\results\retrain_live.log"
$global:RunSystemLog = ".\results\run_system_live.log"

function Invoke-Step {
    param(
        [string]$Name,
        [string]$Command
    )

    Write-Host ""
    Write-Host "=== $Name ===" -ForegroundColor Cyan
    Write-Host $Command -ForegroundColor DarkGray
    "[$(Get-Date -Format s)] STEP_START $Name" | Add-Content -Path $global:RunLog
    try {
        $previousEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        Invoke-Expression $Command
        $ErrorActionPreference = $previousEap
        $code = $LASTEXITCODE
        if ($null -eq $code) { $code = 0 }
        "[$(Get-Date -Format s)] STEP_END $Name EXIT_CODE=$code" | Add-Content -Path $global:RunLog
        if ($code -ne 0) {
            throw "Step '$Name' failed with EXIT_CODE=$code"
        }
    }
    catch {
        $ErrorActionPreference = "Stop"
        "[$(Get-Date -Format s)] STEP_ERROR $Name :: $($_.Exception.Message)" | Add-Content -Path $global:RunLog
        throw
    }
}

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

if (-not (Test-Path $TerminalPath)) {
    throw "MT5 terminal not found: $TerminalPath"
}

$symbolsArg = ($Symbols -join " ")
$timeframesArg = ($Timeframes -join " ")

Invoke-Step -Name "MT5 MAX DOWNLOAD" -Command "& `"$PythonExe`" -u data/mt5/downloader.py --terminal-path `"$TerminalPath`" --output-dir data/mt5 --symbols $symbolsArg --timeframes $timeframesArg --years $Years *>&1 | Tee-Object -FilePath `"$global:Mt5Log`" -Encoding utf8"

Invoke-Step -Name "MODEL RETRAIN" -Command "& `"$PythonExe`" -u backtest/retrain_models.py *>&1 | Tee-Object -FilePath `"$global:RetrainLog`" -Encoding utf8"

Invoke-Step -Name "FULL SYSTEM RUN" -Command "& `"$PythonExe`" -u run_system.py *>&1 | Tee-Object -FilePath `"$global:RunSystemLog`" -Encoding utf8"

Write-Host ""
Write-Host "=== DONE ===" -ForegroundColor Green
Write-Host "Artifacts are in results/" -ForegroundColor Green
"[$(Get-Date -Format s)] END OK duration=$([int]((Get-Date)-$global:ScriptStart).TotalSeconds)s" | Add-Content -Path $global:RunLog
