# MAPA DE LECTURA DEL MERCADO — HYP-002 Piloto 1 (resultado consolidado)

**Fecha:** 2026-08-11
**Ejecución:** GitHub Actions (Ubuntu), `run 31497898201`, 32s. Consumidor puro del motor.
**Muestra:** EURUSD M15, 3000 velas (2022-01 a 2022-02). Setups emitidos por el motor: **4**.
**Regla:** sin WR/PF. Auditoría de FORMACIÓN. UNKNOWN no se convierte en PASS.

---

## 1. Qué partes del setup el motor REALMENTE sabe leer (demostrado setup por setup)

| Capa del setup | Estado en el motor | Evidencia en las 4 fichas |
|---|---|---|
| Contexto HTF (D1/H4/H1) | ✓ demostrado | `htf_aligned=PASS` en los 4; H4 trend BEARISH/BULLISH coherente con dirección |
| Liquidez (BSL/SSL pool existe) | ✓ demostrado (DERIVABLE) | `bsl/ssl_price` presente como columna del detector |
| Liquidez TOMADA (wick del sweep) | ✓ demostrado (OBSERVABLE) | mecha del sweep @idx524/607/1355/2711 con nivel real |
| Sweep | ✓ demostrado (OBSERVABLE) | flag `liquidity_sweep_*` + timestamp real |
| Displacement | ✓ demostrado (OBSERVABLE) | flag `displacement_*` en vela posterior al sweep |
| BOS/CHOCH (evento) | ✓ demostrado (OBSERVABLE) | `bos_dir` en vela posterior al displacement |
| POI (zona FVG/OB) | ✓ demostrado (DERIVABLE) | zona re-derivada entre sweep y BOS con niveles reales en los 4 |
| Retorno al POI (mitigación) | ✓ demostrado (OBSERVABLE) | close toca la zona en @idx535/612/1361/2718 |
| Dirección coherente sweep→disp→BOS→retorno | ✓ demostrado | los 4 setups coherentes en dirección |

## 2. Dónde se rompe la formación (linaje causal NO demostrado)

| Unión causal | Veredicto | Por qué |
|---|---|---|
| Sweep → Displacement | **UNKNOWN** | el motor solo exige proximidad temporal (`displace_gap`), no identidad. No hay `sweep_id` enlazado al displacement. |
| Displacement → BOS | **UNKNOWN** | el motor no conserva "qué swing rompió el BOS". `bos_level` no se emite (ver hallazgo H1). |
| BOS → POI | **UNKNOWN** | anclaje por dirección + timestamp, no identidad. `poi_present` es bool, no vínculo. |

**Conclusión de causalidad:** el motor FORMA la secuencia (orden + dirección observables) pero la
**identidad causal 1:1 no está demostrada** en las 3 uniones. Cada setup → veredicto agregado
**SETUP FORMADO / CAUSALITY BROKEN** en esas uniones.

## 3. Hallazgos científicos (registrados, NO reparados durante el piloto)

- **H1 — `bos_level` no se conserva en la emisión.** El motor calcula `state.bos_level`
  (`engine/sequence.py:579`) pero la señal emitida (`sequence.py:618-634`) no lo incluye y la
  columna `bos_level` del frame está vacía en las velas BOS. Brecha de trazabilidad. No se
  repara aquí (regla AUDITAR→DIAGNOSTICAR→DECIDIR→MODIFICAR).
- **H2 — Liquidez estructural no anclada al sweep.** En 3/4 setups no hay `bsl/ssl_price`
  cercano al sweep (pools escasos). El motor no prueba que el sweep tomó UN pool específico.
  Emparejamiento por proximidad es DERIVABLE pero no demuestra toma.
- **H3 — `Expediente.meta` solo conserva `{"symbol","ltf_tf"}`.** No hay `MarketObject[]` ni
  niveles. El linaje vive solo como índices + dirección (confirmado en `expediente.py:296`).
- **H4 (GAP-1) — Macro/News ausente.** Sin fuente macro conectada → siempre UNKNOWN.
- **H5 — Ejecución fina M5/M1 no auditada.** `est_htf_ctx_fn=None` en este piloto (modo legacy
  rápido). La capa LTF de confirmación queda UNKNOWN.

## 4. Veredicto de la fase (cierre de unidad científica)

**B) SETUP NO FORMADO COMPLETAMENTE / TESIS DE FORMACIÓN NO DEMOSTRADA EN SU TOTALIDAD.**

El motor demuestra leer y formar correctamente: contexto HTF, liquidez tomada, sweep,
displacement, BOS/CHOCH, zona POI y retorno. Pero **la identidad causal del linaje
sweep→displacement→BOS→POI no está demostrada** (3 uniones UNKNOWN) porque el motor no conserva
esa trazabilidad. Esto NO es "el setup perdió": es que **el setup nunca llega a estar
completamente formado como cadena causal demostrable** con los datos que el motor emite hoy.

Esto es resultado correcto y útil: revela exactamente dónde el edificio LEE el mercado vs. dónde
NARRA después de los hechos. Las reparaciones (enriquecer `Expediente` con `MarketObject[]` y
linaje causal) son fase posterior separada, fuera de HYP-002 fase de lectura.

## 5. Qué NO se modificó

- `engine/` — intacto.
- `detectors/` — intacto.
- `ict_backtest/` — NO importado por el piloto (Opción B; evita bug `datetime` en `rules.py`).
- Sin WR/PF/expectancy/optimización.

## 6. Recomendación del CEO para la siguiente fase

1. **Decidir (no aún modificar)** si el motor debe enriquecer `Expediente` con `MarketObject[]`
   y linaje causal 1:1 (sweep_id→displacement_id→bos_id→poi_id). Eso cerraría las 3 uniones UNKNOWN.
2. **Cerrar GAP-1 (macro)**: conectar una fuente macro objetiva antes de claim de contexto.
3. **Solo tras validar la lectura** (esta fase): abrir FORMACIÓN→VALIDACIÓN MACRO/NEWS→
   OUT-OF-SAMPLE/OTC→ESTUDIO ESTADÍSTICO→EDGE/WR/PF. No invertir el orden.
