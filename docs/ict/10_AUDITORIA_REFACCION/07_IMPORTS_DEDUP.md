# Tema 07 — IMPORTS Y DUPLICACIÓN (#7, Medio)

## Hallazgo
`sequence.py::_row_at_time` usa `Any` sin `from typing import Any`:
```python
def _row_at_time(df: pd.DataFrame, t: Any) -> Any:
```
No rompe hoy por `from __future__ import annotations` (anota a string), pero
si algo inspecciona anotaciones en runtime (`typing.get_type_hints`, frameworks
de validación) falla. Además, `_row_at_time` está DUPLICADA casi idéntica en
`engine.py` y `sequence.py`.

## Fix aplicado
1. `sequence.py`: agregar `from typing import Any` (y `cast` si hace falta).
2. Extraer `_row_at_time` a un módulo compartido `ict_backtest/_util.py` y
   borrar la copia de `engine.py` (importa de `_util`).

```python
# ict_backtest/_util.py
from __future__ import annotations
import pandas as pd
from typing import Any
def row_at_time(df: pd.DataFrame, t: Any) -> Any:
    ...
```
`engine.py` y `sequence.py` hacen `from ict_backtest._util import row_at_time`.

## Por qué importa
Limpieza DRY: un solo punto de verdad para el alineamiento HTF/LTF por tiempo
(evita bugs de desalineación distintos en cada copia).
