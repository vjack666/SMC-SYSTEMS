"""RED — dealing_range: clasifica zona premium/discount/EQ (Brecha C).

Tesis (libro 21 §0/§2, libro 08 PO3): un POI valido exige estar en la ZONA
CORRECTA del dealing range (discount para long, premium para short; EQ =
ambiguo, 10-15% central). Hoy el codigo NO filtra zona. dealing_range marca
(bonus, no borra). Test FALLA hasta implementar ict_backtest/dealing_range.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))


def test_zona_discount_para_long_es_ok():
    from ict_backtest.dealing_range import classify_zone, zone_ok_for_direction

    # swing 1.1000-1.1100; EQ=1.1050; zona 1.1020-1.1030 esta en discount
    cls = classify_zone(1.1030, 1.1020, 1.1100, 1.1000)
    assert cls == "DISCOUNT"
    assert zone_ok_for_direction(cls, 1) is True   # long quiere discount
    assert zone_ok_for_direction(cls, -1) is False  # short quiere premium


def test_zona_premium_para_short_es_ok():
    from ict_backtest.dealing_range import classify_zone, zone_ok_for_direction

    # zona 1.1070-1.1080 esta en premium
    cls = classify_zone(1.1080, 1.1070, 1.1100, 1.1000)
    assert cls == "PREMIUM"
    assert zone_ok_for_direction(cls, -1) is True
    assert zone_ok_for_direction(cls, 1) is False


def test_zona_en_eq_es_ambigua():
    from ict_backtest.dealing_range import classify_zone, zone_ok_for_direction

    # EQ = 1.1050; zona pegada al centro es EQ (ambiguo)
    cls = classify_zone(1.1052, 1.1048, 1.1100, 1.1000)
    assert cls == "EQ"
    # EQ no descarta (no es ok ni wrong-side): la dejamos como ambiguo=False
    # (no cuenta como bonificada, pero no mata la senal)
    assert zone_ok_for_direction(cls, 1) is False
    assert zone_ok_for_direction(cls, -1) is False
