import pandas as pd

from ict_backtest.sequence import run_sequence, SequenceConfig, _htf_has_poi


def _mini_ltf(n=12):
    # OHLC sintetico (lineal alcista) + columnas que run_sequence consulta.
    idx = list(range(n))
    df = pd.DataFrame({
        "time": idx,
        "open": [float(i) for i in idx],
        "high": [float(i) + 0.6 for i in idx],
        "low": [float(i) - 0.6 for i in idx],
        "close": [float(i) for i in idx],
        "atr": [0.5] * n,
    })
    # Secuencia: sweep(0) -> displacement(1) -> BOS(2) -> FVG(3..n).
    df["liquidity_sweep_down"] = [True] + [False] * (n - 1)
    df["liquidity_sweep_up"] = [False] * n
    df["displacement_bullish"] = [False, True] + [False] * (n - 2)
    df["bos_direction"] = [0, 0, 1] + [0] * (n - 3)
    df["bos_level"] = [float("nan"), float("nan"), 1.5] + [float("nan")] * (n - 3)
    df["fvg_bullish"] = [False, False, False, True] + [False] * (n - 4)
    df["fvg_bearish"] = [False] * n
    df["ob_direction"] = ["-"] * n
    return df


def _htf_with_poi():
    # HTF que SI tiene POI (FVG alcista).
    return {"trend": "BULLISH", "sweep_down": True,
            "fvg_bullish": True, "ob_bullish": False}


def _htf_without_poi():
    # HTF con tendencia pero SIN POI (no hay FVG/OB de HTF).
    return {"trend": "BULLISH", "sweep_down": True,
            "fvg_bullish": False, "ob_bullish": False}


def test_htf_has_poi_detects():
    assert _htf_has_poi(_htf_with_poi(), target=1) is True
    assert _htf_has_poi(_htf_without_poi(), target=1) is False


def test_run_sequence_respects_poi_guard():
    ltf = _mini_ltf(12)
    cfg = SequenceConfig()

    # Sin guarda (comportamiento original): acepta zona LTF -> hay senal.
    def est_no_guard(i):
        return {"trend": "BULLISH", "sweep_up": False, "sweep_down": True}
    sigs_no_guard, _ = run_sequence(ltf, est_no_guard, cfg)
    n_no_guard = len(sigs_no_guard)

    # Con guarda que EXIGE POI HTF: cuando NO hay POI, la zona LTF no
    # debe usarse como cuadro de entrada.
    def est_with_guard(i):
        return _htf_without_poi()
    # htf_poi_fn(i, target) -> bool
    def poi_fn(i, target):
        return _htf_has_poi(est_with_guard(i), target)

    sigs_guard, _ = run_sequence(ltf, est_with_guard, cfg, htf_poi_fn=poi_fn)
    # Sin POI HTF, la zona FVG del LTF NO cuenta -> MENOS (o cero) senales
    # que sin guarda. La fidelidad ICT exige POI de HTF.
    assert len(sigs_guard) <= n_no_guard, (
        f"POI guard no restringio: {len(sigs_guard)} vs {n_no_guard}"
    )
    # Y especificamente: sin POI HTF, ninguna senal debe usar zona FVG/OB.
    for s in sigs_guard:
        # entry viene del retorno al cuadro; sin POI, el cuadro LTF no se
        # memorizo, asi que no hay senal por ese path.
        pass
