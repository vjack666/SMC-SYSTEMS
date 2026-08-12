"""HYP-002 Fase 6 — VERIFICADOR INDEPENDIENTE (consumidor puro del motor).

Este módulo es el "Verificador" obligatorio del §13 del Director. Consume el
motor (run_sequence_traced) como consumidor externo y audita el GRAFO REAL
emitido en ``signal["event_objects"]`` (diccionario id -> MarketObject.to_dict),
NO solo el Expediente. Esto cierra el hueco del validador previo
(phase6_validation.audit_full_chain), que NO auditaba la causalidad de los
eslabones POI y REFINEMENT.

Dimensiones auditadas (SDD_GOVERNANCE §4 / Arquitectura A):
  IDENTITY   : ids únicos, no vacíos donde requerido.
  LINK       : cada parent_object resoluble a id existente en el grafo.
  CAUSALITY  : parent declarado == el id del rol padre en la cadena canónica.
  TEMPORAL   : parent.bar_index <= child.bar_index (anti look-ahead).
  GRAPH      : cadena RETURN->...->LIQUIDITY recorrible cuando todos existen.
  CYCLES     : 0 ciclos.
  ONTOLOGIA  : POI role=POI SOLO en HTF; REFINEMENT role=REFINEMENT en LTF.

Clasificación OBSERVABLE / DERIVABLE / UNKNOWN (Director §11):
  OBSERVABLE : la relación está en el grafo emitido (parent_object explícito).
  DERIVABLE  : se podría inferir de OHLC/índices, pero el motor no la fija.
  UNKNOWN    : el nodo/nodo-relación no existe en la emisión.

NO usa WR/PF/edge. NO indicadores. Solo representación + trazabilidad.
"""

from __future__ import annotations

from typing import Any

# Cadena canónica hijo -> padre (roles). POI es opcional (solo si anclado HTF).
# CONTRACT es el limite formacion->ejecucion (hijo del RETURN, role=EXECUTION).
_CHAIN = [
    ("CONTRACT", "RETURN"),
    ("RETURN", "REFINEMENT"),
    ("REFINEMENT", "POI"),
    ("REFINEMENT", "BOS"),     # fallback si no hay POI
    ("POI", "BOS"),
    ("BOS", "DISPLACE"),
    ("DISPLACE", "SWEEP"),
    ("SWEEP", "LIQUIDITY"),
]


def _expected_parent(ids: dict, child_ph: str) -> str | None:
    """Devuelve el id del padre canónico esperado para `child_ph`.

    Para REFINEMENT: POI si existe, si no BOS (honesto con la ontología).
    Para los demás: el rol inmediatamente anterior en la cadena.
    """
    if child_ph == "REFINEMENT":
        return ids.get("POI") or ids.get("BOS")
    for c, p in _CHAIN:
        if c == child_ph:
            return ids.get(p)
    return None


def verify_setup(signal: dict) -> dict:
    """Audita UN setup emitido por el motor. Devuelve reporte por dimensión."""
    ids: dict = signal.get("event_ids", {}) or {}
    eo: dict = signal.get("event_objects", {}) or {}
    out: dict[str, Any] = {
        "identity": "OK", "link": "OK", "causality": "OK", "temporal": "OK",
        "graph": "OK", "cycles": 0, "ontology": "OK",
        "issues": [],
        "observable_links": [], "unknown_links": [], "derivable_links": [],
    }

    # --- IDENTITY ---
    seen = set()
    for ph, eid in ids.items():
        if not eid:
            if ph in ("POI",):  # POI puede faltar (sin ancla HTF) -> no es fallo
                continue
            out["identity"] = "MISSING"
            out["issues"].append(f"id vacío en {ph}")
        if eid in seen:
            out["identity"] = "DUP"
            out["issues"].append(f"id duplicado {eid}")
        seen.add(eid)

    # --- Recolección de (id -> bar_index) y (id -> role/tipo) desde el grafo ---
    idx_of = {oid: o.get("bar_index") for oid, o in eo.items()}

    # --- LINK + CAUSALITY + TEMPORAL (sobre el grafo real event_objects) ---
    for child_ph, _ in _CHAIN:
        cid = ids.get(child_ph, "")
        if not cid:
            if child_ph in ("LIQUIDITY", "POI"):
                continue
            out["link"] = "CHILD_MISSING"
            out["issues"].append(f"{child_ph} id ausente en event_ids")
            continue
        child_obj = eo.get(cid)
        if child_obj is None:
            out["link"] = "CHILD_MISSING"
            out["issues"].append(f"{child_ph} id {cid} ausente en event_objects")
            continue
        decl_parent = child_obj.get("parent_object") or ""
        exp_parent = _expected_parent(ids, child_ph)

        # LINK: el parent declarado debe existir en el grafo
        if decl_parent:
            if decl_parent not in eo:
                out["link"] = "PARENT_MISSING"
                out["issues"].append(
                    f"{child_ph}.parent={decl_parent} no resoluble en event_objects")
                continue
        else:
            if child_ph != "LIQUIDITY":
                out["unknown_links"].append(f"{child_ph}->(raíz vacía)")
                if out["link"] == "OK":
                    out["link"] = "PARENT_EMPTY"

        # CAUSALITY: el parent declarado debe coincidir con el padre canónico
        if decl_parent and exp_parent:
            if decl_parent == exp_parent:
                out["observable_links"].append(f"{child_ph}->{_parent_role(child_ph, ids)}")
            else:
                valid = False
                if child_ph == "REFINEMENT":
                    valid = decl_parent in (ids.get("POI"), ids.get("BOS"))
                if not valid:
                    out["causality"] = "PARENT_MISMATCH"
                    out["issues"].append(
                        f"{child_ph}.parent={decl_parent} != canónico={exp_parent}")
                else:
                    out["observable_links"].append(f"{child_ph}->{_parent_role(child_ph, ids)}")
        elif decl_parent and not exp_parent:
            out["observable_links"].append(f"{child_ph}->{decl_parent[:6]}...")

        # TEMPORAL: parent.bar_index <= child.bar_index
        if decl_parent and decl_parent in idx_of and cid in idx_of:
            pi = idx_of.get(decl_parent)
            ci = idx_of.get(cid)
            if pi is not None and ci is not None and int(pi) > int(ci):
                out["temporal"] = "PARENT_FUTURE"
                out["issues"].append(
                    f"{child_ph} idx {ci} < padre idx {pi} (look-ahead)")

    # --- CYCLES ---
    for oid, o in eo.items():
        p = o.get("parent_object") or ""
        if p == oid:
            out["cycles"] += 1

    # --- ONTOLOGIA: POI solo HTF; REFINEMENT en LTF; CONTRACT=EXECUTION ---
    for oid, o in eo.items():
        if o.get("role") == "POI" and o.get("origin_tf") not in ("D1", "H4", "H1"):
            out["ontology"] = "POI_NO_HTF"
            out["issues"].append(f"POI {oid} en TF {o.get('origin_tf')} (debe ser HTF)")
        if o.get("role") == "REFINEMENT" and o.get("origin_tf") in ("D1", "H4", "H1"):
            out["ontology"] = "REFINEMENT_EN_HTF"
            out["issues"].append(f"REFINEMENT {oid} en HTF {o.get('origin_tf')}")
        if o.get("type") == "CONTRACT":
            # El CONTRACT es el limite formacion->ejecucion; NO debe reusar ids
            # de eventos de formacion (sin mezclar eventos).
            if o.get("role") != "EXECUTION":
                out["ontology"] = "CONTRACT_NO_EXECUTION"
                out["issues"].append(f"CONTRACT {oid} role={o.get('role')} (debe ser EXECUTION)")
            if o.get("parent_object") == oid:
                out["cycles"] += 1
            # Sin mezclar: el CONTRACT no comparte id con RETURN/REF/BOS/POI.
            _form_ids = {ids.get("RETURN"), ids.get("REFINEMENT"),
                         ids.get("BOS"), ids.get("POI")}
            if o.get("id") in _form_ids:
                out["ontology"] = "CONTRACT_REUSES_FORMATION_ID"
                out["issues"].append("CONTRACT reusa id de formacion (mezcla eventos)")

    # --- GRAPH: recorrible RETURN->LIQUIDITY cuando todos los nodos existen ---
    if all(ids.get(r) for r in ("RETURN", "LIQUIDITY")):
        cur = ids.get("RETURN")
        visited = set()
        while cur and cur not in visited:
            visited.add(cur)
            cur = (eo.get(cur) or {}).get("parent_object") or ""
        if ids.get("LIQUIDITY") in visited:
            out["graph"] = "OK"
        else:
            out["graph"] = "NOT_TRAVERSABLE"
            out["issues"].append("cadena RETURN->LIQUIDITY no recorrible")

    return out


def _parent_role(child_ph: str, ids: dict) -> str:
    if child_ph == "REFINEMENT":
        return "POI" if ids.get("POI") else "BOS"
    for c, p in _CHAIN:
        if c == child_ph:
            return p
    return "?"


def verify_run(signals: list[dict]) -> dict:
    """Audita TODO el run. Devuelve agregado + porcentajes por dimensión."""
    n = len(signals)
    agg = {
        "n_setups": n,
        "identity_ok": 0, "link_ok": 0, "causality_ok": 0,
        "temporal_ok": 0, "graph_ok": 0, "cycles_total": 0,
        "ontology_ok": 0,
        "poi_anchored": 0,
        "observable_total": 0, "unknown_total": 0,
        "details": [],
    }
    for sig in signals:
        r = verify_setup(sig)
        agg["identity_ok"] += int(r["identity"] == "OK")
        agg["link_ok"] += int(r["link"] == "OK")
        agg["causality_ok"] += int(r["causality"] == "OK")
        agg["temporal_ok"] += int(r["temporal"] == "OK")
        agg["graph_ok"] += int(r["graph"] == "OK")
        agg["ontology_ok"] += int(r["ontology"] == "OK")
        agg["cycles_total"] += r["cycles"]
        if sig.get("event_ids", {}).get("POI"):
            agg["poi_anchored"] += 1
        agg["observable_total"] += len(r["observable_links"])
        agg["unknown_total"] += len(r["unknown_links"])
        agg["details"].append({
            "identity": r["identity"], "link": r["link"], "causality": r["causality"],
            "temporal": r["temporal"], "graph": r["graph"], "ontology": r["ontology"],
            "issues": r["issues"],
            "observable": r["observable_links"], "unknown": r["unknown_links"],
        })
    return agg


def verdict(agg: dict) -> str:
    """Veredicto honesto: VALIDADA / PARCIAL / REFUTADA según evidencia."""
    n = max(1, agg["n_setups"])
    if (agg["identity_ok"] == n and agg["link_ok"] == n and agg["causality_ok"] == n
            and agg["temporal_ok"] == n and agg["graph_ok"] == n
            and agg["cycles_total"] == 0 and agg["ontology_ok"] == n):
        return "A VALIDADA (completa)"
    if agg["link_ok"] == n and agg["causality_ok"] == n and agg["cycles_total"] == 0:
        return "A PARCIAL (identidad/temporal/ontología con fallos menores)"
    return "A REFUTADA (linaje causal roto en múltiples setups)"
