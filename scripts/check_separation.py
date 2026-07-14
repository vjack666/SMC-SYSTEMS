"""check_separation.py — cuenta aristas ENTRE módulos desde graph.json.

Prueba honesta de fragmentación: si dos módulos que "deberían" implementar la
misma lógica tienen 0 aristas entre sí, son islas aisladas (deuda de arquitectura).

Uso: python3 scripts/check_separation.py MODULO1 MODULO2 [MODULO3 ...]
Ej:  python3 scripts/check_separation.py signals/pipeline.py agents/ict_agent.py \
        ict_backtest/sequence.py ict_backtest/rules.py ict_backtest/engine.py
"""
import json
import sys
from pathlib import Path

GRAPH = Path("graphify-out/graph.json")


def main():
    if not GRAPH.exists():
        print("ERROR: graphify-out/graph.json no existe. Corré graphify primero.")
        sys.exit(1)
    modules = sys.argv[1:]
    if not modules:
        print("Uso: check_separation.py mod1 mod2 ...")
        sys.exit(1)

    data = json.loads(GRAPH.read_text(encoding="utf-8"))
    nodes = data.get("nodes", [])
    links = data.get("links", [])

    # id -> source_file real
    sf_of = {n["id"]: n.get("source_file", "") for n in nodes}

    # nodos por módulo (match de substring en source_file)
    mod_nodes = {m: set() for m in modules}
    for n in nodes:
        sfn = n.get("source_file", "")
        for m in modules:
            if m in sfn:
                mod_nodes[m].add(n["id"])
                break

    # comunidad por id (si viene en el nodo)
    comm_of = {n["id"]: n.get("community") for n in nodes}

    inter = {}
    intra = {m: 0 for m in modules}
    for e in links:
        s = e.get("source")
        t = e.get("target")
        if not s or not t:
            continue
        sm = next((m for m in modules if s in mod_nodes[m]), None)
        tm = next((m for m in modules if t in mod_nodes[m]), None)
        if sm and tm:
            if sm == tm:
                intra[sm] += 1
            else:
                inter[(sm, tm)] = inter.get((sm, tm), 0) + 1

    print(f"Grafo: {len(nodes)} nodos, {len(links)} aristas")
    print(f"Módulos analizados: {len(modules)}\n")
    for m in modules:
        c = set(comm_of[i] for i in mod_nodes[m] if comm_of[i] is not None)
        print(f"  {m}: {len(mod_nodes[m])} nodos, "
              f"{intra[m]} aristas internas, comunidad(es): {sorted(c)}")
    print("\nAristas ENTRE módulos:")
    any_inter = False
    for m1 in modules:
        for m2 in modules:
            if m1 >= m2:
                continue
            c = inter.get((m1, m2), 0) + inter.get((m2, m1), 0)
            if c:
                any_inter = True
                print(f"  {m1} <-> {m2}: {c}")
    if not any_inter:
        print("  (0) -- los módulos son ISLAS AISLADAS (0 aristas cruzadas)")


if __name__ == "__main__":
    main()
