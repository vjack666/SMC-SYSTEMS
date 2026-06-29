# Wyckoff Module

Detects Wyckoff accumulation/distribution events and phases using fractal swings.

## Events
- **Selling Climax (SC)**: high volume, wide spread, closes upper
- **Automatic Rally (AR)**: bounce after SC
- **Secondary Test (ST)**: retest of SC area on lower volume
- **Spring**: break below SC low with quick reversal
- **Sign of Strength (SOS)**: strong up move above SC high with volume
- **Last Point of Support (LPS)**: pullback on low volume after SOS

## Phases
- Accumulation A-E based on which events have occurred
- Distribution (future)

## Config
- `swing_lookback` (5)
- `volume_threshold` (1.5)
- `phase_lookback` (30)
- `spring_depth_atr` (0.3)
- `sos_min_atr` (1.0)
- `lps_max_atr` (0.7)
