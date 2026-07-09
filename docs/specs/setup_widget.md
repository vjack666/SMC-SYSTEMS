# SDD — Pestaña Principal "Setup armado" (Wyckoff + sesgo + estructura)

## Objetivo (Ruben, 2026-07-09)
Enriquecer la pestaña "Principal" para que muestre CÓMO está armado el setup del
día, usando las reglas reales de `docs/WYCKOFF_RULEBOOK.md` y el sesgo direccional
del veredicto. Debe ser detallista (no solo "D1: bajista"), citando reglas y el
código que las detecta (Graphify).

## Fuentes de datos (reales, sin inventar)
1. `app_observador/core/engine.py` (ya calcula y expone):
   - `result["estructura"][tf]` = trend, bos_dir, bos_status, sweep_up/down,
     ote_long/short  (engine.py:92-102)
   - `result["estructura"]["WYCKOFF_M15"]` = fase Wyckoff M15 (engine.py:102)
   - `result["bias"]` + `verdict["votes"]` = sesgo direccional (engine.py:84-87)
2. `docs/WYCKOFF_RULEBOOK.md` — significado de cada fase (§1-12) y matriz de
   transición (Appendix A). Se lee como texto para el "qué significa".
3. `graphify-out/graph.json` — grafo de CONOCIMIENTO del CÓDIGO (1705 nodos,
   4557 links, formato networkx). Mapea cada fase detectada a su detector real:
   - Markup/Markdown/Accumulation/Distribution -> `agents/wyckoff_agent.py`
     (WyckoffAgent) y `scripts/fase_wyckoff_m15.py`
   - Spring -> `WyckoffAgent._detect_spring` ; Upthrust -> `_detect_upthrust`
   (confirmado en graph.json: nodos `agents_wyckoff_agent_wyckoffagent_detect_spring`,
   `..._detect_upthrust`).
   NO indexa el rulebook en prosa; por eso el significado se lee del .md.

## Herramientas / terminal (pulcro)
- Python `json` para cargar `graphify-out/graph.json` y consultar nodos por fase.
- `search_files` / `read_file` para citar `WYCKOFF_RULEBOOK.md` (archivo:línea).
- Sin instalar nada (graphify pkg no está, pero el grafo YA está materializado).

## Cambios (KISS, 1 archivo existente + 1 llamada)
1. `app_observador/ui/resumen_widget.py`:
   - `update_state(self, estructura, bias=None, votes=None)` (ampliar firma).
   - Nueva funcion `resumen_setup(estructura, bias, votes, graph)` que arma texto:
     a) Sesgo direccional: votes L/S + bias; cita WYCKOFF_RULEBOOK.md §11-12
        (esfuerzo/resultado volumen-precio) si aplica.
     b) Estructura por TF (D1/H4/M15): tendencia, BOS/CHOCH, barrido liquidez, OTE.
     c) Fase Wyckoff M15: nombre + significado del rulebook (md) + detector real
        mapeado desde graph.json (cita archivo:funcion).
     d) "Setup armado": cruce D1/H4/M15 + Wyckoff -> alineacion (reusa logica del
        veredicto ya existente).
   - Carga `graphify-out/graph.json` UNA vez (module-level lazy load).
2. `app_observador/ui/main_window.py`:
   - En `_apply_result`, pasar `result.get("bias")` y `verdict` votes al resumen:
     `self.resumen.update_state(result.get("estructura"), result.get("bias"), result.get("verdict",{}).get("votes"))`
     (verificar que verdict esté en result; sino pasar votes=None).

## Restricciones
- Solo lectura de graph.json + md; no modificar el grafo.
- No hardcodear significados de fase: leer del rulebook.
- No duplicar logica de deteccion; solo presentacion.
- Compatibilidad: si graph.json falta, fallback a texto sin cita de codigo.

## Verificacion
- py_compile resumen_widget.py + main_window.py
- Run: cargar cache real (`load_cached`), `ResumenWidget.update_state` con
  estructura + bias + votes; assert que el texto contiene la fase Wyckoff y el
  sesgo. Mostrar primeras lineas del texto generado.
- (Visual) abrir app via start_app.bat y revisar pestaña Principal.

## Entregable
Pestaña Principal con setup detallado: sesgo direccional + estructura D1/H4/M15 +
fase Wyckoff M15 (significado del rulebook + detector del grafo) + resumen de
alineacion. Commiteado y pusheado.
