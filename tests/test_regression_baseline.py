import json
import os

HERE = os.path.dirname(__file__)
BASELINE = os.path.join(HERE, "baseline_aged.json")


def _load_eur():
    with open(BASELINE) as f:
        data = json.load(f)
    return data["symbols"]["EURUSD"]


def test_euruidus_baseline_regression():
    """Fija el numero REAL ya medido en Fase 0 como contrato de comparacion.

    No re-corre el backtest (OOM host). Solo afirma que el baseline esta
    documentado y coincide con lo medido via run_sequence_backtest EURUSD
    H4->M15 (diag del host, 28 trades, PF 1.424, 76 senales).
    """
    eur = _load_eur()
    expected = {
        "trades": 28,
        "profit_factor": 1.424,
        "win_rate": 50.0,
        "n_senales": 76,
    }
    for k, v in expected.items():
        assert abs(eur.get(k, 0) - v) < 0.01, f"{k}: {eur.get(k)} != {v}"

    exits = eur["exit_reasons"]
    assert exits["SL"] == 17
    assert exits["hold_limit"] == 9
    assert exits["TP"] == 2
