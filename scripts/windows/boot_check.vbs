' Boot logger: tras el reinicio, espera a que se asienten los procesos
' y vuelca la lista de procesos (con linea de comando) a un archivo de log,
' para revisar despues que no quedo nada de mas abierto.
Set WshShell = CreateObject("WScript.Shell")
WScript.Sleep 25000
Dim cmd
cmd = "powershell -NoProfile -Command ""Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|terminal64|cmd|conhost'} | ForEach-Object { $($_.ProcessId), $($_.Name), $($_.CommandLine) } | Out-File 'C:\Users\v_jac\Desktop\SMC-SYSTEMS\logs\boot_processes.txt' -Encoding utf8"""
WshShell.Run cmd, 0, True
