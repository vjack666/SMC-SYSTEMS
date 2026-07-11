# 06 — Cruce con ICT/SMC del proyecto (acumulación ↔ SMC)

Wyckoff y ICT describen lo mismo desde ángulos distintos. En SMC-SYSTEMS conviven en
`agents/wyckoff_agent.py` + `agents/ict_agent.py`, y el Decision Agent los vota
(ICT 0.35 / Wyckoff 0.30 / Structure 0.20 / ML 0.15). Usa **Wyckoff en D1/H4 como contexto**
y **ICT en M15 como entrada de precisión**.

## Mapeo acumulación Wyckoff → conceptos ICT
| Wyckoff (acumulación) | Equivalente ICT / SMC |
|-----------------------|----------------------|
| SC / Spring (suelo de volumen) | **Liquidity sweep de Sellside (SSL)** + rechazo. Smart money caza el stop de los cortos y absorbe. |
| Spring fallido + Test | **MSS / CHoCH alcista** tras el sweep: cambio de carácter en LTF. |
| SOS (rompe resistencia AR) | **BOS (Break of Structure) alcista** en H4/M15. |
| LPS (último pullback) | **Order Block** / re-acumulación: la última oferta antes del quiebre. Retest del OB = entrada long ICT. |
| Phase B (rango lateral) | **Power of Three (AMD) fase A = Accumulation** (ver `docs/ict/08_POWER_OF_THREE.md`). |
| Markup | Tendencia alcista ICT tras CHoCH confirmado. |

## Sinergia operativa (rutina del proyecto)
1. **D1/H4 (Wyckoff):** confirma que estamos en acumulación (PS→SC→Spring→SOS→LPS). Define
   sesgo = alcista (compras).
2. **M15 (ICT):** espera el sweep de SSL + CHoCH alcista (o BOS) para entrar long con
   precisión. El LPS Wyckoff suele coincidir con un retest de Order Block en M15.
3. **Killzone:** opera la entrada M15 dentro de la sesión de alta actividad
   (ver `docs/ict/01_KILLZONES.md`) para liquidez real.

## Dónde lo implementa el código
- `agents/wyckoff_agent.py`: 12 fases, 40-bar lookback, **stochastic exhaustion**
  (detección de agotamiento en SOBREVENTA + divergencia) — esto es exactamente el SC/Spring
  medido por estocástico: momentum agotado abajo = acumulación.
- `scripts/fase_wyckoff_m15.py`: fase Wyckoff M15 alimenta el agente.
- `docs/WYCKOFF_RULEBOOK.md`: especificación operativa de los detectores (reglas del agente).
- Conflicto ICT bajista + Wyckoff alcista → el Decision Agent aplica `conflict_penalty`
  (ver `docs/STRATEGY_IMPROVEMENT_PLAN.md` P4). No operar ciego: esperar alineación.

> Regla del proyecto: cada agente se ciñe a su rulebook. ICT → `ICT_RULEBOOK.md`;
> Wyckoff → `WYCKOFF_RULEBOOK.md`. Este libro es la **teoría didáctica** de compras que
> respalda ese rulebook; el grafo (`graphify-out/graph.json`) indexa el código, estos .md
> indexan la teoría. Juntos dan trazabilidad: regla → detector → código.
