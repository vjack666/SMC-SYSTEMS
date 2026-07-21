$procs = Get-Process python, pythonw -ErrorAction SilentlyContinue
foreach ($p in $procs) {
    $mb = [math]::Round($p.WorkingSet / 1MB, 1)
    if ($p.WorkingSet -lt 10MB) {
        Write-Host ("KILL " + $p.Id + " " + $p.Name + " " + $mb + "MB")
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host ("KEEP  " + $p.Id + " " + $p.Name + " " + $mb + "MB")
    }
}
Write-Host "=== DONE ==="
