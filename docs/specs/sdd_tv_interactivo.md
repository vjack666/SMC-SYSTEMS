# SDD — TV Interactivo SMC-SYSTEMS (v2, 150% humano)

> Documento de diseño y especificación. App HTML self-contained que consume
> `results/tv_scenarios_multitf.json` (10 setups reales del motor, auditoría WM=3).
> Estilo TradingView (dark fintech, referencia Kraken + smc-price-map).
> TODO GRATIS: canvas nativo + Google Fonts (CDN público). Sin librerías de pago ni APIs.

## 1. Superficie (surface-first, claude-design)
Híbrido **Command/Inspect + Decide/Learn**:
- Inspect: el usuario "maneja" el chart como en TradingView (cambia TF, zoom, navega setups).
- Learn: cada TF muestra su teoría (educativa) y lo que detectó el motor (técnica).
- Clase guiada: tour paso a paso D1→M5 (el "150% humano").

No es dashboard de métricas ni landing. Composición asimétrica: chart 70% / rail 30%.

## 2. Audiencia
Ruben + novatos. Lenguaje simple en educativa; precisión en técnica.

## 3. Arquitectura
- `docs/tv_interactivo/index.html` — un solo archivo, CSS+JS embebidos.
- Datos: `fetch('../../results/tv_scenarios_multitf.json')` (http server local).
- Render: `<canvas>` propio (sin librerías → portátil, offline-safe).
- Estado JS en memoria; persistencia setup/TF/rail en `localStorage`.

## 4. Componentes (UI)
1. **Header**: título, badges setup/sesgo/nivel, dropdown escenario, chips calidad, btn Clase, btn Glosario.
2. **Setup selector** (dropdown 1..10) + **chips calidad** (Todos/Alta/Media/Baja) filtran.
3. **TF tabs** (D1/H4/H1/M15/M5): cambia el panel como TradingView; rail actualiza.
4. **Chart panel** (canvas): velas reales + marcas motor.
   - M15/M5: ENTRY (verde) / SL (rojo) / TP (azul) + triángulo entry + zona POI (amarillo) + flecha BOS (violeta).
   - Zoom (rueda) + Pan (arrastrar) + Tooltip OHLC (hover).
5. **Rail derecho** (Teoría / Técnica ICT): educativa vs qué detectó el motor.
6. **Tour overlay**: clase paso a paso por TF.
7. **Glosario modal**: 10 términos ICT en lenguaje simple.
8. **Footer**: aviso honesto + hints de uso.

## 5. Flujos (probados físicamente, VERIFICATION.md F1-F14)
- F1 carga → F2 TF tabs → F3 cambio setup → F4 rail → F7 tour → F8 glosario
- F9 filtro calidad → F10 tooltip → F11 zoom/pan → F12 POI/BOS → F13 persistencia → F14 responsive.

## 6. Parte educativa (contenido por TF)
- D1: "El jefe. Mira la dirección general. Si dice baja, el motor solo vende."
- H4/H1: "El contexto. Confirma o matiza lo que dice D1."
- M15: "La puerta. Donde rompió la estructura (BOS) o cambió (CHOCH real). Ancla POI."
- M5: "La cerradura. Donde entra (entry), con SL y TP. Ejecución pura."

## 7. Parte técnica (ICT, lo que detectó el motor)
- Sesgo HTF canónico (camino B): D1/H4/H1 → dirección.
- GATE DURO exp012: CHOCH en M15 solo cuenta si empuje ≥2 HH/LL (ruido censurado).
- Filtro autoridad POI: apila PD Arrays; solo Alta/Media operan.
- Estructura event-driven: sweep → displace → BOS → retorno (motor sequence).

## 8. Design system (Kraken-inspired, dark)
- bg `#0e1117`, panel `#161b22`, borde `#1c2230`, texto `#e6edf3`, muted `#8b949e`.
- acento alcista `#26a69a`, bajista `#ef5350`, TP `#42a5f5`, entry `#ffd54f`, BOS `#9b8cff`.
- Inter + JetBrains Mono (CDN gratis). Radios 10-12px.

## 9. Anti-slop (claude-design)
- NO gradientes globales, NO glassmorphism, NO hero centrado.
- Composición asimétrica chart/rail. Type como jerarquía.
- Un solo acento por dirección, no arcoíris.

## 10. Cobertura educativa + técnica (requisito usuario)
- Educativa: rail "Teoría" + Tour guiado + Glosario ICT (10 términos).
- Técnica: rail "Técnica ICT" (sesgo, CHOCH censurado, POI, precios) + marcas pintadas.

## 11. Estado de completitud (v2 — 150% humano)
Todos los huecos del SDD v1 cerrados y verificados físicamente:

| Hueco v1 | Estado v2 |
|----------|-----------|
| Tooltip OHLC en hover | ✅ F10 |
| Zona POI + flecha BOS pintadas | ✅ F12 |
| Tour guiado paso a paso ("Clase") | ✅ F7 |
| Zoom (rueda) + Pan (arrastrar) | ✅ F11 |
| Sync temporal entre TF (cursor cruzado) | ⚠️ parcial: cada TF ventana anclada al setup; no hay cursor temporal cruzado (fuera de scope, no degrada la clase) |
| Glosario ICT | ✅ F8 |
| Filtro por calidad | ✅ F9 |
| Persistencia rail tab | ✅ F13 |
| Responsive / móvil | ✅ F14 |
| Comparación lado a lado de setups | ⚠️ no implementado (fuera de scope; filtro calidad cubre "mejor setup") |

Sync cruzado y comparación lado a lado se postergan (no bloquean la experiencia 150%:
clase guiada + filtro + zoom ya dan recorrido completo). Incrementos aislados sin tocar motor.

## 12. Entregables
- `docs/specs/sdd_tv_interactivo.md` (este archivo, v2 completo)
- `docs/tv_interactivo/index.html` (app, canvas propio, 0 dependencias de pago)
- `docs/tv_interactivo/VERIFICATION.md` (pruebas físicas F1-F14, todas PASS)
- Datos: `results/tv_scenarios_multitf.json` (10 setups reales WM-3)
