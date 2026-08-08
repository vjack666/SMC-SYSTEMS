# VERIFICATION — TV Interactivo SMC-SYSTEMS (v2, 150% humano)

App: `docs/tv_interactivo/index.html` (self-contained, canvas propio, Google Fonts gratuitas).
Sirve: `python -m http.server 8099` → http://localhost:8099/docs/tv_interactivo/index.html

## Pruebas físicas (browser automation) — RESULTADO: PASS

| # | Prueba | Acción | Resultado |
|---|--------|--------|-----------|
| F1 | Carga + fetch JSON | navigate | ✅ dropdown 1-10 poblado, header Setup/Sesgo/Nivel OK |
| F2 | TF tabs (D1/H4/H1/M15/M5) | click cada tab | ✅ chart+rail redibujan por TF |
| F3 | Cambiar setup (dropdown) | select setup 7 | ✅ header/chart/rail actualizan |
| F4 | Rail Teoría ↔ Técnica ICT | click ambos | ✅ ambas renderizan |
| F5 | Consola JS | browser_console | ✅ 0 errores, 0 warnings |
| F6 | Render visual (vision) | screenshot M5 | ✅ velas + ENTRY/SL/TP + triángulo + rail legible |
| F7 | **Tour guiado** (Clase) | click ▶ + Sig x4 | ✅ overlay paso a paso D1→H4→H1→M15→M5, cambia TF de fondo |
| F8 | **Glosario ICT** | click 📖 | ✅ modal con 10 términos (BOS/CHOCH/POI/FVG/...) |
| F9 | **Filtro calidad** (chips) | click "Alta" | ✅ dropdown filtra a setups 1,3,7,9,10 (solo Alta) |
| F10 | **Tooltip OHLC** (hover) | mousemove canvas | ✅ muestra "07-08 11:15 O/H/L/C" en la vela |
| F11 | **Zoom** (rueda) | wheel -120 x4 | ✅ vision confirma 20-25 velas anchas (zoom in), POI/ENTRY/SL/TP/BOS visibles |
| F12 | **POI zona sombreada** | visual M15 | ✅ rectángulo amarillo + BOS flecha violeta pintados |
| F13 | **Persistencia** | localStorage setup/TF/rail | ✅ implementado en init() (rail tab recordado) |
| F14 | **Responsive** | CSS @media 860px | ✅ rail colapsa debajo en móvil |

## Mejoras v2 (sobre v1)
1. ✅ Tooltip OHLC en hover
2. ✅ Zona POI sombreada + flecha BOS pintadas en el chart
3. ✅ Tour guiado ("Clase") paso a paso por TF
4. ✅ Zoom (rueda) + Pan (arrastrar)
5. ✅ Glosario ICT (modal)
6. ✅ Filtro por calidad (chips Todos/Alta/Media/Baja)
7. ✅ Persistencia de rail tab
8. ✅ Responsive (móvil)
9. ✅ Leyenda ampliada (POI, BOS)
10. ✅ Footer con hints de uso

## Notas honestas
- Todo gratis: canvas nativo + Google Fonts (CDN público). Sin librerías de pago ni APIs.
- Datos históricos (WM=3). Footer lo declara.
- Zoom/pan usan estado `view{}` local (no global) — verificado por vision, no por lectura de var.

## Cómo usar
1. `python -m http.server 8099` (raíz repo).
2. Abrir http://localhost:8099/docs/tv_interactivo/index.html
3. Dropdown escenario + tabs TF + Clase guiada + Glosario + filtro calidad + rueda/arrastrar.
