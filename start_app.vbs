' Arranca el observador SMC-SYSTEMS SIN ventana de consola negra.
' Lanza run_app.py con pythonw (oculto, sin cmd negra) y deja stderr en
' data\blackbox\app_stderr.log. WindowStyle=1 => la ventana de la app
' aparece en primer plano (no queda escondida en background).
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\v_jac\Desktop\SMC-SYSTEMS"
cmd = "C:\Python314\pythonw.exe run_app.py 2>> C:\Users\v_jac\Desktop\SMC-SYSTEMS\data\blackbox\app_stderr.log"
WshShell.Run cmd, 1, False
Set WshShell = Nothing
