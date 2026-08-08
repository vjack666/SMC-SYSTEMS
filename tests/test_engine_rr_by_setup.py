"""Tests engine.rr_by_setup — RR por setup (geometria, sin indicadores)."""
from engine.rr_by_setup import rr_for, flag_rr


class _Sig:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def test_rr_for_known():
    assert rr_for("silver_bullet") == 2.0
    assert rr_for("turtle_soup") == 1.5
    assert rr_for("ote") == 3.0
    assert rr_for(None) == 3.0
    assert rr_for("po3") == 3.0


def test_flag_rr_precedence():
    sigs = [_Sig(sb_confirmed=True), _Sig(turtle_confirmed=True), _Sig(ote_confirmed=True), _Sig()]
    out = flag_rr(sigs)
    assert out[0].rr_target == 2.0   # SB > Turtle
    assert out[1].rr_target == 1.5   # Turtle
    assert out[2].rr_target == 3.0   # OTE
    assert out[3].rr_target == 3.0   # default
