"""Bridge: observador levels -> EarnForex Position Sizer (file handoff).

Does NOT open trades. Writes Entry/SL/TP (+ side, risk %) so a small MQL5 EA
(SMC_PS_Bridge) can move PS_EntryLine / PS_StopLossLine / PS_TakeProfitLine
on the chart where Position Sizer is attached.

Handoff path (FILE_COMMON):
  %APPDATA%/MetaQuotes/Terminal/Common/Files/SMC/ps_levels.csv

Also mirrors into the known FundedNext terminal MQL5/Files for local debug.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app_observador.config import SYMBOL


# FundedNext / MetaQuotes terminal id used by this machine (Common is preferred).
DEFAULT_TERMINAL_ID = "89FE26BBBAB28C077BBF5FA8C1B4DF1C"
HANDOFF_REL = Path("SMC") / "ps_levels.csv"
DEFAULT_RISK_PCT = 1.0  # conservative default for prop demo; user adjusts in PS


@dataclass(frozen=True)
class TradeLevels:
    symbol: str
    side: str  # LONG | SHORT
    entry: float
    sl: float
    tp: float
    rr: float
    risk_pct: float = DEFAULT_RISK_PCT
    zone_note: str = ""
    valid_rr: bool = False  # True if R:R >= 2.0 (Stellar rule in Lab)

    def summary_lines(self) -> list[str]:
        ok = "VALIDO (R:R>=2)" if self.valid_rr else "RR bajo (Lab descartaria; demo ok)"
        return [
            f"Symbol: {self.symbol}",
            f"Side:   {self.side}",
            f"Entry:  {self.entry:.5f}",
            f"SL:     {self.sl:.5f}",
            f"TP:     {self.tp:.5f}",
            f"R:R:    1:{self.rr:.2f}  ({ok})",
            f"Risk%:  {self.risk_pct:.2f}  (Position Sizer ajusta el lotaje)",
        ]


def _appdata() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base)


def common_files_dir() -> Path:
    return _appdata() / "MetaQuotes" / "Terminal" / "Common" / "Files"


def terminal_files_dir(terminal_id: str = DEFAULT_TERMINAL_ID) -> Path:
    return (
        _appdata()
        / "MetaQuotes"
        / "Terminal"
        / terminal_id
        / "MQL5"
        / "Files"
    )


def handoff_paths(terminal_id: str = DEFAULT_TERMINAL_ID) -> list[Path]:
    """Ordered write targets: Common first (FILE_COMMON), then terminal Files."""
    paths = [common_files_dir() / HANDOFF_REL]
    term = terminal_files_dir(terminal_id) / HANDOFF_REL
    if term not in paths:
        paths.append(term)
    return paths


def extract_levels(
    result: dict | None,
    *,
    symbol: str = SYMBOL,
    risk_pct: float = DEFAULT_RISK_PCT,
    min_rr: float = 2.0,
) -> TradeLevels | None:
    """Build TradeLevels from engine.run_cycle() / last_cycle payload.

    R7 priority: use ``result["canonical"]`` from sequence when present.
    Fallback: Lab OTE midpoint + invalidation/target (legacy display path).
    """
    if not result:
        return None

    # --- R7 canonical path (sequence) ---
    can = result.get("canonical")
    if isinstance(can, dict) and can.get("entry") is not None and can.get("sl") is not None:
        try:
            entry = float(can["entry"])
            sl = float(can["sl"])
            tp = float(can.get("tp") or 0.0)
            side = str(can.get("side") or "").upper()
            if side not in ("LONG", "SHORT"):
                side = "LONG" if float(can.get("direction", 0)) > 0 else "SHORT"
            risk = abs(entry - sl)
            reward = abs(tp - entry) if tp else 0.0
            rr = float(can.get("rr") or ((reward / risk) if risk > 0 else 0.0))
            verd = result.get("veredicto") or {}
            return TradeLevels(
                symbol=str(can.get("symbol") or symbol),
                side=side,
                entry=entry,
                sl=sl,
                tp=tp,
                rr=rr,
                risk_pct=float(risk_pct),
                zone_note=str(verd.get("zone_note") or f"canonical {can.get('engine', 'sequence')}"),
                valid_rr=rr >= min_rr,
            )
        except (TypeError, ValueError):
            pass

    verd = result.get("veredicto") or {}
    estructura = result.get("estructura") or {}
    m15 = estructura.get("M15") or {}
    if not m15:
        return None

    votes = verd.get("votes") if isinstance(verd.get("votes"), dict) else None
    side = "NEUTRAL"
    if votes:
        if votes.get("LONG", 0) > votes.get("SHORT", 0):
            side = "LONG"
        elif votes.get("SHORT", 0) > votes.get("LONG", 0):
            side = "SHORT"
    if side == "NEUTRAL":
        bias = str(verd.get("bias") or result.get("bias") or "")
        if "LONG" in bias.upper() and "SHORT" not in bias.upper():
            side = "LONG"
        elif "SHORT" in bias.upper():
            side = "SHORT"
    if side not in ("LONG", "SHORT"):
        return None

    # Prefer canonical entry overlay on veredicto if partial
    if verd.get("canonical_entry") is not None and verd.get("invalidation") is not None:
        try:
            entry = float(verd["canonical_entry"])
            sl = float(verd["invalidation"])
            tp = float(verd.get("target") or 0.0)
            risk = abs(entry - sl)
            reward = abs(tp - entry) if tp else 0.0
            rr = (reward / risk) if risk > 0 else 0.0
            return TradeLevels(
                symbol=symbol,
                side=side,
                entry=entry,
                sl=sl,
                tp=tp,
                rr=rr,
                risk_pct=float(risk_pct),
                zone_note=str(verd.get("zone_note") or ""),
                valid_rr=rr >= min_rr,
            )
        except (TypeError, ValueError):
            pass

    invalid = verd.get("invalidation")
    target = verd.get("target")
    if invalid is None or target is None:
        return None

    ote = m15.get("ote_long") if side == "LONG" else m15.get("ote_short")
    if not ote or len(ote) < 2:
        return None
    try:
        lo, hi = float(ote[0]), float(ote[1])
        entry = (lo + hi) / 2.0
        sl = float(invalid)
        tp = float(target)
    except (TypeError, ValueError):
        return None

    risk = abs(entry - sl)
    reward = abs(tp - entry)
    rr = (reward / risk) if risk > 0 else 0.0
    return TradeLevels(
        symbol=symbol,
        side=side,
        entry=entry,
        sl=sl,
        tp=tp,
        rr=rr,
        risk_pct=float(risk_pct),
        zone_note=str(verd.get("zone_note") or ""),
        valid_rr=rr >= min_rr,
    )


def levels_to_csv(levels: TradeLevels, seq: int | None = None) -> str:
    """Simple key,value CSV — one field per line pair (MQL5 FileReadString friendly)."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if seq is None:
        seq = int(datetime.now(timezone.utc).timestamp())
    rows = [
        ("schema", "smc_ps_levels_v1"),
        ("seq", str(seq)),
        ("ts_utc", ts),
        ("symbol", levels.symbol),
        ("side", levels.side),
        ("entry", f"{levels.entry:.8f}"),
        ("sl", f"{levels.sl:.8f}"),
        ("tp", f"{levels.tp:.8f}"),
        ("rr", f"{levels.rr:.4f}"),
        ("risk_pct", f"{levels.risk_pct:.4f}"),
        ("valid_rr", "1" if levels.valid_rr else "0"),
        ("source", "smc_observador"),
        ("auto_trade", "0"),  # hard no — bridge never requests OrderSend
    ]
    return "\n".join(f"{k},{v}" for k, v in rows) + "\n"


def write_ps_handoff(
    levels: TradeLevels,
    *,
    terminal_id: str = DEFAULT_TERMINAL_ID,
    seq: int | None = None,
) -> list[Path]:
    """Write handoff file(s). Returns paths successfully written."""
    body = levels_to_csv(levels, seq=seq)
    written: list[Path] = []
    for path in handoff_paths(terminal_id):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
            written.append(path)
        except OSError:
            continue
    if not written:
        raise OSError(
            "No se pudo escribir el handoff a Common/Files ni a MQL5/Files. "
            "¿MetaQuotes Terminal instalado?"
        )
    return written


def send_result_to_position_sizer(
    result: dict | None,
    *,
    symbol: str = SYMBOL,
    risk_pct: float = DEFAULT_RISK_PCT,
) -> tuple[TradeLevels, list[Path]]:
    """Extract + write. Raises ValueError if no levels, OSError if write fails."""
    levels = extract_levels(result, symbol=symbol, risk_pct=risk_pct)
    if levels is None:
        raise ValueError(
            "No hay plan de trade usable (falta sesgo LONG/SHORT, OTE M15, "
            "invalidation o target). Esperá un setup con números en Lab Setup."
        )
    paths = write_ps_handoff(levels)
    # Also patch EarnForex PS_Settings so a reattach/reload shows the numbers.
    try:
        update_ps_settings_files(levels)
    except OSError:
        pass
    return levels, paths


def ps_settings_dir(terminal_id: str = DEFAULT_TERMINAL_ID) -> Path:
    return (
        _appdata()
        / "MetaQuotes"
        / "Terminal"
        / terminal_id
        / "MQL5"
        / "Files"
        / "PS_Settings"
    )


def update_ps_settings_files(
    levels: TradeLevels,
    *,
    terminal_id: str = DEFAULT_TERMINAL_ID,
) -> list[Path]:
    """Patch Entry/SL/TP into existing Position Sizer settings for the symbol.

    Position Sizer only reloads this file on attach/init. Live panel needs the
    patched EA (OnTimer handoff) OR a reattach. Still useful + verifiable on disk.
    """
    folder = ps_settings_dir(terminal_id)
    if not folder.is_dir():
        return []
    updated: list[Path] = []
    prefix = levels.symbol.upper()
    for path in folder.glob(f"{prefix}*.txt"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        mapping = {
            "EntryType": "1",  # Pending — keeps Entry editable / not Bid/Ask
            "EntryLevel": f"{levels.entry:.{5}f}",
            "StopLossLevel": f"{levels.sl:.{5}f}",
            "TakeProfitLevel": f"{levels.tp:.{5}f}",
            "Risk": f"{levels.risk_pct:.2f}",
            "SLDistanceInPoints": "0",
            "TPDistanceInPoints": "0",
            "ShowLines": "1",
        }
        # File format: alternating key / value lines
        out: list[str] = []
        i = 0
        seen = set()
        while i < len(lines):
            key = lines[i].strip()
            if i + 1 < len(lines) and key in mapping:
                out.append(key)
                out.append(mapping[key])
                seen.add(key)
                i += 2
                continue
            out.append(lines[i])
            i += 1
        for k, v in mapping.items():
            if k not in seen:
                out.append(k)
                out.append(v)
        try:
            path.write_text("\n".join(out) + "\n", encoding="utf-8")
            updated.append(path)
        except OSError:
            continue
    return updated


def place_limit_from_levels(
    levels: TradeLevels,
    *,
    mt5_path: str | None = None,
) -> dict:
    """Place LIMIT (or STOP if wrong side of market) with SL/TP via MetaTrader5."""
    from app_observador.core.mt5_status import MT5_PATH
    from risk.sizer import compute_lot, send_limit_order
    import MetaTrader5 as mt5

    path = mt5_path or MT5_PATH
    if not mt5.initialize(path=path):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        # Ensure symbol visible
        if not mt5.symbol_select(levels.symbol, True):
            raise RuntimeError(f"symbol_select {levels.symbol}: {mt5.last_error()}")
        sizing = compute_lot(
            levels.symbol,
            levels.entry,
            levels.sl,
            risk_percent=levels.risk_pct,
        )
        result = send_limit_order(
            levels.symbol,
            levels.side,
            levels.entry,
            levels.sl,
            levels.tp,
            volume=sizing.lot,
            risk_percent=levels.risk_pct,
            comment="SMC_OBS_LIMIT",
        )
        result["sizing"] = {
            "lot": sizing.lot,
            "risk_percent": sizing.risk_percent,
            "risk_money": sizing.risk_money,
            "sl_ticks": sizing.sl_ticks,
        }
        # Verify pending order is on book
        orders = mt5.orders_get(symbol=levels.symbol) or ()
        result["open_orders"] = [
            {
                "ticket": o.ticket,
                "type": o.type,
                "price_open": o.price_open,
                "sl": o.sl,
                "tp": o.tp,
                "volume": o.volume_current,
                "comment": o.comment,
            }
            for o in orders
        ]
        return result
    finally:
        # Do not shutdown — app may keep the connection for status panel.
        pass


def send_and_place_limit(
    result: dict | None,
    *,
    symbol: str = SYMBOL,
    risk_pct: float = DEFAULT_RISK_PCT,
) -> tuple[TradeLevels, list[Path], dict]:
    """Write handoff + PS settings, then place pending limit on MT5."""
    levels, paths = send_result_to_position_sizer(
        result, symbol=symbol, risk_pct=risk_pct
    )
    order = place_limit_from_levels(levels)
    return levels, paths, order
