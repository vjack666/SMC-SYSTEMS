"""Limpia remanente duplicado al final de la linea 112 de CRONOGRAMA_Y_ROADMAP.md.

La linea 112 (Fase 5) quedó con texto duplicado pegado al final tras un parche
mal aplicado. Este script la recorta en el marcador correcto:
'...B/C/E cerradas) | Alta |'  ->  deja la linea exactamente hasta ahi.
No lee parquet ni toca codigo.
"""
from pathlib import Path

p = Path("docs/plan/CRONOGRAMA_Y_ROADMAP.md")
lines = p.read_text(encoding="utf-8").splitlines()
assert len(lines) >= 112, f"esperaba >=112 lineas, tiene {len(lines)}"
marker = "B/C/E cerradas) | Alta |"
line = lines[111]  # 0-indexed -> linea 112
idx = line.find(marker)
assert idx != -1, "no encontre el marcador de fin correcto en linea 112"
cut = idx + len(marker)
new_line = line[:cut]
lines[111] = new_line
p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"linea 112 recortada: {len(line)} -> {len(new_line)} chars")
print("fin correcto:", new_line[-60:])
