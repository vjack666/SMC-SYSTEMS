"""Cache de datos entre ciclos del motor.

Evita recargar parquets y re-ejecutar analyze_timeframe si los datos
no cambiaron (mtime del archivo intacto). Alivia I/O de disco y CPU.

Uso:
  store_tfs_data(symbol, tfs_data)   — guarda después de un ciclo
  get_tfs_data()                     — recupera para canonical/mapas
  get_tfs_entry(symbol, tf)          — recupera un TF específico
  clear_cache()                      — fuerza recarga en próximo ciclo
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app_observador.config import DATA_RAW

# Cache: {(symbol, tf): {"df": DataFrame, "info": dict, "mtime": float}}
_tfs_cache: dict[tuple[str, str], dict[str, Any]] = {}


def _parquet_mtime(symbol: str, tf: str) -> float:
    """Devuelve mtime del parquet, 0 si no existe."""
    p = DATA_RAW / f"{symbol}_{tf}.parquet"
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def store_tfs_data(symbol: str, tfs_data: dict[str, tuple]) -> None:
    """Guarda los DataFrames + infos de un ciclo en cache.

    tfs_data es {tf: (df, info)} — exactamente lo que devuelve run_cycle.
    """
    for tf, (df, info) in tfs_data.items():
        mtime = _parquet_mtime(symbol, tf)
        _tfs_cache[(symbol, tf)] = {
            "df": df,
            "info": info,
            "mtime": mtime,
        }


def get_tfs_data(symbol: str | None = None) -> dict[str, tuple]:
    """Devuelve {tf: (df, info)} de lo cacheado.

    Si symbol es None, usa el primer symbol encontrado.
    """
    result: dict[str, tuple] = {}
    for (sym, tf), entry in _tfs_cache.items():
        if symbol is not None and sym != symbol:
            continue
        # Verificar que el mtime no haya cambiado (datos frescos)
        current = _parquet_mtime(sym, tf)
        if entry["mtime"] != current:
            # Archivo cambió — saltamos esta entrada (se recargará en próximo ciclo)
            continue
        result[tf] = (entry["df"], entry["info"])
    return result


def get_tfs_entry(symbol: str, tf: str) -> tuple | None:
    """Devuelve (df, info) para un symbol+tf específico, o None."""
    entry = _tfs_cache.get((symbol, tf))
    if entry is None:
        return None
    current = _parquet_mtime(symbol, tf)
    if entry["mtime"] != current:
        return None
    return (entry["df"], entry["info"])


def clear_cache() -> None:
    """Fuerza recarga completa en el próximo ciclo."""
    _tfs_cache.clear()


def store_analyzed(symbol: str, tf: str, info: dict) -> None:
    """Actualiza SOLO el info analizado (sin df) para un TF.

    Útil cuando PASS 2 ya cargó un TF (ej. M5) y queremos evitar
    duplicar analyze_timeframe en el loop scalping.
    """
    entry = _tfs_cache.get((symbol, tf))
    if entry is not None:
        entry["info"] = info
    else:
        _tfs_cache[(symbol, tf)] = {
            "df": None,
            "info": info,
            "mtime": _parquet_mtime(symbol, tf),
        }
