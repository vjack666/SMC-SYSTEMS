"""ict_backtest/market_object.py — Objeto de mercado ICT (fuente canonica).

Un MarketObject es UNA estructura real del mercado con identidad: sabe su
capa de origen (origin_tf), su proposito (role), su estado por EVENTO
(state) y su lugar en la cadena causal (parent_object / related_objects).

Disenado en DISENO_ARQUITECTURA_OBJETOS_MERCADO.md y definido
conceptualmente en MARKET_OBJECT_MODEL.md (ontologia / contrato).

Regla dura de capa (tesis 18 / ontologia): el POI institucional SOLO existe
en HTF (D1/H4/H1). Un FVG/OB de M15 es siempre REFINEMENT.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import uuid


class ObjectType(str, Enum):
    BOS = "BOS"
    CHOCH = "CHOCH"
    FVG = "FVG"
    ORDER_BLOCK = "ORDER_BLOCK"
    LIQUIDITY = "LIQUIDITY"
    SWEEP = "SWEEP"


class Role(str, Enum):
    POI = "POI"
    REFINEMENT = "REFINEMENT"
    CONTEXT = "CONTEXT"


class ObjectState(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    MITIGATED = "MITIGATED"
    INVALIDATED = "INVALIDATED"
    CONSUMED = "CONSUMED"


# Capas permitidas para POI (ONTologia: POI solo en HTF).
_POI_TFS = {"D1", "H4", "H1"}


@dataclass
class MarketObject:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    type: ObjectType = ObjectType.FVG
    origin_tf: str = ""               # SELLO DE CAPA: obligatorio
    role: Role = Role.REFINEMENT
    direction: int = 0
    zone_high: float = 0.0
    zone_low: float = 0.0
    creation_time: object = None
    state: ObjectState = ObjectState.CREATED
    meta: dict = field(default_factory=dict)
    parent_object: str | None = None
    related_objects: list[str] = field(default_factory=list)
    quality_score: float | None = None

    def __post_init__(self) -> None:
        if not self.origin_tf:
            raise TypeError("origin_tf es obligatorio (sello de capa)")
        if self.role == Role.POI and self.origin_tf not in _POI_TFS:
            raise ValueError(
                f"POI solo en HTF ({sorted(_POI_TFS)}); recibido {self.origin_tf}"
            )
