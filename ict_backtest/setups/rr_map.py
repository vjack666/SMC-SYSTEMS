"""ict_backtest/setups/rr_map.py — RR POR SETUP (MDS_RR_POR_SETUP, SPEC §20).

Mapea cada senal ICT a su RR objetivo segun el setup detectado:

    Silver Bullet  -> 1:2   (libro 07 #5, SPEC §17)
    Turtle Soup    -> 1:1.5 (tesis 20 §9)
    OTE            -> 1:3   (default)
    default        -> 1:3   (PO3 / setup no reconocido)

RESPONSABILIDAD LIMITADA (importante, ver MDS §3):
    Este modulo SOLO RESUELVE y ANOTA el RR objetivo de la senal en
    ``sig.rr_target``. NO calcula el TP ni modifica entry/SL/TP: la
    APLICACION de ``rr_target`` al calculo del take-profit queda para la
    integracion del orquestador (cuando el motor pase el setup detectado a
    ``rr_ok`` / al calculo de TP en canonical/engine). Hoy el motor fuerza
    RR fijo (canonical usa ``* 3.0 * risk``); este mapa es la fuente de
    verdad por-setup que el orquestador consultara, sin tocar el motor actual.

CONTRATO CON ICTSignal (engine.py, NO editado):
    ICTSignal aun no expone flags de setup ni ``rr_target``. Por eso:
      - ``flag_rr`` usa getattr(..., False) defensivo para leer
        ``sb_confirmed`` / ``turtle_confirmed`` / ``ote_confirmed``
        (los seteara el futuro detector de setup).
      - ``flag_rr`` escribe ``sig.rr_target`` via setattr, asi funciona tanto
        en ICTSignal real como en dobles ligeros de test.
"""
from __future__ import annotations

from typing import Iterable, List, Optional

# RR objetivo por setup. SPEC §20 / libro 07 #5 / tesis 20 §9.
RR_BY_SETUP: dict[str, float] = {
    "silver_bullet": 2.0,   # 1:2
    "turtle_soup": 1.5,     # 1:1.5
    "ote": 3.0,             # 1:3
    "default": 3.0,         # PO3 y setups no reconocidos -> 1:3
}

_DEFAULT_SETUP = "default"


def rr_for(setup_name: Optional[str]) -> float:
    """RR objetivo del setup, o el default 3.0 si es None/desconocido.

    >>> rr_for("silver_bullet")
    2.0
    >>> rr_for(None)
    3.0
    >>> rr_for("po3")
    3.0
    """
    if setup_name is None:
        return float(RR_BY_SETUP[_DEFAULT_SETUP])
    return float(RR_BY_SETUP.get(setup_name, RR_BY_SETUP[_DEFAULT_SETUP]))


def _setup_of(sig) -> str:
    """Resuelve el nombre del setup de una senal.

    Precedencia declarada: Silver Bullet > Turtle Soup > OTE > default.
    Los flags se leen con getattr defensivo porque ICTSignal (engine.py) aun
    no los declara; el futuro detector los seteara. Si ninguno esta presente
    devuelve "default".
    """
    sb = bool(getattr(sig, "sb_confirmed", False))
    turtle = bool(getattr(sig, "turtle_confirmed", False))
    ote = bool(getattr(sig, "ote_confirmed", False))
    if sb:
        return "silver_bullet"
    if turtle:
        return "turtle_soup"
    if ote:
        return "ote"
    return _DEFAULT_SETUP


def flag_rr(signals: Iterable) -> List:
    """Anota ``sig.rr_target`` en cada senal segun su setup detectado.

    Mutacion in-place (setattr) y retorna la misma lista recibida para
    encadenar. NO edita engine.py ni altera entry/SL/TP: solo resuelve y
    anota el RR objetivo (ver docstring del modulo).

    Args:
        signals: iterable de ICTSignal (u objetos con los flags opcionales).

    Returns:
        La misma lista, con ``rr_target`` asignado a cada elemento.
    """
    # Conserva la misma lista recibida (si ya es list) para que el call-site
    # pueda encadenar/comparar por identidad; sino devuelve una nueva.
    sigs = signals if isinstance(signals, list) else list(signals)
    for sig in sigs:
        setup = _setup_of(sig)
        setattr(sig, "rr_target", rr_for(setup))
    return sigs
