# Auditoría de Uso — SMC-SYSTEMS (2026-07-09)

**Objetivo:** separar lo que tu RUTINA DIARIA real usa de lo que el README documenta
pero es código de "bot" heredado (no cableado a tu flujo de observador FundedNext).

**Método:** lectura de `loop_analisis.py` (orquestador), trazado de imports de los
scripts propios, cruce con `graphify-out/graph.json` (1772 nodos) y conteo de LOC por
carpeta. Sin leer la doc como verdad — se midió el código.

---

## 1. Cadena real de uso (verificada por imports)

```
loop_analisis.py  (observador 24/7, SIEMPRE ACTIVO)
├─ update_mt5_data.py     → data/raw/*.parquet (MT5 demo)
├─ rutina_eurusd.py       → detectors/*, indicators/, fase_wyckoff_m15.py
│   ├─ detectors: bos, choch, fvg, order_blocks, trend, zones
│   │   (+ liquidity, killzones, gaps, fib usados por mapa_precio)
│   ├─ indicators/ (paquete) → add_atr, add_stochastic
│   └─ fase_wyckoff_m15.py → agents/wyckoff_agent.py
├─ informe_eurusd.py      → rutina_eurusd + news_report
├─ semaforo_fundednext.py → rutina_eurusd + news_report + tools/fundednext_compliance.py
├─ alertas.py             → popup + beep (WinForms)
├─ vigilante_riesgo.py    → risk/sizer.py (MT5, SOLO CIERRA 2%/4%)
└─ mapa_precio.py         → rutina_eurusd + detectors/* (ICT, solo imagen)
```

**Import OK confirmado:** `indicators` resuelve como paquete (`indicators/__init__.py` re-exporta `indicators/indicators.py`).

---

## 2. Clasificación

### ✅ USADO — cableado a tu rutina diaria
| Módulo | LOC aprox | Rol |
|--------|-----------|-----|
| `scripts/loop_analisis.py` | 186 | Orquestador observador |
| `scripts/rutina_eurusd.py` | 359 | Ficha top-down D1/H4/M15 + Wyckoff |
| `scripts/fase_wyckoff_m15.py` | 105 | Fase Wyckoff M15 |
| `scripts/informe_eurusd.py` | 138 | Informe técnico + fundamental |
| `scripts/semaforo_fundednext.py` | 128 | Semáforo regla Stellar Lite |
| `scripts/news_report.py` | — | RSS nfs.faireconomy.media |
| `scripts/alertas.py` | 67 | Popup + beep local |
| `scripts/vigilante_riesgo.py` | 141 | Cierre defensivo MT5 |
| `scripts/update_mt5_data.py` | — | Descarga MT5 demo |
| `scripts/mapa_precio.py` | — | Imagen ICT (no loop) |
| `detectors/*` (11) | 812 | BOS/CHOCH/FVG/OB/Trend/Zones + Liquidez/Killzones/Gaps/Fib |
| `indicators/` (paquete) | — | ATR/Stoch/EMA/RSI |
| `agents/wyckoff_agent.py` | — | Calculador fase Wyckoff |
| `tools/fundednext_compliance.py` | 265 | Límites DLL/MLL/riesgo |
| `risk/sizer.py` | — | Cierre MT5 |

### 🟡 USADO-MANUAL — existe, lo corrés a mano, no en el loop
| Módulo | Por qué |
|--------|---------|
| `mapa_precio.py` | Lo pedís por hora; no está en el ciclo del loop (decisión tuya). |

### ❌ NO USADO — bot heredado del README, fuera de tu flujo "sin bot"
| Carpeta | LOC | Qué es |
|---------|-----|--------|
| `ml/` | 2467 | Pipeline ML (XGBoost gate, walk-forward, Optuna) |
| `desktop/` | 1641 | UI PySide6 (6 tabs) |
| `backtest/` | 1430 | Motor backtest combinado |
| `agents/` | 1160 | ICTAgent / StructureAgent / DecisionAgent / Orchestrator |
| `paper_trading/` | 940 | PaperTradingRunner (PAPER/LIVE) |
| `integration/` | 743 | Puente MQL5/ZeroMQ + MQL5 EA |
| `governance/` | 455 | Model registry, retraining scheduler |
| `monitoring/` | 593 | Drift PSI, alerts, telemetry |
| `features/` | 301 | FeatureEngine (30+ features ML) |
| `signals/` | 391 | Scalping pipeline + ScalpingConfig |
| `data/` | 331 | MT5 connector genérico |

**Total NO USADO:** ~10,611 LOC de ~16,500 LOC del repo (~64%).

---

## 3. Stubs / código muerto

- **Cadena activa (tu rutina): 0 stubs.** Ningún `NotImplementedError`/`# TODO`/`# STUB`.
- **Repo completo: 2 archivos** con marcas stub, AMBOS en `integration/mt5_bridge/`
  (exporter.py, receiver.py) — parte del bot heredado, NO afecta tu observador.

---

## 4. Hallazgos / riesgos honestos

1. **README describe un BOT; tu flujo es OBSERVADOR.** El README (desktop, live
   trading, ML gate, MQL5) es el proyecto "SMC_SUCCESSOR" original. Vos decidiste
   "por ahora SIN bot". Hay desalineación doc↔uso real. Recomiendo un README corto
   que diga "Modo actual: observador FundedNext (sin bot)" para no confundirte.

2. **`indicators` ahora es un PAQUETE (`indicators/`)** con `__init__.py` que
   re-exporta el módulo. Antes estaba suelto en la raíz (frágil). Ya robustecido
   en esta sesión: `from indicators import ...` sigue funcionando sin tocar los
   importadores.

3. **`ml/` y `backtest/` NO están en tu loop.** El README reporta WR 63.7% / PF 1.61,
   pero eso es backtest IN-SAMPLE de 91 trades (4 símbolos) — NO validado walk-forward
   OOS en tu flujo actual. No lo usás para decidir hoy, así que no es riesgo operativo,
   pero no lo presentes como "el sistema funciona" sin matizar.

4. **`vigilante_riesgo.py` y `loop_analisis.py` requieren reinicio manual** si se
   editan (no hot-reload). Hoy corren en producción (vigilante PID 15676).

---

## 5. Recomendación (no ejecutada — espero tu visto bueno)

- **Mantener** todo lo de la sección ✅ (es tu rutina real).
- **No borrar** el bot heredado sin tu autorización (podría servirte si activás la
  cuenta real de FundedNext con bot más adelante). Pero etiquetarlo como "no activo".
- **Acción sugerida #1:** agregar un `README_MODESTO.md` o encabezado en README que
  aclare el modo observador. Bajo esfuerzo, alto valor para no confundirte.
- **Acción sugerida #2:** ✅ YA EJECUTADA — `indicators.py` movido a `indicators/`
  con `__init__.py` re-export (robustez, sin breaking). Verificado por import + loop.

---

*Generado por Hermes — evidencia: imports de scripts propios, graph.json (1772 nodos),
conteo LOC por carpeta, grep de stubs. Sin ejecutar live (no hay cuenta real).*
