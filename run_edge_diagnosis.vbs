' EDGE DIAGNOSIS - launcher OCULTO (sin pantalla negra).
' Corre el harness de validacion de scalping en segundo plano.
' Doble clic a este .vbs cuando quieras validar los simbolos cortos.
' El progreso queda en results/edge_diagnosis/ y el reporte en
' docs/EDGE_DIAGNOSIS_REPORT.md (no abre consola).
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c C:\Users\v_jac\Desktop\SMC-SYSTEMS\reset_and_run_cortos.bat", 0, False
