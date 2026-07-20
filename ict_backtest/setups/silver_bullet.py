"""C2 — Silver Bullet (SB): setup de 'hora limpia' (libro 07 / 18 ICT).

Silver Bullet = retorno a una zona (FVG/OB) DENTRO de una killzone 'limpia'
tras un barrido (sweep) de liquidez reciente. Solo opera en:

  - London Open (07:00-10:00 UTC)  -> sb_killzone='L'
  - New York AM  (12:30-15:00 UTC) -> sb_killzone='NY_AM'

Fuera de esas ventanas NO opera (aunque haya estructura SB). NY PM NO es
killzone SB.

Diseno (principio Brecha D / leccion A''): este modulo SOLO ANOTA las senales
que produce ict_backtest.canonical.evaluate_signals. NO filtra ciego ni veta:
setea atributos dinamicos en el ICTSignal (sb_confirmed / sb_killzone). El filtro
duro queda como knob apagado (ver flag_silver_bullet). NO edita engine.py (el
campo no se agrega al dataclass ICTSignal) ni canonical.py.

Killzone: reusa ict_backtest.rules.killzone_en (NO se modifica). Devuelve
'London Open' / 'New York AM' / 'New York PM' / 'Asia' / 'London Close' / ''.

NO dependency en datos reales: todas las pruebas usan frames sinteticos.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Iterable, Sequence

import pandas as pd

from ict_backtest.engine import ICTSignal

# Killzones validas para Silver Bullet. Se mapea 'London Open' -> 'L'.
_SB_KILLZONES = {
    "London Open": "L",
    "New York AM": "NY_AM",
}


def _to_ts(value: Any) -> datetime | None:
    """Normaliza un timestamp (datetime / string / int de indice + frames)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        ts = value
    elif isinstance(value, (int, float)):
        # indice entero: no es timestamp por si solo; lo resuelve el caller via frames.
        return None
    else:
        ts = pd.to_datetime(value, utc=True, errors="coerce")
        if pd.isna(ts):
            return None
        ts = ts.to_pydatetime()
    if getattr(ts, "tzinfo", None) is None:
        ts = ts.replace(tzinfo=__import__("datetime").timezone.utc)
    return ts


def is_silver_bullet(
    sweep_ts: Any,
    return_ts: Any,
    direction: int,
    killzone_fn: Callable[[datetime], str],
) -> tuple[bool, dict]:
    """Decide si sweep+retorno constituyen un Silver Bullet valido.

    Requisitos:
      1. sweep_ts y return_ts caen en la MISMA killzone SB (London Open o NY AM).
      2. return_ts >= sweep_ts (el retorno es posterior al barrido).

    Args:
        sweep_ts: timestamp del barrido (datetime/str).
        return_ts: timestamp del retorno a zona / entry (datetime/str).
        direction: +1 long / -1 short (no se usa para vetar, solo se propaga).
        killzone_fn: killzone_en(ts) -> str (reusado de ict_backtest.rules).

    Returns:
        (True, meta) si es SB valido; (False, meta) en caso contrario.
        meta={'sb_killzone': 'L'|'NY_AM'|None, 'direction': direction,
              'sweep_kz': <str>, 'return_kz': <str>}.
    """
    sweep = _to_ts(sweep_ts)
    ret = _to_ts(return_ts)

    if sweep is None or ret is None:
        return False, {
            "sb_killzone": None, "direction": direction,
            "sweep_kz": None, "return_kz": None,
        }

    # El retorno (entry) es posterior al sweep (estructura SB: sweep -> displace -> return).
    if ret < sweep:
        return False, {
            "sb_killzone": None, "direction": direction,
            "sweep_kz": killzone_fn(sweep), "return_kz": killzone_fn(ret),
        }

    sweep_kz = killzone_fn(sweep)
    return_kz = killzone_fn(ret)

    sb_sweep = _SB_KILLZONES.get(sweep_kz)
    sb_return = _SB_KILLZONES.get(return_kz)

    if sb_sweep is not None and sb_sweep == sb_return:
        return True, {
            "sb_killzone": sb_sweep, "direction": direction,
            "sweep_kz": sweep_kz, "return_kz": return_kz,
        }

    return False, {
        "sb_killzone": None, "direction": direction,
        "sweep_kz": sweep_kz, "return_kz": return_kz,
    }


def _ts_from_index(frames: Any, idx: int | None) -> datetime | None:
    """Resuelve el timestamp de un indice LTF sobre el frame."""
    if frames is None or idx is None:
        return None
    try:
        return pd.to_datetime(frames.iloc[int(idx)]["time"], utc=True, errors="coerce").to_pydatetime()
    except (IndexError, KeyError, ValueError, AttributeError):
        return None


def flag_silver_bullet(
    signals: Sequence[ICTSignal],
    frames: Any = None,
    killzone_fn: Callable[[datetime], str] | None = None,
    *,
    hard_filter: bool = False,
) -> list[ICTSignal]:
    """Anota sb_confirmed / sb_killzone en cada ICTSignal de evaluate_signals.

    Para cada senal usa los indices sweep_at / entry_at (LTF) para resolver los
    timestamps contra ``frames`` (el frame LTF que contiene esos indices). Si no
    hay frames, intenta usar los enteros como indices sobre un df interno del
    caller (no aplica aqui; el test pasa el frame real).

    Side-effect intencional: setea atributos DINAMICOS en el ICTSignal:
        sig.sb_confirmed : bool
        sig.sb_killzone  : 'L' | 'NY_AM' | None
    NO edita engine.py (el dataclass no cambia).

    Principio Brecha D: por defecto hard_filter=False -> NO se descartan senales,
    solo se anotan. El veto duro queda como knob apagado (hard_filter=True
    devolveria solo las confirmadas).

    Args:
        signals: lista de ICTSignal que devuelve evaluate_signals.
        frames: frame LTF (pd.DataFrame) con columna 'time' para resolver indices.
        killzone_fn: killzone_en (default ict_backtest.rules.killzone_en).
        hard_filter: si True, devuelve solo las senales SB confirmadas.

    Returns:
        La misma lista de senales (anotadas). Con hard_filter=True se filtra.
    """
    from ict_backtest.rules import killzone_en as _default_kz

    kz_fn = killzone_fn or _default_kz
    ltf_df = frames if isinstance(frames, pd.DataFrame) else None

    out: list[ICTSignal] = []
    for sig in signals:
        sweep_ts = _ts_from_index(ltf_df, getattr(sig, "sweep_at", None))
        return_ts = _ts_from_index(ltf_df, getattr(sig, "entry_at", None))

        ok, meta = is_silver_bullet(
            sweep_ts, return_ts, int(getattr(sig, "direction", 0) or 0), kz_fn,
        )
        # Atributos dinamicos (NO se toca engine.py).
        sig.sb_confirmed = bool(ok)  # type: ignore[attr-defined]
        sig.sb_killzone = meta["sb_killzone"]  # type: ignore[attr-defined]

        if hard_filter and not ok:
            continue
        out.append(sig)
    return out
