# SDD — TV Interactivo SMC-SYSTEMS (experiencia 150% humana)

> Documento de diseño y especificación. App HTML self-contained que consume
> `results/tv_scenarios_multitf.json` (10 setups reales del motor, auditoría WM=3).
> Estilo TradingView (dark fintech, referencia Kraken + smc-price-map).

## 1. Superficie (surface-first, claude-design)
Híbrido **Command/Inspect + Decide/Learn**:
- Inspect: el usuario "maneja" el chart como en TradingView (cambia TF, navega setups).
- Learn: cada TF muestra su teoría (educativa) y lo que detectó el motor (técnica).

No es un dashboard de métricas (Monitor) ni landing (Decide puro). Composición:
panel de chart DOMINANTE a la izquierda + rail lateral derecho con teoría/técnica.

## 2. Audiencia
Ruben + novatos. Lenguaje simple en la parte educativa; precisión en la técnica.

## 3. Arquitectura
- `docs/tv_interactivo/index.html` — un solo archivo, CSS+JS embebidos.
- Datos: `fetch('../../results/tv_scenarios_multitf.json')` (servido por http server local).
- Render de velas: `<canvas>` propio (sin librerías externas → portátil, offline-safe).
- Estado en memoria JS; persistencia de setup/TF en `localStorage`.

## 4. Componentes (UI)
1. **Header**: título "EURUSD — TV Interactivo SMC", badge de setup actual, sesgo, nivel.
2. **Setup selector** (dropdown 1..10): cambia el escenario completo.
3. **TF tabs** (D1/H4/H1/M15/M5): cambia el panel de chart como en TradingView.
   - Al cambiar TF, el chart redibuja ese marco; el rail derecho actualiza teoría+técnica.
4. **Chart panel** (canvas): velas reales del TF + marcas del motor.
   - M15/M5: líneas ENTRY (verde) / SL (rojo) / TP (azul) + triángulo en entry_idx.
   - D1/H4/H1: velas + etiqueta de sesgo.
5. **Rail derecho** (two tabs):
   - "Teoría" (educativa): qué significa ese TF en lenguaje simple (la "clase").
   - "Técnica" (ICT): qué detectó el motor (sesgo, BOS, CHOCH censurado, POI, entry/SL/TP).
6. **Footer**: aviso honesto (datos históricos, no señal en vivo).

## 5. Flujos de datos (a probar físicamente)
- F1: cargar página → fetch JSON → primer setup (n=1), TF=M15 por defecto.
- F2: cambiar setup (dropdown) → redibuja chart + rail.
- F3: cambiar TF (tab) → redibuja solo ese marco + rail actualiza teoría/técnica.
- F4: hover sobre vela → tooltip con OHLC (bonus, si da tiempo).
- F5: persistencia localStorage → recargar mantiene setup/TF.

## 6. Parte educativa (contenido por TF)
- D1: "El jefe. Mira la dirección general. Si dice baja, el motor solo vende."
- H4/H1: "El contexto. Confirma o matiza lo que dice D1."
- M15: "La puerta. Donde el precio rompió la estructura (BOS) o cambió (CHOCH real)."
- M5: "La cerradura. Donde el motor entra (entry), con su límite (SL) y meta (TP)."

## 7. Parte técnica (ICT, lo que detectó el motor)
- Sesgo HTF (canónico, camino B): D1/H4/H1 → dirección.
- GATE DURO exp012: CHOCH en M15 solo cuenta si empuje ≥2 HH/LL (ruido censurado).
- Filtro autoridad POI: apila PD Arrays; solo Alta/Media operan.
- Estructura event-driven: sweep → displace → BOS → retorno (motor sequence).

## 8. Design system (Kraken-inspired, dark)
- bg `#0e1117`, panel `#161b22`, borde `#1c2230`, texto `#e6edf3`, muted `#8b949e`.
- acento alcista `#26a69a`, bajista `#ef5350`, TP `#42a5f5`, entry marker `#ffd54f`.
- tipografía: Inter (CDN) + mono para números.
- radios 10-12px, sombras whisper.

## 9. Anti-slop (claude-design)
- NO gradientes globales, NO glassmorphism, NO hero centrado, NO 3 cards iguales.
- Composición asimétrica: chart 70% / rail 30%. Type como jerarquía, no cajas.
- Un solo acento (verde/rojo según dirección), no arcoíris.

## 10. Verificación física (browser automation)
- Servir `docs/tv_interactivo/` en http://localhost:PORT.
- browser_navigate → snapshot → click cada TF tab → verificar chart cambia.
- Cambiar setup dropdown → verificar chart+rail cambian.
- Console errors = 0 requerido.
- vision_analyze screenshot para confirmar velas + marcas + rail legibles.

## 11. Entregables
- `docs/specs/sdd_tv_interactivo.md` (este archivo)
- `docs/tv_interactivo/index.html` (app)
- Pruebas físicas documentadas en `docs/tv_interactivo/VERIFICATION.md`
