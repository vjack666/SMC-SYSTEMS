# 06 — Cruce con ICT/SMC del proyecto (distribución ↔ SMC)

Wyckoff y ICT describen lo mismo desde ángulos distintos. En SMC-SYSTEMS conviven en
`agents/wyckoff_agent.py` + `agents/ict_agent.py`, y el Decision Agent los vota
(ICT 0.35 / Wyckoff 0.30 / Structure 0.20 / ML 0.15). Usa **Wyckoff en D1/H4 como contexto**
y **ICT en M15 como entrada de precisión**.

## Mapeo distribución Wyckoff → conceptos ICT
| Wyckoff (distribución) | Equivalente ICT / SMC |
|------------------------|----------------------|
| BC / UTAD (techo de volumen) | **Liquidity sweep de Buyside (BSL)** + rechazo. Smart money caza el stop de los largos y entrega. |
| UT / UTAD fallido | **MSS / CHoCH bajista** tras el sweep: cambio de carácter en LTF. |
| SOW (rompe soporte AR) | **BOS (Break of Structure) bajista** en H4/M15. |
| LPSY (último rally débil) | **Order Block** / re-distribución: la última oferta antes del quiebre. Retest del OB = entrada short ICT. |
| Phase B (rango lateral) | **Power of Three (AMD) fase D = Distribution** (ver `docs/ict/08_POWER_OF_THREE.md`). |
| Markdown | Tendencia bajista ICT tras CHoCH confirmado. |

## Sinergia operativa (rutina del proyecto)
1. **D1/H4 (Wyckoff):** confirma que estamos en distribución (PSY→BC→UTAD→SOW→LPSY). Define
   sesgo = bajista (ventas).
2. **M15 (ICT):** espera el sweep de BSL + CHoCH bajista (o BOS) para entrar corto con
   precisión. El LPSY Wyckoff suele coincidir con un retest de Order Block en M15.
3. **Killzone:** opera la entrada M15 dentro de la sesión de alta actividad
   (ver `docs/ict/01_KILLZONES.md`) para liquidez real.

## Dónde lo implementa el código
- `agents/wyckoff_agent.py`: 12 fases, 40-bar lookback, **stochastic exhaustion**
  (detección de agotamiento en sobrecompra + divergencia) — esto es exactamente el BC/UTAD
  medido por estocástico: momentum agotado arriba = distribución.
- `scripts/fase_wyckoff_m15.py`: fase Wyckoff M15 alimenta el agente.
- `docs/WYCKOFF_RULEBOOK.md`: especificación operativa de los detectores (reglas del agente).
- Conflicto ICT alcista + Wyckoff bajista → el Decision Agent aplica `conflict_penalty`
  (ver `docs/STRATEGY_IMPROVEMENT_PLAN.md` P4). No operar ciego: esperar alineación.

> Regla del proyecto: cada agente se ciñe a su rulebook. ICT → `ICT_RULEBOOK.md`;
> Wyckoff → `WYCKOFF_RULEBOOK.md`. Este libro es la **teoría didáctica** de ventas que
> respalda ese rulebook; el grafo (`graphify-out/graph.json`) indexa el código, estos .md
> indexan la teoría. Juntos dan trazabilidad: regla → detector → código.
