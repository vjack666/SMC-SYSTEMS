"""ict_backtest/engine.py — Motor event-driven (vela a vela) rescatado.

Rescata la simulacion de legacy/backtest/engine.py (_build_signals_from_context
+ _simulate_trade_with_stats), SIN ML ni dependencias del legacy. El bucle de
simulacion es barra por barra: por cada senal, avanza vela a vela hasta SL/TP/
limite de hold. Eso es lo que pediste: no procesar todo de golpe.

Para ICT no usamos ScalpingSignal del legacy; definimos ICTSignal propio con
SL/TP derivados de la regla (structural SL + TP en liquidez opuesta, RR>=1:2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from ict_backtest.trade_mgmt import apply_trade_management  # Fase 1.2 wiring (call-site real)


@dataclass
class ICTSignal:
    symbol: str
    time: str
    direction: int          # +1 long, -1 short
    entry: float
    stop_loss: float
    take_profit: float
    model: str = ""         # "intradia" | "scalping"
    confidence: float = 0.0
    # Metadatos de indices de la secuencia canonica (R7 T3.1): permiten
    # trazabilidad de la senal sin alterar la simulacion (entry/SL/TP).
    sweep_at: int | None = None
    bos_at: int | None = None
    entry_at: int | None = None
    # Fase C (C2/C3): ZoneAuthority anotada (peso de confianza de zona).
    # Metadato de percepcion; NO altera entry/SL/TP ni el conteo de senales.
    zone_authority: Any = None
    # Brecha B (Opción 2, 2026-07-20): ancla POI HTF padre en la direccion de
    # la senal. Metadato de percepcion (NO filtra: principio Brecha D). None si
    # enable_pd_index=False (modo historico). Se calcula en post-proceso, sin
    # tocar run_sequence (radio de explosion minimo).
    htf_anchored: bool | None = None
    # Brecha A (Fase C, 2026-07-20): ¿habia POI HTF anclado en la
    # direccion de la senal al momento de la entrada? BONUS de autoridad de
    # zona (NO filtra: principio Fase E / Brecha D). None si
    # enable_pd_index=False (modo historicor). Se calcula en run_sequence
    # via htf_poi_fn (hook poi_ok), NO altera entry/SL/TP ni el conteo.
    poi_present: bool | None = None
    # Brecha C (Opción 2, 2026-07-20): clase de zona de la entrada segun el
    # dealing range del swing HTF (PREMIUM/DISCOUNT/EQ). Metadato de percepcion
    # (NO filtra: principio Brecha D). None si no hay swing HTF disponible.
    zone_class: str | None = None
    # Brecha E (Opción 2, 2026-07-20): ciclo PO3/AMD completo al momento de la
    # entrada. Metadato de percepcion (NO filtra: principio Brecha D). None si
    # no hay datos de estructura (modo historico).
    po3_complete: bool | None = None
    # B3 (2026-07-20): objetivo de liquidez EXTERNAL (PDH/PDL del dia previo)
    # anotado como metadato para Trade Management (E1). El TP primario sigue
    # siendo internal (bsl/ssl). None si no hay dia previo o modo historico.
    external_tp: float | None = None
    # R3.5: flags de setups canónicos como metadatos (Brecha D: no vetan).
    breaker_active: bool | None = None
    breaker_type: str | None = None
    mitigation_level: float | None = None
    breaker_strength: float | None = None
    ote_confirmed: bool | None = None
    ote_zone: tuple[float, float] | None = None
    smt_divergence_active: bool | None = None
    smt_divergence_direction: int | None = None
    smt_divergence_strength: float | None = None
    # POI quality (2026-07-23): tipo de zona PD donde ocurre la entrada
    # ("OB", "FVG", "NONE", etc.). Propagado desde sequence.py state.zone_pd_type.
    # Usado por poi_quality.py para scoring y filtro de reacción.
    zone_pd_type: str | None = None


@dataclass
class ICTTrade:
    symbol: str
    entry_time: str
    exit_time: str
    direction: int
    entry: float
    exit: float
    pnl_r: float            # PnL en unidades de riesgo (RR)

def fill_entry_price(frame: pd.DataFrame, entry_at: int, fill_mode: str) -> float:
    """Precio de ENTRADA segun el modo de fill (R6.2 / G2).

    - 'next_open'  (default produccion): open de la vela SIGUIENTE a la senal.
      Es el fill realista: no puedes entrar al close de la vela que acaba de
      cerrar; la orden se ejecuta al abrir la siguiente.
    - 'signal_close' (theory/paper): close de la vela de senal. Sobre-estima el
      fill (la trampa del R4). Solo para modo teoria con --no-cost.

    Levanta ValueError si el modo es desconocido (contrato cerrado, no 'modo
    abierto' silencioso).
    """
    if fill_mode == "next_open":
        nxt = entry_at + 1
        if nxt >= len(frame):
            raise ValueError("fill next_open: no hay vela siguiente al entry_at")
        return float(frame.iloc[nxt]["open"])
    if fill_mode == "signal_close":
        return float(frame.iloc[entry_at]["close"])
    raise ValueError(f"fill_mode desconocido: {fill_mode!r} (use 'next_open'|'signal_close')")


def simulate_trade(frame: pd.DataFrame, signal: ICTSignal,
                  max_hold_bars: int, cost: dict | None = None,
                  *, trade_mgmt: bool = False) -> tuple[ICTTrade | None, dict[str, Any]]:
    """Simula UN trade vela a vela hasta SL/TP/hold_limit. (Rescatado legacy.)

    cost: dict opcional con costos de transaccion realistas:
      - spread_pips:   medio spread en pips (EURUSD~1.0, XAUUSD~2-3)
      - commission_pips: comision ida+vuelta en pips
      - slippage_pips: slippage promedio en pips (adverso al trade)
    Sin cost (cost=None) se conserva el comportamiento teorico anterior.

    trade_mgmt (Fase 1.2, E1, libro 18/20): si True, tras la simulacion
    SL/TP simple se re-simula el trade con gestion post-entry real
    (BE + partial exit + trailing) via `apply_trade_management`. El PnL /
    exit_reason resultantes reflejan la gestion. Si False (default), el
    comportamiento es IDENTICO al historico (regresion cero).
    """
    # tamaño de pip segun el rango de precios (FX 4 dec => 0.0001; XAU ~0.01)
    ref_price = float(signal.entry)
    pip = 0.01 if ref_price >= 10 else 0.0001

    spread = (cost or {}).get("spread_pips", 0.0) * pip
    comm = (cost or {}).get("commission_pips", 0.0) * pip
    slip = (cost or {}).get("slippage_pips", 0.0) * pip

    times = frame["time"].astype(str)
    matches = list(frame.index[times == signal.time])
    if len(matches) == 0:
        return None, {"exit_reason": "time_not_found", "mfe_r": 0.0, "mae_r": 0.0, "hold_bars": 0}

    idx = int(matches[0])
    sl, tp = signal.stop_loss, signal.take_profit
    # Entrada con slippage ADVERSO + medio spread (peor para el trader).
    dirn = 1 if signal.direction == 1 else -1
    entry_fill = signal.entry + dirn * (slip + spread / 2.0)
    # Risk respecto al entry REAL (antes del empuje de costo): si el SL queda
    # a <1 pip del entry, el trade es invalido (SL mal ubicado del motor:
    # evita R absurdos por division por risk ~0 en hold_limit lejano).
    risk_real = abs(signal.entry - sl)
    min_risk = 1.0 * pip
    if risk_real <= min_risk:
        return None, {"exit_reason": "invalid_risk", "mfe_r": 0.0, "mae_r": 0.0, "hold_bars": 0}
    risk = abs(entry_fill - sl)

    exit_idx, exit_price, exit_reason = idx, entry_fill, "hold_limit"
    mfe_r, mae_r = -1e9, 1e9
    pnl_r = 0.0  # inicializado; recalculado abajo (o por trade_mgmt)

    for step in range(1, max_hold_bars + 1):
        j = idx + step
        if j >= len(frame):
            break
        row = frame.iloc[j]
        high, low = float(row["high"]), float(row["low"])

        if signal.direction == 1:
            step_mfe = (high - entry_fill) / risk
            step_mae = (low - entry_fill) / risk
            if low <= sl:
                exit_idx, exit_price, exit_reason = j, sl, "SL"
                mfe_r, mae_r = max(mfe_r, step_mfe), min(mae_r, step_mae)
                break
            if high >= tp:
                exit_idx, exit_price, exit_reason = j, tp, "TP"
                mfe_r, mae_r = max(mfe_r, step_mfe), min(mae_r, step_mae)
                break
        else:
            step_mfe = (entry_fill - low) / risk
            step_mae = (entry_fill - high) / risk
            if high >= sl:
                exit_idx, exit_price, exit_reason = j, sl, "SL"
                mfe_r, mae_r = max(mfe_r, step_mfe), min(mae_r, step_mae)
                break
            if low <= tp:
                exit_idx, exit_price, exit_reason = j, tp, "TP"
                mfe_r, mae_r = max(mfe_r, step_mfe), min(mae_r, step_mae)
                break
        exit_idx, exit_price = j, float(row["close"])
        mfe_r, mae_r = max(mfe_r, step_mfe), min(mae_r, step_mae)
    # --- Fase 1.2 (E1, libro 18/20): re-simular con gestion post-entry real ---
    # Si trade_mgmt=True, aplicamos BE + partial + trailing SOBRE la sub-serie
    # post-entry (mismo rango que el loop SL/TP simple) y sobreescribimos la
    # salida con la del modulo ya testeado (apply_trade_management). Esto es
    # wiring puro: NO se toca la logica de to_breakeven/partial_exit/trailing.
    # El PnL del modulo es en R; le restamos la comision igual que el base.
    # Si trade_mgmt=False (default), el bloque se salta y queda IDENTICO.
    if trade_mgmt:
        sub_df = frame.iloc[idx: idx + max_hold_bars + 1]
        tm = apply_trade_management(
            entry=float(entry_fill), sl=float(sl), tp=float(tp),
            direction=int(signal.direction), df=sub_df,
        )
        tm_reason = tm["exit_reason"]
        reason_map = {"tp": "TP", "sl": "SL", "be": "BE",
                      "trailing": "TRAILING", "open": "hold_limit"}
        exit_reason = reason_map.get(tm_reason, "hold_limit")
        exit_price = float(tm["exit_price"])
        # PnL ya ponderado (parcial + remanente) por apply_trade_management;
        # solo restamos comision en precio. Se respeta abajo (no se recalcula).
        pnl_r = (float(tm["pnl_r"]) * risk - comm) / risk if risk > 0 else 0.0
    # Salida: pnl en R. El costo de comision se resta en PRECIO (no /risk),
    # para no inflar pnl_r cuando risk es pequeño (FIX R6.3). Si trade_mgmt
    # esta activo, pnl_r ya fue calculado arriba (PnL ponderado del modulo).
    pnl_price = (exit_price - entry_fill) if signal.direction == 1 else (entry_fill - exit_price)
    if not trade_mgmt:
        pnl_r = (pnl_price - comm) / risk
    trade = ICTTrade(
        symbol=signal.symbol, entry_time=signal.time,
        exit_time=str(frame.iloc[exit_idx]["time"]), direction=signal.direction,
        entry=entry_fill, exit=exit_price, pnl_r=float(pnl_r),
    )
    hold_bars = max(0, int(exit_idx - idx))
    if mfe_r < -1e8:
        mfe_r = 0.0
    if mae_r > 1e8:
        mae_r = 0.0
    return trade, {"exit_reason": exit_reason, "mfe_r": float(mfe_r), "mae_r": float(mae_r), "hold_bars": hold_bars}


def simulate_trade_with_context(
    frame: pd.DataFrame, signal: "ICTSignal", max_hold_bars: int,
    cost: dict | None = None, *, est_htf_fn=None, ltf_tf: str = "M15",
    backtest_id: str = "",
    market_stack: dict[str, Any] | None = None,
    trade_mgmt: bool = False,
) -> tuple["ICTTrade | None", dict[str, Any], RawDiagnosticData | None]:
    """EMITE RawDiagnosticData para el Diagnosis Engine (Fase D, Paso 2 + multi-TF).

    NO construye TradeContext (esa es responsabilidad de
    `diagnostics.context_builder.build_trade_context`). Solo SIMULA el trade
    (igual que `simulate_trade`) y empaqueta los datos disponibles en
    simulacion para que el builder los congele.

    El PnL / exit_reason son IDENTICOS a `simulate_trade` (R1 de Paso 2: no
    altera el resultado de la simulacion). Si el trade es None (filtro de
    riesgo / tiempo no encontrado), emite RawDiagnosticData=None.

    est_htf_fn(i) opcional: si se pasa, se usa para poblar htf_context del
    builder (trend/sweep). Si es None, el builder usa defaults (no inventa).
    market_stack opcional: stack closed-only multi-TF {tf: snapshot} que el
    builder congela en TradeContext.market_context (Fase D multi-TF). Si es
    None, market_context queda None (contexto v1 sigue valido).
    """
    trade, meta = simulate_trade(frame, signal, max_hold_bars, cost=cost,
                                trade_mgmt=trade_mgmt)
    if trade is None:
        return None, meta, None

    # fila LTF en signal.time (para atr_z / sl_is_structural si existen)
    row: dict[str, Any] = {}
    try:
        times = frame["time"].astype(str)
        matches = list(frame.index[times == signal.time])
        if matches:
            r = frame.iloc[int(matches[0])]
            row = {k: r.get(k) for k in ("atr", "atr_z", "sl_is_structural",
                                         "dist_entry_to_sl_r")}
    except (KeyError, ValueError, IndexError):
        row = {}

    htf_context: dict[str, Any] | None = None
    if est_htf_fn is not None:
        try:
            htf_context = est_htf_fn(int(getattr(signal, "entry_at", 0) or 0))
        except (TypeError, ValueError, KeyError):
            htf_context = None

    raw = RawDiagnosticData(
        signal=signal, trade=trade, meta=meta, row=row,
        htf_context=htf_context, backtest_id=backtest_id,
        market_stack=market_stack,
    )
    return trade, meta, raw


# ---- helpers ----


def _coerce_ts(value: Any) -> pd.Timestamp | None:
    if value is None:
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.tz_convert("UTC") if ts.tz else ts.tz_localize("UTC")


def _build_estructura(frames: dict[str, pd.DataFrame], i: int,
                      ltf: str) -> dict[str, dict]:
    """Arma el dict estructura[tf] = {trend, bos_dir, bos_status, sweep_up, sweep_down, ...}
    leyendo la fila i de cada TF (o la mas cercana en tiempo)."""
    est: dict[str, dict] = {}
    ltf_time = frames[ltf].iloc[i]["time"] if ltf in frames else None
    # Frecuencia de cada TF para exigir cierre de la barra al hacer join
    # cross-timeframe (evita look-ahead: ver AUDIT_LOOKAHEAD_HTF.md).
    TF_FREQ = {
        "M1": pd.Timedelta(minutes=1), "M5": pd.Timedelta(minutes=5),
        "M15": pd.Timedelta(minutes=15), "H1": pd.Timedelta(hours=1),
        "H4": pd.Timedelta(hours=4), "D1": pd.Timedelta(days=1),
    }
    for tf, df in frames.items():
        if tf == ltf or len(df) == 0:
            pass
        # indice por tiempo si es posible. El TF != LTF exige barra ya cerrada
        # (freq) para no leer indicadores de una barra HTF aun en formacion.
        freq = TF_FREQ.get(tf) if tf != ltf else None
        row = _row_at_time(df, ltf_time, freq=freq) if ltf_time is not None else (df.iloc[i] if i < len(df) else None)
        if row is None:
            est[tf] = {}
            continue
        est[tf] = {
            "trend": str(row.get("macro_direction", row.get("trend", "RANGING"))),
            "bos_dir": int(row.get("bos_direction", 0) or 0),
            "bos_status": str(row.get("bos_status", "")),
            "choch_status": str(row.get("choch_signal", row.get("choch_status", ""))),
            "sweep_up": bool(row.get("liquidity_sweep_up", row.get("sweep_up", False))),
            "sweep_down": bool(row.get("liquidity_sweep_down", row.get("sweep_down", False))),
            "fvg_state": str(row.get("fvg_state", row.get("fvg_bullish", "-"))),
            "ob_dir": str(row.get("ob_direction", row.get("ob_dir", "-"))),
        }
    if ltf in frames:
        est[ltf] = est.get(ltf, {})
    return est


from ict_backtest._util import row_at_time as _row_at_time  # noqa: E402
from ict_backtest.diagnostics.context_builder import RawDiagnosticData  # noqa: E402


def _nearest_opposite_swing(
    df: pd.DataFrame, row: pd.Series, direction: int, close: float
) -> float | None:
    """Swing de liquidez OPUESTO mas cercano en precio al entry (tesis §13).

    Bug #2: la tesis exige el BSL/SSL opuesto MAS CERCANO que el precio toca
    yendo a favor, NO el promedio del cluster HTF. Para un long, ese objetivo
    es el ``swing_high`` ya formado mas bajo que este POR ENCIMA del entry
    (primer pool de buy-side liquidity que el precio alcanzara). Para un short,
    el ``swing_low`` mas alto que este POR DEBAJO del entry.

    ANTI-LOOK-AHEAD: solo se consideran swings de velas YA CERRADas en o antes
    de la vela de ``row`` (por ``time``). Nunca se leen swings futuros del TF.
    El swing es un pivote confirmado (columnas ``swing_high``/``swing_low`` que
    ``detect_market_structure`` publica con .shift, ya sin look-ahead), y aqui
    ademas lo recortamos al pasado por seguridad.

    Devuelve None si no hay swing valido (el caller cae al fallback RR).
    """
    col = "swing_high" if direction == 1 else "swing_low"
    if col not in df.columns:
        return None

    # Recorte anti look-ahead: solo velas con time <= el time del row.
    sub = df
    try:
        row_ts = pd.to_datetime(row.get("time"), utc=True, errors="coerce")
        if pd.notna(row_ts) and "time" in df.columns:
            df_ts = pd.to_datetime(df["time"], utc=True, errors="coerce")
            sub = df[df_ts <= row_ts]
    except (TypeError, ValueError, KeyError):
        sub = df
    if sub is None or not len(sub):
        return None

    try:
        vals = pd.to_numeric(sub[col], errors="coerce").dropna()
    except (TypeError, ValueError, KeyError):
        return None
    if vals.empty:
        return None

    arr = vals.to_numpy(dtype=float)
    if direction == 1:
        # buy-side liquidity POR ENCIMA del entry -> el mas bajo (mas cercano).
        above = arr[arr > close]
        if above.size == 0:
            return None
        return float(above.min())
    else:
        # sell-side liquidity POR DEBAJO del entry -> el mas alto (mas cercano).
        below = arr[arr < close]
        if below.size == 0:
            return None
        return float(below.max())


def _tp_liquidity(row: pd.Series, direction: int, df: pd.DataFrame | None = None) -> dict:
    """Jerarquia de liquidez para el TP (MDS_B3_LIQUIDEZ_INT_EXT, tesis §14).

    Devuelve dict con dos niveles de objetivo:
      - ``internal``: liquidez del swing reciente de la sesion/estructura
        (BSL si long / SSL si short). Es el TP PRIMARIO.
      - ``external``: liquidez macro del dia/semana previo
        (PDH si long / PDL si short). Objetivo macro para gestion (E1).

    El TP de la senal = internal (igual que antes: bsl_price/ssl_price).
    external se anota como metadato para Trade Management (E1).

    Regresion cero: sin ``df`` o sin dia previo, external=None y el
    comportamiento es identico al historico (usa solo internal/bsl-ssl).
    """
    out: dict = {"internal": None, "external": None}

    # --- internal: swing de liquidez opuesto MAS CERCANO al entry (tesis §13) ---
    # Bug #2 (AUDITORIA_FIDELIDAD, contradiccion 2): antes se usaba
    # bsl_price/ssl_price del row, que detect_liquidity produce como PROMEDIO
    # (``mid = mean(prices)``) del CLUSTER de swings. En rangos amplios ese
    # cluster queda lejano y el trade sale por hold_limit (7/11 EURUSD, 11/13
    # GBPUSD en v29). La tesis §13 exige el BSL/SSL opuesto MAS CERCANO en
    # PRECIO al entry ("primer swing de liquidez opuesta que el precio toca
    # yendo a favor").
    #
    # Resolucion: con ``df`` disponible, buscamos el swing_high (long) /
    # swing_low (short) ya FORMADO (anti look-ahead: solo velas cerradas <=
    # la vela de entry) mas cercano en precio por encima/por debajo del entry.
    # Sin ``df`` (llamada unitaria legacy) se conserva el fallback a
    # bsl_price/ssl_price del row -> regresion cero.
    close = None
    try:
        close = float(row["close"])
    except (TypeError, ValueError, KeyError):
        close = None

    nearest = None
    if df is not None and len(df) and close is not None:
        nearest = _nearest_opposite_swing(df, row, direction, close)

    if nearest is not None:
        out["internal"] = nearest
    else:
        # Fallback (df=None o sin swing valido): BSL/SSL del row (cluster mean).
        try:
            if direction == 1:
                bsl = float(row.get("bsl_price"))
                if pd.notna(bsl) and bsl > (close if close is not None else float(row["close"])):
                    out["internal"] = bsl
            else:
                ssl = float(row.get("ssl_price"))
                if pd.notna(ssl) and ssl < (close if close is not None else float(row["close"])):
                    out["internal"] = ssl
        except (TypeError, ValueError, KeyError):
            pass

    # --- external: PDH/PDL del dia previo en df (EQ = promedio de ambos) ---
    if df is not None and len(df):
        try:
            tcol = "time" if "time" in df.columns else None
            row_ts = pd.to_datetime(row.get("time"), utc=True, errors="coerce")
            if pd.notna(row_ts):
                if tcol is not None:
                    df_ts = pd.to_datetime(df[tcol], utc=True, errors="coerce")
                else:
                    df_ts = pd.to_datetime(df.index, utc=True, errors="coerce")
                row_day = row_ts.tz_convert("UTC").normalize() if row_ts.tz else row_ts.normalize()
                prev_mask = df_ts.dt.normalize() < row_day
                if prev_mask.any():
                    prev = df[prev_mask]
                    if direction == 1:
                        # PDH (y EQ high): maximo high del dia previo
                        out["external"] = float(prev["high"].max())
                    else:
                        # PDL (y EQ low): minimo low del dia previo
                        out["external"] = float(prev["low"].min())
        except (TypeError, ValueError, KeyError):
            pass

    return out


def _coerce_ts(value: Any) -> pd.Timestamp | None:
    if value is None:
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.tz_convert("UTC") if ts.tz else ts.tz_localize("UTC")


# Maximo ancho del SL estructural en RANGO (high-low promedio). Si el sweep
# fue gigante y el SL queda mas alla de esto, el RR se rompe -> el motor
# SALTA el trade (P5). Migrado de STRUCT_SL_MAX_ATR (ATR) a rango puro:
# misma magnitud de umbral (6.0) para medir impacto en Fase 2 (calibración).
STRUCT_SL_MAX_RANGE = 6.0


def calc_structural_sl(row: pd.Series, direction: int, rng: float) -> float | None:
    """Stop-loss estructural ICT (libro 14_STOP_LOSS_ESTRUCTURAL).

    Ancla el SL al NIVEL donde la tesis del trade se cae, NO a la volatilidad.
    Prioridad (ICT mistake #4: usar buffer, no 1 pip):
      1. Mechas del sweep (sweep_low/sweep_high) +- buffer (la fuente madre).
      2. Si no hay sweep: swing roto (swing_low/swing_high de BOS/CHOCH).
      3. Si tampoco: None -> el motor NO opera (no degrada a rango).
    El buffer evita que el spike post-sweep toque el stop por 1 pip.

    El buffer ahora usa el RANGO PROMEDIO (high-low) de la fuente única
    ``avg_candle_range`` (en vez de ATR), bajo la regla de matemática pura
    sin indicadores. Múltiplo equivalente inicial (0.3) para medir impacto.
    """
    from typing import cast
    buf = STRUCT_SL_BUFFER_RANGE * rng

    def _lvl(col: str) -> float | None:
        v = row.get(col, np.nan)
        fv = cast(float, v)
        if pd.isna(fv) or fv <= 0:
            return None
        return float(fv)

    if direction == 1:  # long: SL bajo la mecha que barrio la SSL
        sweep = _lvl("sweep_low")
        if sweep is not None:
            return sweep - buf
        swing = _lvl("swing_low")
        if swing is not None:
            return swing - buf
    else:  # short: SL sobre la mecha que barrio la BSL
        sweep = _lvl("sweep_high")
        if sweep is not None:
            return sweep + buf
        swing = _lvl("swing_high")
        if swing is not None:
            return swing + buf
    return None


# Buffer del SL estructural en RANGO (high-low promedio). ICT mistake #4:
# stops 1 pip past the level get tagged on the spike. 0.3 * rango da aire sin
# romper el RR. Migrado de STRUCT_SL_BUFFER_ATR (ATR) a rango puro (Fase 1).
STRUCT_SL_BUFFER_RANGE = 0.3


def _invalidation_level(estructura: dict, direction: int, exec_tf: str = "M15") -> float | None:
    """DEPRECADO: usado antes de calc_structural_sl. Conservado para
    referencia; el motor ya no lo llama (columna 'invalidation' nunca
    existio en el pipeline)."""
    m15 = estructura.get(exec_tf, {})
    inv = m15.get("invalidation") if isinstance(m15, dict) else None
    if inv is not None:
        try:
            v = float(inv)
            if np.isfinite(v) and v > 0:
                return v
        except (TypeError, ValueError):
            pass
    return None


if __name__ == "__main__":
    print("ict_backtest.engine cargado OK")
