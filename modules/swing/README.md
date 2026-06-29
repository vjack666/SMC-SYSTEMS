# Swing Module

Este modulo contiene la deteccion de swing highs y swing lows por pivotes.

## Archivos
- `swing_detector.py`: implementacion principal.
- `detector.py`: alias de import para mantener consistencia con otros modulos.
- `__init__.py`: API publica del modulo.

## Uso rapido
```python
from modules.swing import SwingConfig, detect_swings

result = detect_swings(frame, SwingConfig(left_window=5, right_window=5, min_distance=3))
```
