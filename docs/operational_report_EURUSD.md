# 📚 INFORME PARA NOVATOS — Cómo el motor lee el EURUSD


> 💡 **LEE ESTO PRIMERO:** este informe NO es señal de 'compra ahora'. 

> El motor trabaja con datos del pasado (una auditoría), no tiene conexión 

> en vivo. Lo que ves abajo son ejemplos REALES de cómo el motor encontró 

> oportunidades en el mes pasado, para que aprendas la lógica. Es como 

> ver una clase grabada de YouTube, no operar en directo.


**De qué trata:** estudié 10 oportunidades reales en EURUSD. Abajo te explico cada una en lenguaje simple.


## 1. La idea en una frase


El motor mira el mercado como quien mira un edificio desde lejos para cerca:

- 🏢 **D1 / H4 / H1 (los pisos altos)** = ¿Hacia dónde va el mercado en general? (arriba = alcista, abajo = bajista). Esto es el **SESGO**.
- 🚪 **M15 (la puerta)** = ¿En qué punto exacto el precio rompió algo importante? Ahí está la **ESTRUCTURA**.
- 🔑 **M5 (la cerradura)** = ¿Dónde tocó el precio el nivel para entrar? Esa es la **EJECUCIÓN**.

Si los tres pisos dicen 'sube', el motor solo busca entrar comprando. Si dicen 'baja', solo busca entrar vendiendo. Simple.


## 2. ¿El mercado está de acuerdo con el motor?


De las 10 oportunidades, solo **3** estaban alineadas con la dirección general del mercado (30%). Esto es bueno: significa que el motor es **selectivo** y no entra a lo loco. Mejor pocas buenas que muchas malas.


De esas 10, la calidad fue:
- 🟢 **Alta (muy buena):** 2 oportunidades (20%)
- 🟠 **Media (buena):** 6 oportunidades (60%)
- 🔴 **Baja (débil):** 2 oportunidades (20%)
**80% de las oportunidades eran de calidad Alta o Media.** El filtro descarta las débiles para no operar basura.


## 3. El filtro (cuántas 'ideas' sobreviven)


El motor ve muchas cosas, pero la mayoría no sirven. Imagina un embudo:
- 💧 Vio **23** 'barridas de liquidez' (el precio va a cazar stop losses de otros).
- ✨ De esas, **22** tuvieron un movimiento real fuerte.
- 🔨 De esas, **19** rompieron la estructura (el mercado cambió de dirección).
- ✅ Al final, **19** fueron setups completos, y el filtro de calidad dejó **10** buenas.


O sea: de 23 ideas iniciales, solo quedaron 10 dignas de considerar. El filtro quita el ruido.


## 4. Las oportunidades reales (dónde mirar el precio)


Cada fila es una oportunidad que el motor encontró. Los números son **precios**:
- **Entry** = dónde el motor sugería entrar.
- **SL (stop loss)** = dónde poner el límite de pérdida (si te equivocas, sales ahí).
- **TP (take profit)** = dónde cobrar el beneficio.

| # | Cuándo (UTC) | Calidad | Dirección | Entrar en | SL | TP |
|---|---|---|---|---|---|---|
| 1 | 2026-07-31 07:15 | Alta | BEARISH | 1.15112 | 1.15123 | 1.15144 |
| 2 | 2026-08-03 07:15 | Media | BEARISH | 1.15327 | 1.15219 | 1.15650 |
| 3 | 2026-08-03 08:15 | Alta | BULLISH | 1.15335 | 1.15253 | 1.15499 |
| 4 | 2026-08-03 09:15 | Media | BEARISH | 1.15340 | 1.15252 | 1.15516 |
| 5 | 2026-08-04 14:45 | Baja | BULLISH | 1.15163 | 1.15020 | 1.15448 |
| 6 | 2026-08-04 17:15 | Media | BULLISH | 1.15270 | 1.15019 | 1.16023 |
| 7 | 2026-08-05 14:45 | Media | BULLISH | 1.15528 | 1.15303 | 1.16203 |
| 8 | 2026-08-05 15:45 | Baja | BULLISH | 1.15458 | 1.15296 | 1.15943 |
| 9 | 2026-08-06 09:00 | Media | BULLISH | 1.15467 | 1.15466 | 1.15471 |
| 10 | 2026-08-06 13:45 | Media | BULLISH | 1.15409 | 1.15436 | 1.15491 |

📌 **Cómo leerlo:** si la fila dice 'BULLISH' (alcista), tú buscarías COMPRAR cerca del precio 'Entrar en', pondrías el SL un poco debajo, y el TP un poco arriba. Si dice 'BEARISH' (bajista), al revés: vender, SL arriba, TP abajo.


## 5. ¿Por qué no te digo 'opera esto hoy'?


- Este motor analiza el **pasado**, no el momento actual. No está conectado a una plataforma en vivo (como MT5 o Quotex) que le dé el precio de ahora mismo.
- Los datos que usé terminan en agosto pasado. No sé qué pasó hoy.
- Para tener señales de 'hoy', habría que conectar el motor a una fuente en vivo y que mirara el mercado vela por vela. Eso es otro trabajo.
- Lo que te di es la **enseñanza**: cómo piensa el motor y dónde miraría el precio. Con eso ya puedes empezar a entender el método.


## 6. La gráfica (para verlo de un vistazo)


![informe operacional](../results/operational_report_EURUSD.png)


**Qué significa cada dibujo:**
- 📊 **Izquierda:** el embudo (cuántas ideas se descartan hasta quedar pocas buenas).
- 🥧 **Centro:** qué porcentaje eran de calidad Alta / Media / Baja.
- 📈 **Derecha:** los precios de entrada (verde), pérdida (rojo) y ganancia (azul) de cada oportunidad, una al lado de otra.


---
💻 Generado por scripts/build_operational_report.py · datos: results/funnel_authority_filter.json