"""Verificacion del nuevo comportamiento del semaforo (R:R >= 1:2 para VERDE).

Este test cubre el cambio de semaforo_fundednext.evaluate(): ya no dice VERDE
solo por "estructura clara y sin roja"; exige un setup valido (R:R >= 1:2).
Si el contexto esta limpio pero el R:R no llega -> AMARILLO "esperar".
"""
import sys
import types
from pathlib import Path
sys.path.insert(0, '.')
sys.path.insert(0, str(Path('.').resolve() / 'scripts'))

# rutina_eurusd imports BosConfig/detect_bos from detectors which were
# removed in the R7 unification (now in ict_backtest/market_structure.py).
# evaluate() never uses those — mock the transitive imports so the test
# stays isolated from the broken production import chain.
for mod_name in ("rutina_eurusd", "news_report"):
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

from scripts.semaforo_fundednext import evaluate


def test_verde_requiere_setup_valido():
    # Sesgo claro, sin roja, R:R >= 1:2 -> VERDE
    color, reasons = evaluate(
        "SHORT", [], {"valido": True, "rr": 2.3})
    assert color == "VERDE"
    assert any("R:R" in r for r in reasons)


def test_amarillo_si_rr_insuficiente():
    # Sesgo claro, sin roja, PERO R:R < 1:2 -> AMARILLO (no miente con VERDE)
    color, reasons = evaluate(
        "SHORT", [], {"valido": False, "rr": 0.42})
    assert color == "AMARILLO"
    assert any("R:R" in r for r in reasons)
    assert any("esperar" in r.lower() for r in reasons)


def test_amarillo_con_noticia_roja():
    red = [{"currency": "USD", "event": "CPI", "time_utc": "12:30"}]
    color, _ = evaluate("LONG", red, {"valido": True, "rr": 2.5})
    assert color == "AMARILLO"


def test_rojo_neutral_con_roja():
    red = [{"currency": "USD", "event": "CPI", "time_utc": "12:30"}]
    color, _ = evaluate("NEUTRAL (esperar)", red)
    assert color == "ROJO"


def test_amarillo_neutral_sin_roja():
    color, _ = evaluate("NEUTRAL (esperar)", [])
    assert color == "AMARILLO"


if __name__ == "__main__":
    test_verde_requiere_setup_valido()
    test_amarillo_si_rr_insuficiente()
    test_amarillo_con_noticia_roja()
    test_rojo_neutral_con_roja()
    test_amarillo_neutral_sin_roja()
    print("ALL SEMAFORO TESTS PASSED")
