"""Limpia remanente duplicado al final de la linea 115 de ROADMAP_BIBLIOTECA_Y_APLICACION.md.

Patrón igual que el fix de CRONOGRAMA: la linea quedó con texto duplicado tras
un parche mal aplicado. Recorta en 'B/C/E cerradas) | Alta |' (fin correcto).
No lee parquet ni toca codigo.
"""
from pathlib import Path

p = Path("docs/plan/ROADMAP_BIBLIOTECA_Y_APLICACION.md")
lines = p.read_text(encoding="utf-8").splitlines()
assert len(lines) >= 115, f"esperaba >=115 lineas, tiene {len(lines)}"
marker = "B/C/E cerradas) | Alta |"
line = lines[114]  # 0-indexed -> linea 115
idx = line.find(marker)
assert idx != -1, "no encontre el marcador de fin correcto en linea 115"
cut = idx + len(marker)
new_line = line[:cut]
lines[114] = new_line
p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"linea 115 recortada: {len(line)} -> {len(new_line)} chars")
print("fin correcto:", new_line[-60:])
