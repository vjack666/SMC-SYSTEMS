"""Tests for Observador → Position Sizer handoff (levels only)."""
from __future__ import annotations

from pathlib import Path

from app_observador.core.position_sizer_bridge import (
    extract_levels,
    levels_to_csv,
    write_ps_handoff,
    TradeLevels,
)


def _sample_result(**overrides) -> dict:
    base = {
        "bias": "SHORT",
        "veredicto": {
            "bias": "SHORT",
            "votes": {"LONG": 1, "SHORT": 3},
            "zone_note": "Zona de venta (OTE M15): 1.14633 - 1.14658",
            "invalidation": 1.14747,
            "target": 1.14603,
        },
        "estructura": {
            "M15": {
                "ote_long": [1.14692, 1.14716],
                "ote_short": [1.14633, 1.14658],
            }
        },
    }
    base.update(overrides)
    return base


def test_extract_short_levels_from_last_cycle_shape():
    levels = extract_levels(_sample_result())
    assert levels is not None
    assert levels.side == "SHORT"
    assert levels.symbol == "EURUSD"
    assert abs(levels.entry - (1.14633 + 1.14658) / 2) < 1e-9
    assert levels.sl == 1.14747
    assert levels.tp == 1.14603
    assert levels.rr > 0
    assert levels.valid_rr is False  # RR ~0.42


def test_extract_long_levels():
    result = _sample_result(
        bias="LONG",
        veredicto={
            "bias": "LONG",
            "votes": {"LONG": 3, "SHORT": 1},
            "invalidation": 1.14000,
            "target": 1.16000,
            "zone_note": "buy",
        },
        estructura={
            "M15": {
                "ote_long": [1.14500, 1.14600],
                "ote_short": [1.14000, 1.14100],
            }
        },
    )
    levels = extract_levels(result)
    assert levels is not None
    assert levels.side == "LONG"
    assert abs(levels.entry - 1.1455) < 1e-9
    assert levels.valid_rr is True


def test_extract_none_without_votes_or_ote():
    assert extract_levels(None) is None
    assert extract_levels({"veredicto": {}, "estructura": {}}) is None
    neutral = _sample_result(
        veredicto={"bias": "NEUTRAL", "votes": {"LONG": 1, "SHORT": 1},
                   "invalidation": 1.1, "target": 1.2},
    )
    # tie votes + NEUTRAL bias -> no side
    assert extract_levels(neutral) is None


def test_csv_contains_no_auto_trade_flag():
    levels = TradeLevels(
        symbol="EURUSD", side="SHORT", entry=1.1, sl=1.2, tp=1.0, rr=1.0
    )
    csv = levels_to_csv(levels, seq=42)
    assert "auto_trade,0" in csv
    assert "seq,42" in csv
    assert "entry,1.10000000" in csv


def test_write_ps_handoff_tmp(tmp_path, monkeypatch):
    levels = extract_levels(_sample_result())
    assert levels is not None

    common = tmp_path / "Common" / "Files"
    term = tmp_path / "Term" / "MQL5" / "Files"
    monkeypatch.setattr(
        "app_observador.core.position_sizer_bridge.common_files_dir",
        lambda: common,
    )
    monkeypatch.setattr(
        "app_observador.core.position_sizer_bridge.terminal_files_dir",
        lambda terminal_id="x": term,
    )

    paths = write_ps_handoff(levels, seq=99)
    assert len(paths) == 2
    for p in paths:
        text = Path(p).read_text(encoding="utf-8")
        assert "seq,99" in text
        assert "side,SHORT" in text
        assert "auto_trade,0" in text


def test_update_ps_settings_files(tmp_path, monkeypatch):
    from app_observador.core.position_sizer_bridge import update_ps_settings_files

    folder = tmp_path / "PS_Settings"
    folder.mkdir()
    sample = folder / "EURUSD123.txt"
    sample.write_text(
        "EntryType\n0\nEntryLevel\n1.10000\nStopLossLevel\n1.09000\n"
        "TakeProfitLevel\n1.12000\nRisk\n1.00\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app_observador.core.position_sizer_bridge.ps_settings_dir",
        lambda terminal_id="x": folder,
    )
    levels = extract_levels(_sample_result())
    assert levels is not None
    updated = update_ps_settings_files(levels)
    assert sample in updated
    text = sample.read_text(encoding="utf-8")
    assert "EntryType\n1\n" in text
    assert f"{levels.entry:.5f}" in text
    assert f"{levels.sl:.5f}" in text
    assert f"{levels.tp:.5f}" in text
