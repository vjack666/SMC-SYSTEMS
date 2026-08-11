# PRUEBA DE FALSABILIDAD — Arquitectura B (HYP-002 Fase 3)
Símbolo: EURUSD M15 | Motor: run_sequence_traced (consumidor puro, Opción B)
Regla: PROXIMIDAD NO ES CAUSALIDAD; >1 candidato -> AMBIGUOUS

## Metodología
- Se emite el setup con el motor (índices sweep/displace/bos/entry).
- El AUDITOR (no el motor) reconstruye el linaje por PROXIMIDAD+DIRECCIÓN.
- Por cada unión se CUENTA el nº de candidatos plausibles (unicidad).
- Si >1 -> AMBIGUOUS (nunca se elige el más cercano silenciosamente).
- Sensibilidad: se repite con ventanas de gap {2,3,4,5,7}.

## Resultados por muestra

### S1_5k (5000 velas M15) — 5 setups emitidos
- Setup con las 3 uniones UNIQUE: 1/5 (20%)
- Setup con >=1 union AMBIGUOUS: 3/5 (60%)
- Setup con >=1 union NONE (sin candidato): 2/5
  - sweep_disp: candidatos promedio=0.60, max=1, >=2 en 0/25 setups
  - disp_bos: candidatos promedio=0.80, max=2, >=2 en 5/25 setups
  - bos_poi: candidatos promedio=1.60, max=2, >=2 en 15/25 setups

### S2_15k (15000 velas M15) — 10 setups emitidos
- Setup con las 3 uniones UNIQUE: 1/10 (10%)
- Setup con >=1 union AMBIGUOUS: 8/10 (80%)
- Setup con >=1 union NONE (sin candidato): 3/10
  - sweep_disp: candidatos promedio=0.70, max=1, >=2 en 0/50 setups
  - disp_bos: candidatos promedio=1.30, max=2, >=2 en 25/50 setups
  - bos_poi: candidatos promedio=1.60, max=3, >=2 en 25/50 setups

### S3_38k (38000 velas M15) — 10 setups emitidos
- Setup con las 3 uniones UNIQUE: 1/10 (10%)
- Setup con >=1 union AMBIGUOUS: 8/10 (80%)
- Setup con >=1 union NONE (sin candidato): 3/10
  - sweep_disp: candidatos promedio=0.70, max=1, >=2 en 0/50 setups
  - disp_bos: candidatos promedio=1.30, max=2, >=2 en 25/50 setups
  - bos_poi: candidatos promedio=1.60, max=3, >=2 en 25/50 setups

### S4_60k (60000 velas M15) — 10 setups emitidos
- Setup con las 3 uniones UNIQUE: 1/10 (10%)
- Setup con >=1 union AMBIGUOUS: 8/10 (80%)
- Setup con >=1 union NONE (sin candidato): 3/10
  - sweep_disp: candidatos promedio=0.70, max=1, >=2 en 0/50 setups
  - disp_bos: candidatos promedio=1.30, max=2, >=2 en 25/50 setups
  - bos_poi: candidatos promedio=1.60, max=3, >=2 en 25/50 setups

## Resumen agregado
| Muestra | Setups | UNIQUE(3/3) | AMBIGUOUS(>=1) | NONE(>=1) |
|---|---|---|---|---|
| S1_5k | 5 | 1 | 3 | 2 |
| S2_15k | 10 | 1 | 8 | 3 |
| S3_38k | 10 | 1 | 8 | 3 |
| S4_60k | 10 | 1 | 8 | 3 |

## Casos adversariales (muestra de setups con >=1 union AMBIGUOUS)
- [S1_5k] dir=-1 sweep@524 disp@529 bos@534 -> {'sweep_disp': 'NONE', 'disp_bos': 'NONE', 'bos_poi': 'AMBIGUOUS'}
- [S1_5k] dir=1 sweep@1355 disp@1358 bos@1360 -> {'sweep_disp': 'UNIQUE', 'disp_bos': 'AMBIGUOUS', 'bos_poi': 'AMBIGUOUS'}
- [S1_5k] dir=1 sweep@4451 disp@4453 bos@4454 -> {'sweep_disp': 'UNIQUE', 'disp_bos': 'UNIQUE', 'bos_poi': 'AMBIGUOUS'}
- [S2_15k] dir=-1 sweep@524 disp@529 bos@534 -> {'sweep_disp': 'NONE', 'disp_bos': 'NONE', 'bos_poi': 'AMBIGUOUS'}
- [S2_15k] dir=1 sweep@1355 disp@1358 bos@1360 -> {'sweep_disp': 'UNIQUE', 'disp_bos': 'AMBIGUOUS', 'bos_poi': 'AMBIGUOUS'}
- [S2_15k] dir=1 sweep@4451 disp@4453 bos@4454 -> {'sweep_disp': 'UNIQUE', 'disp_bos': 'UNIQUE', 'bos_poi': 'AMBIGUOUS'}
- [S2_15k] dir=-1 sweep@6175 disp@6176 bos@6177 -> {'sweep_disp': 'UNIQUE', 'disp_bos': 'AMBIGUOUS', 'bos_poi': 'UNIQUE'}
- [S2_15k] dir=-1 sweep@6232 disp@6234 bos@6237 -> {'sweep_disp': 'NONE', 'disp_bos': 'AMBIGUOUS', 'bos_poi': 'AMBIGUOUS'}
- [S2_15k] dir=-1 sweep@7400 disp@7405 bos@7406 -> {'sweep_disp': 'UNIQUE', 'disp_bos': 'UNIQUE', 'bos_poi': 'AMBIGUOUS'}
- [S2_15k] dir=-1 sweep@7902 disp@7904 bos@7905 -> {'sweep_disp': 'UNIQUE', 'disp_bos': 'AMBIGUOUS', 'bos_poi': 'UNIQUE'}
- [S2_15k] dir=1 sweep@8434 disp@8435 bos@8436 -> {'sweep_disp': 'UNIQUE', 'disp_bos': 'AMBIGUOUS', 'bos_poi': 'UNIQUE'}
- [S3_38k] dir=-1 sweep@524 disp@529 bos@534 -> {'sweep_disp': 'NONE', 'disp_bos': 'NONE', 'bos_poi': 'AMBIGUOUS'}

## Determinacion A vs B (por evidencia, no preferencia)
Total setups auditados: 35
UNIQUE(3/3): 4 (11%)
AMBIGUOUS(>=1): 27 (77%)
NONE(>=1): 11 (31%)

**VEREDICTO:** RESULTADO C (tendencia): B produce ambiguedad material (>10%). La evidencia sugiere que la info no se recupera fiablemente post-hoc; estudiar Arquitectura A (motor conserva ids enlazados).

Tiempo total: 102.9s