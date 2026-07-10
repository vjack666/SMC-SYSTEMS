#!/bin/bash
# Wrapper lanzado DESDE /c/Users/v_jac/Desktop/SMC-SYSTEMS (rutas relativas).
cd /c/Users/v_jac/Desktop/SMC-SYSTEMS
PY="/c/Users/v_jac/smc_probe/Scripts/python.exe"
SCRIPT="scripts/edge_diagnosis/run.py"
LOG="results/edge_diagnosis/_driver.log"

for i in $(seq 1 80); do
  if grep -q "Done." "$LOG" 2>/dev/null; then
    echo "[wrapper] completado en intento $i"; break
  fi
  echo "[wrapper] intento $i @ $(date +%H:%M:%S)" >> "$LOG"
  timeout 50 "$PY" -u "$SCRIPT" --driver >> "$LOG" 2>&1
  sleep 1
done
echo "[wrapper] FIN bucle" >> "$LOG"
