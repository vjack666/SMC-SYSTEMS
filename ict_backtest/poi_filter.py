"""ict_backtest/poi_filter.py — BRECHA A (Fase C): cablear htf_poi_fn REAL.

El motor (sequence.run_sequence) ya tiene el hook::

    poi_ok = (htf_poi_fn is None) or bool(htf_poi_fn(i, target))

en la memoria de zona (sequence.py ~l.427). Pero canonical.py pasaba
``htf_poi_fn=None``, así que el hook estaba MUERTO (no filtraba nada).

Aquí construimos la fn REAL que consulta el POI anclado HTF (el HtfPdIndex
ya construido en canonical.py cuando ``enable_pd_index=True``) y lo usa como
BONUS de autoridad/calidad de zona — NO como gate duro.

REGLA DE AUDITORÍA FASE E (Ruben): el POI anclado como GATE DURO destruye
el edge (PF 0.900). Por eso ``make_htf_poi_fn`` por defecto (as_gate=False)
SIEMPRE devuelve True (nunca veta la entrada); la presencia real se anota
apartE vía ``poi_present()`` para enriquecer zone_authority / scoring. El
modo as_gate=True (veto real) es SOLO para experimentación y NO se usa en
producción.
"""

from __future__ import annotations

from typing import Any, Callable

from ict_backtest.htf_pd_index import HtfPdIndex, HtfPdZone


def poi_present(
    htf_pd_index: HtfPdIndex | None,
    ltf_map: dict[str, Any] | None,
    i: int,
    target: int,
) -> bool:
    """¿Hay al menos un POI HTF anclado en la dirección ``target`` en la vela LTF ``i``?

    Consulta ``htf_pd_index.zones_at(i, tf, ltf_map)`` para cada TF HTF y
    devuelve True si ALGUNA zona vigente va en ``target``.

    Reutilizable en scoring (bonus de autoridad de zona). Sin índice
    (``None``) -> False (no aporta bonus, comportamiento histórico intacto).
    """
    if htf_pd_index is None or ltf_map is None:
        return False
    for tf in htf_pd_index.timeframes:
        zones = htf_pd_index.zones_at(i, tf, ltf_map)
        for z in zones:
            if getattr(z, "direction", 0) == target:
                return True
    return False


def make_htf_poi_fn(
    htf_pd_index: HtfPdIndex | None,
    ltf_map: dict[str, Any] | None,
    *,
    as_gate: bool = False,
) -> Callable[[int, int], bool]:
    """Devuelve ``(i, target) -> bool`` para el hook ``poi_ok`` de run_sequence.

    - ``as_gate=False`` (DEFAULT, producción): la fn SIEMPRE devuelve True
      (NO veta la entrada; el POI anclado es BONUS, no gate duro, según
      auditoría Fase E). La presencia real se anota aparte vía
      ``poi_present()`` para enriquecer zone_authority / scoring.
    - ``as_gate=True`` (SOLO experimentación, NO producción): devuelve la
      presencia real como VETO duro. Nunca se usa en producción.
    """
    def _fn(i: int, target: int) -> bool:
        present = poi_present(htf_pd_index, ltf_map, i, target)
        if as_gate:
            return present  # veto real (experimental / no producción)
        return True  # nunca veta: bonus de autoridad

    return _fn
