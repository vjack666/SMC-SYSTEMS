# VERIFICATION — TV Interactivo SMC-SYSTEMS

App: `docs/tv_interactivo/index.html` (self-contained, consume `results/tv_scenarios_multitf.json`).
Servida en http://localhost:8099/docs/tv_interactivo/index.html (python -m http.server).

## Pruebas físicas (browser automation) — RESULTADO: PASS

| # | Prueba | Acción | Resultado |
|---|--------|--------|-----------|
| F1 | Carga de página + fetch JSON | navigate | ✅ Loading desaparece, header Setup 1 / Sesgo BEARISH / Nivel Alta, dropdown 1-10 poblado |
| F2 | Cambiar TF (todos los tabs) | click D1/H4/H1/M15/M5 | ✅ Rail heading cambia D1→M5, chart redibuja cada marco |
| F3 | Cambiar setup (dropdown) | select setup 7 | ✅ Header "Setup 7", combobox "7 · Alta · BEARISH", chart+rail actualizan |
| F4 | Rail Teoría ↔ Técnica ICT | click ambos tabs | ✅ "M5 — Teoría" y "M5 — Técnica ICT" con secciones correctas |
| F5 | Consola JS | browser_console | ✅ 0 errores, 0 warnings |
| F6 | Render visual (vision_analyze) | screenshot Setup7/M5/Técnica | ✅ velas reales + ENTRY/SL/TP + triángulo + rail ICT legible, sin glitches |

## Hallazgos
- TF tabs: todos funcionales (e2=D1, e3=H4, e4=H1, e5=M15, e6=M5).
- Dropdown nativo: manejable vía JS dispatch (select + change) — clicks directos en
  <option> fallan por cierre de popup, pero la selección funciona igual.
- Persistencia localStorage: setup/TF se recuerdan al recargar (no re-testeado por
  recarga pero implementado en init()).

## Notas honestas
- Datos históricos (auditoría WM=3). No es señal en vivo (footer lo declara).
- CHOCH cens. M5 = 2397 (acumulado hasta el setup) — número alto esperado, es conteo histórico.
- Sin librerías externas de charting: canvas propio (portátil, offline-safe).

## Cómo usar
1. Servir repo: `python -m http.server 8099` (desde raíz SMC-SYSTEMS).
2. Abrir: http://localhost:8099/docs/tv_interactivo/index.html
3. Cambiar escenario (dropdown 1-10) y TF (tabs D1→M5) como en TradingView.
