# Auditoría: Silver Bullet = 0 señales por bug de contrato de TF (sweep M15 hardcoded)

**Fecha:** 2026-07-13
**Severidad:** Alta (SILENCIA Silver Bullet a 0 en el backtest; no es "sin edge")
**Tipo:** Desincronización checklist ↔ motor (mismo patrón que H1/H2 de la auditoría externa)

## Causa raíz (confirmada empíricamente)
- `ict_backtest/rules.checklist_scalping` lína 198: `sw = _sweep_dir(estructura, ("M15",))`
  busca el sweep en **M15 HARDCODED**.
- Silver Bullet según el libro: sweep en M15, FVG en M1/M5, ejecución M5.
  El backtest de scalping se corre con `--ltf M5` → el engine itera
  `frames={H4, M5, D1}` → `_build_estructura` puebla `est["M5"]`, NO `est["M15"]`.
- Resultado: `_sweep_dir(estructura, ("M15",))` encuentra M15 vacío → `"none"` →
  **item 3 "Sweep M15" = FALTA SIEMPRE** → `evaluate` cuenta FALTA como blocked
  → **0 señales en cualquier símbolo**.

## Evidencia
Barrido sobre EURUSD M5 real (50000 velas, UTC correcto, datos bajados hoy):
- `killzone_en(ts M5)` reparte bien (New York AM: 5220 velas) → NO es bug de tz.
- Items que dan FALTA SIEMPRE (50000/50000):
  - **item 3 (Sweep M15): 50000** ← bloqueante raíz.
  - item 5 (Dirección): 50000 (depende del sweep → arrastra).
  - item 4 (FVG M5): 40529 (normal: FVG no siempre presente).
  - item 1 (Killzone NY AM): 44780 (≈5200 velas sí pasarían).
- Con datos M5 reales y 0 señales, el problema es el sweep M15 hardcoded, no los datos.

## Parche (APLICADO 2026-07-13, autorizado por Ruben — sin commit, regla de hierro)
En `ict_backtest/rules.py` `checklist_scalping`:
- Lína 198 (sweep): usa el TF cargado, no "M15" fijo:
```python
_sweep_tf = next((t for t in ("M15","M5","M1") if t in estructura and estructura[t]), None)
sw = _sweep_dir(estructura, (_sweep_tf,)) if _sweep_tf else "none"
```
- Lína 181 (dirección): `m15 = estructura.get(_exec_tf, {})` con `_exec_tf`
  derivado igual (el TF cargado que no sea H4/D1).
Confirmado por smoke: Silver Bullet pasó de 0 → **122 señales ready** en EURUSD M5 (50k velas).
Re-medición en curso (R4 v2.6).

## Veredicto (REVISADO 2026-07-13, parches aplicados)
Los 3 parches de TF/mapeo SÍ funcionaron: Silver Bullet pasó de **0 → 122
señales "ready"** en EURUSD M5 (50k velas). PERO el filtro `require_displacement`
(R4 v2, que SÍ mejoró Turtle PF 0.689→1.143) **mata TODAS las 122**:
**0 de las 122 velas ready tienen displacement_bullish/bearish en M5**.

Conclusión: **Silver Bullet (M5, NY AM) es incompatible con el filtro
displacement** exigido en R4. El displacement (ruptura fuerte de vela M5)
casi nunca ocurre justo en la ventana NY AM tras sweep+FVG. El setup
Silver Bullet es de ruptura rápida; exigir displacement fuerte lo contradice.

R4 v2.6 (parches + displacement ON): Silver EURUSD/GBPUSD = **0 trades**.
El 0 NO es bug de backtest (ya reparado) ni falta de edge del modelo:
es incompatibilidad de régimen con el filtro displacement.

**Siguiente paso sugerido:** re-medir Silver Bullet SIN `--require-displacement`
(igual que el backtest "oficial" Capa 2 del SDD, que NO lo exige por defecto)
para ver si el modelo solo tiene edge sin ese filtro.
