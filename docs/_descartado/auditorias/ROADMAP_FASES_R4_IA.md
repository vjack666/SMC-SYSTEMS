# Roadmap Fases R4 (según IA externa, 2026-07-13)

Protocolo de ejecución con checkpoints. Hermes = ejecutor de protocolo, NO
buscador autónomo de resultado positivo. Detenerse y esperar decisión de Ruben
entre fases.

## Fase 0 — Cerrar pendiente (1 corrida)
- Turtle Soup LIMPIO (look-ahead fix en 6d4b158). `scripts/r4_turtle_v28.py`.
- Salida: PF/WR/n EURUSD y GBPUSD. Documentar en METRICS_CANON §8.2c.
- **Gate:** PF>=1.10 y n>=30 en >=1 símbolo -> Fase 1. Si no -> "sin edge
  confirmado en R4 puros", saltar a Fase 3 (no a Optuna).

## Fase 1 — Validación OOS del candidato (sin tocar parámetros)
- `scripts/edge_diagnosis/run.py --variant baseline --symbol EURUSD --timeframe M15`
  (split IS/OOS 70/30 ya implementado, n>=100).
- **Regla dura:** el PF que importa es OOS (30%), no IS (70%). Si IS=1.3 y
  OOS=0.9 -> no hay edge, hay ajuste al pasado. Anotar ANTES de correr.

## Fase 2 — Optuna, solo si Fase 1 sobrevive
- `ict_backtest/optimize.py --symbol EURUSD --ltf M15 --trials 60 --n-windows 3`
  (walk-forward + Optuna ya implementado).
- **Reglas fijadas antes:** reportar PF promedio OOS (nunca IS). Si PF OOS <
  gate -> descartar, NO re-correr con más trials. Registrar # trials; si >50-100,
  subir gate (PF>=1.20) o exigir bootstrap de significancia.

## Fase 3 — Solo si Turtle puro no pasa: hipótesis nuevas, no barrido ciego
- Antes de código: doc con fecha, variante, justificación ICT/estructural,
  criterio éxito/fracaso fijado. Cada variante = comparación múltiple -> llevar
  registro (# probadas) como control anti-p-hacking.

## Fase 4 — Confirmación final antes de vivo (FundedNext)
1. PF OOS >= gate en >=2 símbolos.
2. n>=30 por símbolo EN OOS (no IS+OOS).
3. MaxDD OOS < 8% (umbral prop firm).
4. Replicación en ventana temporal que no tocó Fase 1 ni 2 (hold-out final).

---

## ESTADO DE EJECUCIÓN (2026-07-14, auditoría real contrastada con código)

### Fase 0 — Cerrar pendiente (Turtle Soup LIMPIO)
- **Look-ahead corregido** en `6d4b158`/`07afc0e`: el join H4→M5 leía velas sin cerrar. Medido: **97.4% de velas M15/M5 contaminadas por HTF futuro**. Los PF de v2.7 (Turtle 1.14) eran FALSO positivo.
- Re-medición v2.7 tras el fix:
  - **Silver Bullet (E4):** PF 0.896 / 0.639 → **RECHAZADO** (pierde de verdad, no era bug de look-ahead).
  - **PO3 + displacement:** 2 y 0 trades → INCONCLUSO.
  - **Turtle Soup:** **PENDIENTE re-correr LIMPIO (v2.8)** con `scripts/r4_turtle_v28.py` (ya marcado en Fase 0 arriba). Es el único que rozó el gate; su veredicto decide si R4 sigue o se documenta "sin edge para live".
- **SL Estructural v29** (`e2a9c11`): SL anclado a mecha del sweep. EURUSD PF 1.128 / GBPUSD PF 2.101, PERO sostenido en `hold_limit` (7/11 y 11/13 cerraron por hold, no TP). Rentable vs ATR v28 (<1), pero el éxito vive del hold, no del TP real.

### Veredicto parcial
- Silver Bullet y PO3 aislados: **sin edge** (rechazado / inconcluso).
- Turtle Soup: **DEFINICIÓN PENDIENTE** (correr v2.8 limpio).
- Si Turtle < 1.10 → Fase 0 gate falla → saltar a Fase 3 (hipótesis nuevas: SMT/Breaker/OTE del roadmap R3.5), NO a Optuna.
- Si Turtle >= 1.10 → continuar Fase 1 (validación OOS del candidato).

### Nota de arquitectura (grafo, 2026-07-14)
Los modelos R4 viven en `ict_backtest/sequence.py` + `engine.py`, aislados del motor en vivo `signals/pipeline.py` (0 aristas cruzadas, ver R7 en ROADMAP_BIBLIOTECA_Y_APLICACION.md). Antes de cualquier vivo, unificar a single source of truth (riesgo "backtest bueno, vivo malo").
