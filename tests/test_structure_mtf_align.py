"""Tests fase 4 — alineacion temporal HTF/ITF/LTF de onsets BOS/CHOCH."""

from __future__ import annotations

import pandas as pd

from ict_backtest.structure_mtf_align import (
    AlignConfig,
    StructureOnset,
    classify_ltf_onsets,
    classify_onset_tf_level,
    extract_onsets,
    summarize_by_tf_level,
)


def _ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


def test_extract_onsets_from_structure_label():
    df = pd.DataFrame(
        {
            "time": pd.to_datetime(
                ["2024-01-01 10:00", "2024-01-01 10:05", "2024-01-01 10:10"], utc=True
            ),
            "bos_dir": [1, 0, 0],
            "choch_dir": [0, 0, -1],
            "bos_level": [1.10, float("nan"), float("nan")],
            "choch_level": [float("nan"), float("nan"), 1.09],
            "structure_label": ["BOS", "", "CHOCH"],
        }
    )
    onsets = extract_onsets(df, "M5")
    assert len(onsets) == 2
    assert onsets[0].event == "BOS" and onsets[0].direction == 1
    assert onsets[1].event == "CHOCH" and onsets[1].direction == -1


def test_match_htf_same_event_direction_within_tol():
    ltf = StructureOnset(
        time=_ts("2024-03-12 14:35:00"),
        event="CHOCH",
        direction=-1,
        level=1.085,
        tf="M5",
    )
    h4 = [
        StructureOnset(
            time=_ts("2024-03-12 12:00:00"),
            event="CHOCH",
            direction=-1,
            level=1.086,
            tf="H4",
        )
    ]
    by_tf = {"H4": h4, "D1": [], "H1": []}
    assert classify_onset_tf_level(ltf, by_tf) == "HTF"


def test_match_itf_when_only_h1():
    ltf = StructureOnset(
        time=_ts("2024-03-12 14:35:00"),
        event="BOS",
        direction=1,
        level=1.10,
        tf="M5",
    )
    h1 = [
        StructureOnset(
            time=_ts("2024-03-12 14:00:00"),
            event="BOS",
            direction=1,
            level=1.101,
            tf="H1",
        )
    ]
    by_tf = {"H4": [], "D1": [], "H1": h1}
    assert classify_onset_tf_level(ltf, by_tf) == "ITF"


def test_ltf_when_no_higher_match():
    ltf = StructureOnset(
        time=_ts("2024-03-12 16:10:00"),
        event="CHOCH",
        direction=1,
        level=1.092,
        tf="M5",
    )
    by_tf = {"H4": [], "D1": [], "H1": []}
    assert classify_onset_tf_level(ltf, by_tf) == "LTF"


def test_no_match_different_direction():
    ltf = StructureOnset(
        time=_ts("2024-03-12 14:35:00"),
        event="CHOCH",
        direction=-1,
        level=1.085,
        tf="M5",
    )
    h4 = [
        StructureOnset(
            time=_ts("2024-03-12 12:00:00"),
            event="CHOCH",
            direction=1,  # opuesta
            level=1.086,
            tf="H4",
        )
    ]
    by_tf = {"H4": h4, "D1": [], "H1": []}
    assert classify_onset_tf_level(ltf, by_tf) == "LTF"


def test_no_match_outside_tolerance():
    ltf = StructureOnset(
        time=_ts("2024-03-12 14:35:00"),
        event="BOS",
        direction=1,
        level=1.10,
        tf="M5",
    )
    # H4 onset 2 dias antes — fuera de ±4h
    h4 = [
        StructureOnset(
            time=_ts("2024-03-10 12:00:00"),
            event="BOS",
            direction=1,
            level=1.10,
            tf="H4",
        )
    ]
    by_tf = {"H4": h4, "D1": [], "H1": []}
    assert classify_onset_tf_level(ltf, by_tf) == "LTF"


def test_partition_summary_exhaustive():
    events = [
        {"event": "BOS", "tf_level": "HTF"},
        {"event": "BOS", "tf_level": "LTF"},
        {"event": "BOS", "tf_level": "LTF"},
        {"event": "CHOCH", "tf_level": "ITF"},
        {"event": "CHOCH", "tf_level": "LTF"},
    ]
    s = summarize_by_tf_level(events)
    assert s["partition_ok"] is True
    assert s["bos"]["total"] == 3
    assert s["bos"]["by_tf"]["HTF"] == 1
    assert s["bos"]["by_tf"]["LTF"] == 2
    assert s["choch"]["total"] == 2
    assert s["choch"]["by_tf"]["ITF"] == 1
    assert s["choch"]["by_tf"]["LTF"] == 1


def test_classify_batch_mixed():
    ltf_onsets = [
        StructureOnset(_ts("2024-03-12 14:35:00"), "CHOCH", -1, 1.085, "M5"),
        StructureOnset(_ts("2024-03-12 16:10:00"), "CHOCH", 1, 1.092, "M5"),
        StructureOnset(_ts("2024-03-12 11:05:00"), "BOS", 1, 1.10, "M5"),
    ]
    by_tf = {
        "H4": [
            StructureOnset(_ts("2024-03-12 12:00:00"), "CHOCH", -1, 1.086, "H4"),
        ],
        "D1": [],
        "H1": [
            StructureOnset(_ts("2024-03-12 11:00:00"), "BOS", 1, 1.101, "H1"),
        ],
    }
    rows = classify_ltf_onsets(ltf_onsets, by_tf, AlignConfig())
    levels = {r["time"]: r["tf_level"] for r in rows}
    assert levels["2024-03-12T14:35:00+00:00"] == "HTF"
    assert levels["2024-03-12T16:10:00+00:00"] == "LTF"
    assert levels["2024-03-12T11:05:00+00:00"] == "ITF"
