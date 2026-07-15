"""ict_backtest/sequence.py — Capa 2: motor EVENT-SEQUENCE (memoria de eventos).

Arregla la raiz del problema que viste: el mini-check del dashboard evaluaba
sweep + BOS + displacement en la MISMA vela ("todo de golpe"). En ICT real los
eventos ocurren EN SECUENCIA y el mercado se revela en cascada (D1 -> H4 -> M15):

  1. SWEEP    : el precio barre una liquidez (BSL/SSL) en HTF o LTF.
  2. DISPLACE  : en las proximas N velas hay una vela de displacement fuerte
                en la direccion del setup (la "falla" de la que habla ICT).
  3. BOS/CHOCH : luego el precio rompe estructura (BOS continuacion o CHOCH giro)
                en esa direccion.
  4. ENTRY     : aparece un FVG/OB en la direccion -> se genera la senal.

Cada evento se recuerda vela a vela en SequenceState (memoria). Si pasa
max_gap velas sin avanzar, la secuencia se reinicia (no acumula ruido).

Esto es la "memoria" que pediste, antes de meter ML (Capa 3): el estado de
que eventos ya pasaron y hace cuantas velas.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ict_backtest._util import row_at_time as _row_at_time


PHASE = ("IDLE", "SWEEP_DONE", "DISPLACE_DONE", "BOS_DONE")


@dataclass
class SequenceConfig:
    sweep_lookback: int = 8        # el sweep debe verse en las ultimas N velas
    displace_gap: int = 6          # ventana para el displacement tras el sweep
    bos_gap: int = 40          # ventana para el BOS/retorno tras el displacement
                            # (40 velas M15 ~ 10h: cubre la sesion/killzone)
    require_displacement: bool = True
    counter_trend: bool = False
    tp_mode: str = "fixed2r"


@dataclass
class SequenceState:
    """Memoria de la secuencia en curso para UN simbolo/direccion."""
    phase: str = "IDLE"
    direction: int = 0
    sweep_idx: int = -1
    displace_idx: int = -1
    bos_idx: int = -1
    bos_level: float = float("nan")
    zone_high: float = float("nan")
    zone_low: float = float("nan")
    history: list = field(default_factory=list)

    def reset(self):
        self.phase = "IDLE"
        self.direction = 0
        self.sweep_idx = -1
        self.displace_idx = -1
        self.bos_idx = -1
        self.bos_level = float("nan")
        self.zone_high = float("nan")
        self.zone_low = float("nan")

    def note(self, tag: str, i: int, extra: str = ""):
        self.history.append((tag, i, extra))


def _has_sweep(row_ltf: pd.Series, est_htf: dict, direction: int) -> bool:
    """Sweep de la liquidez OPUESTA a la direccion del setup (stop-hunt).

    Long busca sweep DOWN (barre SSL); Short busca sweep UP (barre BSL).
    Se acepta en LTF o HTF.
    """
    if direction == 1:
        return bool(row_ltf.get("liquidity_sweep_down", False)) or bool(est_htf.get("sweep_down", False))
    if direction == -1:
        return bool(row_ltf.get("liquidity_sweep_up", False)) or bool(est_htf.get("sweep_up", False))
    return False


def _has_displacement(row_ltf: pd.Series, direction: int, est_htf: dict | None = None) -> bool:
    """Displacement de impulso fuerte en la direccion del setup.

    Igual que el sweep, se acepta en LTF O HTF (la vela del sweep puede ser
    HTF). Antes solo miraba la vela LTF exacta, lo que silenciaba setups de
    ruptura rapida (Silver Bullet) donde la entrada M5 es pequena sobre el FVG.
    Ver AUDIT_BUG_SILVER_TF.md (hallazgo IA externa: asimetria de diseno).
    """
    if direction == 1:
        if bool(row_ltf.get("displacement_bullish", False)):
            return True
        return bool((est_htf or {}).get("displacement_bullish", False))
    if direction == -1:
        if bool(row_ltf.get("displacement_bearish", False)):
            return True
        return bool((est_htf or {}).get("displacement_bearish", False))
    return False


def _has_choch(row_ltf: pd.Series, est_htf: dict, direction: int, counter_trend: bool) -> bool:
    """CHOCH en la direccion del giro (aviso de cambio de caracter, libro 02 §3.1).

    En contratendencia el CHOCH debe ir OPUESTO al HTF (es el paso 2 de la
    secuencia canonica BOS->CHOCH->BOS). En a-favor no se exige (el BOS de
    continuacion basta).
    """
    choch_dir = int(row_ltf.get("choch_dir", 0) or 0)
    htf_trend = str(est_htf.get("trend", "RANGING"))
    if counter_trend:
        want = -1 if htf_trend == "BULLISH" else 1 if htf_trend == "BEARISH" else direction
    else:
        return False  # a-favor: el CHOCH no es requisito (ver _has_bos)
    return choch_dir == want


def _has_bos(row_ltf: pd.Series, est_htf: dict, direction: int, counter_trend: bool) -> bool:
    """BOS/CHOCH en la direccion del setup.

    A-favor (counter_trend=False): el BOS del LTF debe ir en la direccion del
    sesgo HTF. Contratendencia: el BOS/CHOCH debe ir en direccion OPUESTA al HTF.
    """
    bos_dir = int(row_ltf.get("bos_dir", 0) or 0)
    choch_dir = int(row_ltf.get("choch_dir", 0) or 0)
    htf_trend = str(est_htf.get("trend", "RANGING"))
    if counter_trend:
        want = -1 if htf_trend == "BULLISH" else 1 if htf_trend == "BEARISH" else direction
    else:
        want = direction
    return (bos_dir == want) or (choch_dir == want)


def _htf_has_poi(est_htf: dict, target: int) -> bool:
    """¿El HTF tiene un POI (FVG/OB) en la direccion del setup?

    Ontologia (MARKET_OBJECT_MODEL.md): el POI institucional SOLO existe en
    HTF (D1/H4/H1). La zona de entrada del LTF (FVG/OB) solo cuenta si
    hay un POI de HTF que la respalde. Sin esto, un FVG M15 suelto se
    usa como entrada (error conceptual que la tesis 18 corrige).

    `est_htf` puede traer las columnas de detectores del HTF; si no las trae,
    se asume que NO hay POI (comportamiento conservador).
    """
    if target == 1:
        return bool(est_htf.get("fvg_bullish", False)) or bool(est_htf.get("ob_bullish", False))
    if target == -1:
        return bool(est_htf.get("fvg_bearish", False)) or bool(est_htf.get("ob_bearish", False))
    return False


def _latest_fvg_zone(row_ltf: pd.Series, direction: int) -> tuple[float, float] | None:
    """Cuadro del FVG mas reciente en la direccion del setup.

    Devuelve (zone_high, zone_low) del FVG. El trader traza ESTE cuadro y
    espera el retorno (mitigation). Si no hay FVG, None.
    """
    if direction == 1 and bool(row_ltf.get("fvg_bullish", False)):
        return (float(row_ltf.get("high")), float(row_ltf.get("low")))
    if direction == -1 and bool(row_ltf.get("fvg_bearish", False)):
        return (float(row_ltf.get("high")), float(row_ltf.get("low")))
    return None


def _latest_ob_zone(row_ltf: pd.Series, direction: int) -> tuple[float, float] | None:
    """Cuerpo del order block (vela de displacement previa) como cuadro.

    La columna del dataframe es 'ob_direction' (values 'bullish'/'bearish'),
    NO 'ob_dir'. Se corrige el nombre y el case para que el OB se use de
    verdad como zona de entrada.
    """
    ob_dir = str(row_ltf.get("ob_direction", "-")).lower()
    if direction == 1 and ob_dir == "bullish":
        o, c = float(row_ltf.get("open")), float(row_ltf.get("close"))
        return (max(o, c), min(o, c))
    if direction == -1 and ob_dir == "bearish":
        o, c = float(row_ltf.get("open")), float(row_ltf.get("close"))
        return (max(o, c), min(o, c))
    return None


def _touches_zone(row_ltf: pd.Series, zone_high: float, zone_low: float) -> bool:
    """La vela toca/retorna al cuadro (mitigation). Confirma entrada."""
    low, high = float(row_ltf.get("low")), float(row_ltf.get("high"))
    return (low <= zone_high) and (high >= zone_low) and (zone_low < zone_high)


def _direction_from_bias(bias: str, counter_trend: bool) -> int:
    if bias == "BULLISH":
        return -1 if counter_trend else 1
    if bias == "BEARISH":
        return 1 if counter_trend else -1
    return 0


def run_sequence(ltf_df: pd.DataFrame, est_htf_fn, cfg: SequenceConfig, htf_poi_fn=None):
    """Recorre el LTF vela a vela y devuelve lista de dicts de senal.

    est_htf_fn(i) -> dict con trend/sweep_up/sweep_down del HTF en la vela i.
    htf_poi_fn(i, target) -> bool OPCIONAL: si se pasa, la zona de entrada del
        LTF (FVG/OB) SOLO se memoriza cuando el HTF tiene un POI en esa
        direccion (fidelidad ICT, tesis 18). Si es None (default), el
        comportamiento es el historico (no rompe llamadores existentes).
    Cada senal: {time, direction, entry, phase_log}.
    """
    state = SequenceState()
    signals: list[dict] = []
    n = len(ltf_df)
    phase_seen = {"SWEEP": 0, "DISPLACE": 0, "BOS": 0, "ENTRY": 0}

    for i in range(n):
        row = ltf_df.iloc[i]
        est_htf = est_htf_fn(i)
        htf_trend = str(est_htf.get("trend", "RANGING"))
        bias = htf_trend if htf_trend in ("BULLISH", "BEARISH") else "RANGING"
        if bias == "RANGING":
            state.reset()
            continue

        # Direccion objetivo segun sesgo (a-favor o contratendencia)
        target = _direction_from_bias(bias, cfg.counter_trend)
        if target == 0:
            state.reset()
            continue

        # Si la secuencia en curso es de distinta direccion, reinicia
        if state.phase != "IDLE" and state.direction != target:
            state.reset()

        # Memoria de zona: recordar la ULTIMA vela con FVG/OB entre el sweep y
        # el BOS (el FVG/OB NO esta en la vela del BOS). Se congela en BOS_DONE
        # para que el cuadro no se mueva mientras se espera el retorno.
        if state.phase in ("SWEEP_DONE", "DISPLACE_DONE"):
            # Fidelidad ICT (tesis 18): la zona LTF (FVG/OB) solo se traza como
            # cuadro de entrada si el HTF tiene un POI en esa direccion. Sin
            # guarda (htf_poi_fn=None) el comportamiento es el historico.
            poi_ok = (htf_poi_fn is None) or bool(htf_poi_fn(i, target))
            if poi_ok:
                _fvg = _latest_fvg_zone(row, target)
                _ob = _latest_ob_zone(row, target)
                if _fvg is not None:
                    state.zone_high, state.zone_low = _fvg
                elif _ob is not None:
                    state.zone_high, state.zone_low = _ob

        if state.phase == "IDLE":
            if _has_sweep(row, est_htf, target):
                state.phase = "SWEEP_DONE"
                state.direction = target
                state.sweep_idx = i
                state.note("SWEEP", i)
                phase_seen["SWEEP"] += 1
        elif state.phase == "SWEEP_DONE":
            if i - state.sweep_idx > cfg.displace_gap:
                state.reset()
                continue
            if (not cfg.require_displacement) or _has_displacement(row, target, est_htf):
                state.phase = "DISPLACE_DONE"
                state.displace_idx = i
                state.note("DISPLACE", i)
                phase_seen["DISPLACE"] += 1
        elif state.phase == "DISPLACE_DONE":
            if i - state.displace_idx > cfg.bos_gap:
                state.reset()
                continue
            if _has_bos(row, est_htf, target, cfg.counter_trend):
                # Secuencia canonica BOS->CHOCH->BOS (libro 02 §3.1): en
                # contratendencia exigir CHOCH (giro) ANTES del BOS de confirmacion.
                if cfg.counter_trend and not _has_choch(row, est_htf, target, cfg.counter_trend):
                    continue
                state.phase = "BOS_DONE"
                state.bos_idx = i
                try:
                    state.bos_level = float(row.get("bos_level", np.nan))
                except (TypeError, ValueError):
                    state.bos_level = float("nan")
                # TRAZAR EL CUADRO: usar la zona cacheada (FVG/OB del tramo
                # sweep->displacement, memoria arriba), NO la vela del BOS donde
                # el imbalance ya no esta. El trader marca ese cuadro y ESPERA
                # el retorno (mitigation). Fallback: nivel del BOS +- 0.5 ATR.
                if not (np.isfinite(state.zone_high) and np.isfinite(state.zone_low)):
                    atr = float(row.get("atr", np.nan))
                    if np.isfinite(atr) and np.isfinite(state.bos_level):
                        state.zone_high = state.bos_level + 0.5 * atr
                        state.zone_low = state.bos_level - 0.5 * atr
                state.note("BOS", i)
                phase_seen["BOS"] += 1
        elif state.phase == "BOS_DONE":
            if i - state.bos_idx > cfg.bos_gap:
                state.reset()
                continue
            # ENTRADA = el precio RETORNA al cuadro trazado (mitigation), no FVG instantaneo.
            if _touches_zone(row, state.zone_high, state.zone_low):
                # SENAL: la secuencia completa ocurrio en orden y el precio
                # volvio al cuadro (igual que el trader que espera el toque).
                signals.append({
                    "time": str(row["time"]),
                    "direction": target,
                    "entry": float(row["close"]),
                    "bos_level": state.bos_level,
                    "sweep_at": state.sweep_idx,
                    "displace_at": state.displace_idx,
                    "bos_at": state.bos_idx,
                    "entry_at": i,
                })
                state.note("ENTRY", i)
                phase_seen["ENTRY"] += 1
                state.reset()  # una secuencia por senal
    return signals, phase_seen


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from ict_backtest.data_feed import load_frames
    from ict_backtest.market_structure import detect_market_structure

    fr = load_frames("XAUUSD", ("D1", "H4"))
    h4 = detect_market_structure(fr["H4"])
    d1 = detect_market_structure(fr["D1"])

    def est_htf_fn(i):
        t = h4.iloc[i]["time"]
        d1row = _row_at_time(d1, t)
        return {"trend": str(d1row.get("trend", "RANGING")),
                "sweep_up": bool(d1row.get("liquidity_sweep_up", False)),
                "sweep_down": bool(d1row.get("liquidity_sweep_down", False))}

    sigs, phases = run_sequence(h4, est_htf_fn, SequenceConfig())
    print(f"Senales secuencia (D1->H4): {len(sigs)}")
    print(f"Fases alcanzadas: {phases}")
    if sigs:
        print("primera:", sigs[0])
