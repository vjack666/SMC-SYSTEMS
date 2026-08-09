' Lanza start_all_session.bat OCULTO (sin ventana de consola negra).
' Usado por el acceso directo en la Carpeta de Inicio de Windows.
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c ""C:\Users\v_jac\Desktop\SMC-SYSTEMS\start_all_session.bat""", 0, False
