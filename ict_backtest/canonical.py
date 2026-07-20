"""R7 — Single source of truth for ICT decision.

Only public decision API for the in-scope R7 surface:

    evaluate_signals(...)  -> list[ICTSignal]
    latest_plan(...)       -> dict | None   (for observador / live)

Canonical engine: ``sequence.run_sequence`` (+ structural SL / RR 1:3 / killzone).

Out of R7 implementation scope (documented debt — not invisible):
  - legacy/backtest/engine.py  — accepted as DEBT; not rewired here
  - ml/dataset_builder.py      — accepted as DEBT; still uses legacy

Those must not be treated as a second "official" ICT motor for new work.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ict_backtest._util import (
    avg_candle_range,
    closed_row_at_time,
    tf_duration,
)
from ict_backtest.engine import (
    STRUCT_SL_MAX_RANGE,
    ICTSignal,
    calc_structural_sl,
    fill_entry_price,
    _tp_liquidity,
)
from ict_backtest.htf_pd_index import HtfPdIndex
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.multitf_context import MultiTFContext, build_multitf_context, extract_htf_layer
from ict_backtest.poi_anchor_motor import compute_htf_anchored
from ict_backtest.dealing_range_motor import compute_zone_class
from ict_backtest.po3_motor import compute_po3_complete, Po3MotorConfig
from ict_backtest.rules import killzone_en
from ict_backtest.sequence import SequenceConfig, run_sequence
from ict_backtest.zone_authority import evaluate_zone_authority

CANONICAL_ENGINE = "sequence"

# Explicit R7 debt (DoD H2/H3) — not migrated in this change.
R7_DOCUMENTED_DEBT = (
    "legacy/backtest/engine.py",
    "ml/dataset_builder.py",
)


def load_bos_table() -> dict | None:
    """Load empirical bos_table if present (R10); else None -> sequence fallback."""
    from pathlib import Path
    import json

    path = Path(__file__).resolve().parent / "bos_table.json"
    if not path.exists():
        return None
    try:
        return {int(k): int(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
    except (ValueError, OSError):
        return None


def evaluate_signals(
    symbol: str,
    htf: str,
    ltf: str,
    *,
    counter_trend: bool = False,
    tp_mode: str = "fixed2r",
    require_displacement: bool = True,
    displace_gap: int = 6,
    bos_gap: int | None = 10,
    bos_table: dict | None = None,
    frames: dict | None = None,
    fill_mode: str = "next_open",
    enable_pd_index: bool = False,
) -> list[ICTSignal]:
    """Canonical ICT signal generator (R7).

    Event-sequence sweep→displace→BOS→return, structural SL, RR≥1:3, killzone.

    ``enable_pd_index`` activa la Fase C (capa de autoridad de zonas HTF):
    construye HtfPdIndex y anota ``zone_authority`` en cada señal. Si esta
    False (modo historico), NO se paga el costo de detectar FVG/OB del HTF y
    el comportamiento es identico al de antes de Fase C (C desactivado).
    """
    if bos_table is None:
        bos_table = load_bos_table()
    if frames is None:
        from ict_backtest.data_feed import load_frames

        # Fase 1 (lectura multitemporal): cargar TODA la cadena D1/H4/H1/M15/M5/M1.
        # Los datos de 6 TF ya están en disco (EURUSD/XAUUSD/GBPUSD/...); el
        # cuello de botella era que el motor solo leía [htf, ltf, "D1"].
        tfs = ("D1", "H4", "H1", "M15", "M5", "M1")
        frames = load_frames(symbol, tfs)

    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[ltf]
    htf_df = ms.get(htf, ltf_df)

    # --- Fase C (C1): indice de PD arrays HTF vigentes (plumbing que faltaba) ---
    # Solo los TF HTF (no el LTF) alimentan el evaluador de autoridad de zonas.
    # CONTRATO: el indice SOLO se construye si enable_pd_index=True. Con False
    # (modo historico) el comportamiento es identico al de antes de Fase C y no
    # se paga el costo de detectar FVG/OB del HTF.
    htf_frames = {tf: df for tf, df in frames.items() if tf != ltf}
    htf_pd_index = HtfPdIndex(htf_frames) if (enable_pd_index and htf_frames) else None
    # Mapa LTF->HTF resuelto UNA sola vez (O(n), no O(n^2)). Se pasa al
    # motor para lookup O(1) por barra (ver sequence.run_sequence).
    ltf_map = htf_pd_index.build_ltf_map(ltf_df) if htf_pd_index is not None else None

    # --- Fase 1 (lectura multitemporal): est_htf_ctx_fn devuelve el
    # MultiTFContext closed-only de TODA la cadena en t. run_sequence usa
    # extract_htf_layer(context, htf) para seguir decidiendo con el MISMO
    # HTF de hoy (Opción A): comportamiento 100% idéntico al baseline.
    # Los otros 5 TF viajan disponibles en el contexto pero aún no influyen.
    def est_htf_ctx_fn(i: int) -> "MultiTFContext":
        t = ltf_df.iloc[i]["time"]
        anchored = None
        if htf_pd_index is not None and ltf_map is not None:
            anchored = {}
            for tf_ in htf_pd_index.timeframes:
                zs = htf_pd_index.zones_at(i, tf_, ltf_map)
                if zs:
                    anchored[tf_] = zs
        return build_multitf_context(
            ms, t, tfs=("D1", "H4", "H1", "M15", "M5", "M1"),
            anchored_pd_zones=anchored,
        )

    # Fallback legacy: si run_sequence se llamara sin est_htf_ctx_fn, este
    # est_htf_fn devuelve el dict plano idéntico al de antes (extract_htf_layer
    # sobre el contexto). Mantiene compatibilidad con el 2º arg posicional.
    def est_htf_fn_legacy(i: int) -> dict:
        return extract_htf_layer(est_htf_ctx_fn(i), htf)

    raw_sigs, _ = run_sequence(
        ltf_df,
        est_htf_fn_legacy,  # 2º arg (est_htf_fn legacy): dict plano válido.
        SequenceConfig(
            counter_trend=counter_trend,
            tp_mode=tp_mode,
            require_displacement=require_displacement,
            displace_gap=displace_gap,
            bos_gap=bos_gap,
        ),
        ltf_tf=ltf,
        bos_table=bos_table,
        htf_pd_index=htf_pd_index,
        ltf_map=ltf_map,
        htf=htf,
        est_htf_ctx_fn=est_htf_ctx_fn,
    )

    signals: list[ICTSignal] = []
    # FUENTE ÚNICA de volatilidad/riesgo: rango promedio (high-low) del LTF.
    # Migrado de la columna `atr` (inexistente en el ms, lo que mataba el
    # filtro). Mismo contrato: serie alineada al índice de ltf_df.
    rng_series = avg_candle_range(ltf_df, window=50)
    for s in raw_sigs:
        direction = s["direction"]
        entry_at = s["entry_at"]
        entry_row = ltf_df.iloc[entry_at]
        try:
            entry = fill_entry_price(ltf_df, entry_at, fill_mode)
        except ValueError:
            continue
        # Volatilidad de contexto = rango promedio en la barra de entrada.
        rng = float(rng_series.iloc[entry_at]) if entry_at < len(rng_series) else 0.0
        if not (rng > 0):
            continue
        kz = killzone_en(pd.to_datetime(entry_row["time"], utc=True))
        if kz not in ("London Open", "New York AM", "New York PM"):
            continue
        sweep_row = ltf_df.iloc[s["sweep_at"]]
        sl = calc_structural_sl(sweep_row, direction, rng)
        if sl is None:
            continue
        risk = abs(entry - sl)
        if risk <= 0 or risk > STRUCT_SL_MAX_RANGE * rng:
            continue
        liq = _tp_liquidity(entry_row, direction)
        if liq is not None:
            tp = liq
        else:
            tp = entry + 3.0 * risk if direction == 1 else entry - 3.0 * risk
        if direction == 1 and tp <= entry + 2.0 * risk:
            tp = entry + 3.0 * risk
        if direction == -1 and tp >= entry - 2.0 * risk:
            tp = entry - 3.0 * risk
        # --- Brecha C (Opción 2): clase de zona según dealing range HTF ---
        htf_ms = ms.get(htf, ltf_df)
        htf_row = closed_row_at_time(htf_ms, ltf_df.iloc[s["entry_at"]]["time"],
                                     tf_duration(htf))
        zone_class = compute_zone_class(
            sig_dir=direction,
            entry=entry,
            swing_high_htf=float(htf_row["swing_high"]) if htf_row is not None else None,
            swing_low_htf=float(htf_row["swing_low"]) if htf_row is not None else None,
        )
        # --- Brecha E (Opción 2): ciclo PO3/AMD completo al momento de entry ---
        # Estructura con velas CERRADAS <= entry_at (anti look-ahead).
        po3_structure: dict = {}
        for tf_key, tf_df in ms.items():
            sub = tf_df.iloc[: s["entry_at"] + 1]
            if len(sub) == 0:
                continue
            last = sub.iloc[-1]
            po3_structure[tf_key] = {
                "trend": str(last.get("trend", "")),
                "sweep_up": bool(last.get("sweep_up", False)),
                "sweep_down": bool(last.get("sweep_down", False)),
                "bos_dir": int(last.get("bos_dir", 0) or 0),
                "bos_status": str(last.get("bos_status", "")),
                "choch_status": str(last.get("choch_status", "")),
                "fvg_state": str(last.get("fvg_state", "")),
                "ob_dir": str(last.get("ob_dir", "")),
                "session_range": str(last.get("session_range", "")),
                "session_open": float(last.get("open", "nan")) if tf_key == "D1" else None,
            }
        htf_bias = str(htf_ms.iloc[s["entry_at"]]["trend"]) if len(htf_ms) > s["entry_at"] else ""
        po3_complete = compute_po3_complete(
            po3_structure if po3_structure else None,
            config=Po3MotorConfig(bias=htf_bias, exec_tf=ltf, htf=htf),
        )

        signals.append(
            ICTSignal(
            symbol=symbol,
            time=s["time"],
            direction=direction,
            entry=entry,
            stop_loss=sl,
            take_profit=tp,
            model="sequence",
            sweep_at=s["sweep_at"],
            bos_at=s["bos_at"],
            entry_at=s["entry_at"],
            zone_authority=s.get("zone_authority"),
            htf_anchored=compute_htf_anchored(
                sig_dir=direction, entry_at=s["entry_at"],
                htf_pd_index=htf_pd_index, ltf_map=ltf_map,
            ),
            zone_class=zone_class,
            po3_complete=po3_complete,
            )
        )
    return signals


def latest_plan(
    symbol: str,
    htf: str = "H4",
    ltf: str = "M15",
    *,
    frames: dict | None = None,
    max_age_bars: int = 48,
) -> dict[str, Any] | None:
    """Last canonical signal as a live plan dict, or None.

    Used by the observador so Lab/LIMIT share the same brain as sequence.
    ``max_age_bars``: ignore signals whose entry_at is older than this many
    bars from the end of the LTF series (stale setups).
    """
    signals = evaluate_signals(symbol, htf, ltf, frames=frames, enable_pd_index=True)
    if not signals:
        return None
    sig = signals[-1]
    # Optional freshness when frames available
    if frames is not None and ltf in frames and sig.entry_at is not None:
        n = len(frames[ltf])
        if n - 1 - int(sig.entry_at) > max_age_bars:
            return None
    side = "LONG" if sig.direction == 1 else "SHORT"
    risk = abs(sig.entry - sig.stop_loss)
    reward = abs(sig.take_profit - sig.entry)
    rr = (reward / risk) if risk > 0 else 0.0
    plan = {
        "engine": CANONICAL_ENGINE,
        "symbol": sig.symbol,
        "side": side,
        "direction": sig.direction,
        "entry": float(sig.entry),
        "sl": float(sig.stop_loss),
        "tp": float(sig.take_profit),
        "rr": float(rr),
        "time": str(sig.time),
        "model": sig.model,
        "sweep_at": sig.sweep_at,
        "bos_at": sig.bos_at,
        "entry_at": sig.entry_at,
    }
    # Fase C (C3): la autoridad de la zona es INFORMACION para el operador
    # (humor del mercado / "donde mirar"), no un filtro.
    za = sig.zone_authority
    if za is not None:
        plan["zone_authority"] = {
            "has_htf_anchor": za.has_htf_anchor,
            "tier": za.tier,
            "stacking_level": za.stacking_level,
            "confidence_weight": za.confidence_weight,
            "level": za.level,
        }
    return plan
