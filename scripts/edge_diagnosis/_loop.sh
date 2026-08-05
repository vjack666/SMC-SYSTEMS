#!/bin/bash
# Wrapper: corre el driver de edge-diagnosis en reintentos hasta completion.
# Cada reintento muere a ~55s por el launcher del terminal, pero el checkpoint
# de run.py sobrevive en disco. Este bucle relanza hasta ver "Done." en el log.
ROOT="/c/Users/v_jac/Desktop/SMC-SYSTEMS"
PY="/c/Users/v_jac/smc_probe/Scripts/python.exe"
SCRIPT="/c/Users/v_jac/Desktop/SMC-SYSTEMS/scripts/edge_diagnosis/run.py"
LOG="/c/Users/v_jac/Desktop/SMC-SYSTEMS/results/edge_diagnosis/_driver.log"

for i in $(seq 1 80); do
  if grep -q "Done." "$LOG" 2>/dev/null; then
    echo "[wrapper] completado en intento $i"; break
  fi
  echo "[wrapper] intento $i @ $(date +%H:%M:%S)" >> "$LOG"
  timeout 50 "$PY" -u "$SCRIPT" --driver >> "$LOG" 2>&1
  sleep 1
done
echo "[wrapper] FIN bucle" >> "$LOG"
