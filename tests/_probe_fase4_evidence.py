# -*- coding: utf-8 -*-
"""Fase 4 SDD — sonda de evidencia viva (EURUSD real vía parquet, SIN MT5).

Carga D1/H4/H1/M15 (y M5 si está) desde data/raw vía rutina_eurusd._load,
corre run_pipeline y (si RUN_CYCLE=1) run_cycle(force_fetch=False), y vuelca
la evidencia HONESTA a docs/evidence/fase4_last_cycle_probe.json.

Uso:  python tests/_probe_fase4_evidence.py            (solo pipeline)
      RUN_CYCLE=1 python tests/_probe_fase4_evidence.py (pipeline + run_cycle)
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import rutina_eurusd as rut  # noqa: E402
from app_observador.core import pipeline as pl  # noqa: E402

OUT = ROOT / "docs" / "evidence" / "fase4_last_cycle_probe.json"
SYMBOL = "EURUSD"

evidence: dict = {
    "probe": "fase4_evidencia_viva",
    "symbol": SYMBOL,
    "generated_utc": datetime.now(timezone.utc).isoformat(),
    "fuente_datos": "data/raw/*.parquet via rutina_eurusd._load (SIN MT5)",
    "timeframes": {},
    "pipeline": None,
    "run_cycle": None,
    "notas_honestas": [],
}

infos: dict = {}
for tf in ("D1", "H4", "H1", "M15", "M5"):
    t0 = time.time()
    try:
        df = rut._load(SYMBOL, tf)
        info = rut.analyze_timeframe(df, tf)
        infos[tf] = info
        evidence["timeframes"][tf] = {
            "disponible": True,
            "filas": int(len(df)),
            "ultima_vela": str(df.index[-1]) if len(df) else None,
            "analyze_s": round(time.time() - t0, 1),
        }
    except Exception as e:  # honesto: no inventar
        infos[tf] = None
        evidence["timeframes"][tf] = {"disponible": False, "error": f"{type(e).__name__}: {e}"}
        evidence["notas_honestas"].append(f"{tf} no disponible: {e}")

if all(infos.get(tf) for tf in ("D1", "H4", "H1", "M15")):
    res = pl.run_pipeline(infos["D1"], infos["H4"], infos["H1"], infos["M15"], m5=infos.get("M5"))
    ca = res.get("context_alignment", {})
    evidence["pipeline"] = {
        "bias": res.get("bias"),
        "context_alignment": {
            "macro": ca.get("macro"),
            "intraday": ca.get("intraday"),
            "poi": ca.get("poi"),
            "poi_tier": ca.get("poi_tier"),
            "poi_anchored": ca.get("poi_anchored"),
            "poi_stacked": ca.get("poi_stacked"),
            "poi_quality_bonus": ca.get("poi_quality_bonus"),
            "trigger": ca.get("trigger"),
            "trigger_machine": ca.get("trigger_machine"),
            "premium_discount": ca.get("premium_discount"),
            "confidence": ca.get("confidence"),
            "stages": ca.get("stages"),
        },
        "votes_legado": res.get("votes"),
        "poi_detalle": {k: res.get("poi", {}).get(k) for k in
                        ("valid", "tier", "anchored", "stacked", "displacement",
                         "quality_bonus", "tier_note", "premium_discount")},
        "trigger_detalle": {
            "session": res.get("trigger", {}).get("session"),
            "long_machine": (res.get("trigger", {}).get("long") or {}).get("machine_state"),
            "short_machine": (res.get("trigger", {}).get("short") or {}).get("machine_state"),
        },
        "checks": {
            "tiene_poi_tier": ca.get("poi_tier") is not None,
            "tiene_trigger_machine": ca.get("trigger_machine") is not None,
        },
    }
else:
    evidence["notas_honestas"].append(
        "Faltan TF de contexto (D1/H4/H1/M15) -> run_pipeline no ejecutado")

if os.environ.get("RUN_CYCLE") == "1":
    from app_observador.core import engine as eng
    t0 = time.time()
    try:
        rc = eng.run_cycle(force_fetch=False)
        canonical = rc.get("canonical")
        cache_ok = eng.CACHE_PATH.exists()
        verd_ca = (rc.get("veredicto") or {}).get("context_alignment", {})
        evidence["run_cycle"] = {
            "duracion_s": round(time.time() - t0, 1),
            "cache_escrito": cache_ok,
            "cache_path": str(eng.CACHE_PATH),
            "canonical_estado": ("EN CONSTRUCCIÓN" if canonical == "EN CONSTRUCCIÓN"
                                 else "None" if canonical is None else "dict"),
            "canonical": canonical if isinstance(canonical, (str, type(None))) else
                         {k: canonical.get(k) for k in ("side", "entry", "sl", "tp", "rr", "engine")},
            "veredicto_poi_tier": verd_ca.get("poi_tier"),
            "veredicto_trigger_machine": verd_ca.get("trigger_machine"),
            "errores": rc.get("errores"),
        }
    except Exception as e:
        evidence["run_cycle"] = {"error": f"{type(e).__name__}: {e}",
                                 "duracion_s": round(time.time() - t0, 1)}
        evidence["notas_honestas"].append(f"run_cycle falló: {e}")
else:
    evidence["run_cycle"] = "OMITIDO (setear RUN_CYCLE=1 para incluirlo)"

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str),
               encoding="utf-8")
print("Evidencia escrita en", OUT)
print(json.dumps({"timeframes": evidence["timeframes"],
                  "checks": (evidence.get("pipeline") or {}).get("checks"),
                  "run_cycle": evidence["run_cycle"] if isinstance(evidence["run_cycle"], str)
                  else {k: evidence["run_cycle"].get(k) for k in
                        ("cache_escrito", "canonical_estado", "duracion_s")}},
                 ensure_ascii=False, indent=2, default=str))
