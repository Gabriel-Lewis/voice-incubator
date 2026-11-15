"""The Sessions list (voice_incubator/calls.py)."""

from __future__ import annotations

import json

import pytest

from voice_incubator.calls import CallLog
from voice_incubator.protocol import BYTE_RATE


def test_clearing_sessions(tmp_path):
    log = CallLog(tmp_path, {"keep_audio": True, "max_saved_calls": 100})
    kitchen, office = {"id": "kitchen-vpe"}, {"id": "office-vpe"}
    for satellite in (kitchen, office, kitchen):
        log.finish(log.begin("call", satellite), "done", "turned on the lights", {"call": b"\0\0" * 160})
    going = log.begin("call", kitchen)  # still being said
    # Saved long ago: no longer among the recent, but on disk.
    old = tmp_path / "20200101-000000-0001-office"
    old.mkdir()
    (old / "trace.json").write_text(json.dumps({"satellite": office}))

    # A satellite's: only its own, saved ones too.
    assert log.clear("office-vpe") == 2
    assert not old.exists()
    assert [c["satellite"]["id"] for c in log.list()] == ["kitchen-vpe"] * 3

    # Everyone's, but not the one still going: it finishes, and is saved.
    assert log.clear() == 2
    assert [c["id"] for c in log.list()] == [going.id]
    assert [p.name for p in tmp_path.iterdir()] == []
    log.finish(going, "done", "", {"call": b"\0\0" * 160})
    assert (tmp_path / going.id / "trace.json").is_file()


def finished(log, outcome, *stages, seconds=4.0, detection=1.5):
    record = log.begin("call", {"id": "kitchen-vpe"})
    record.marks["detection"] = detection
    for stage in stages:
        record.stage(stage["stage"], **{k: v for k, v in stage.items() if k != "stage"})
    log.finish(record, outcome, "", {"call": b"\1\0" * int(seconds * BYTE_RATE / 2), "command": b"\1\0" * 160})
    return record


def test_only_the_wake_word_is_kept(tmp_path):
    log = CallLog(tmp_path, {"keep_audio": False, "keep_wake_audio": True, "max_saved_calls": 100})
    record = finished(log, "wake rejected", {"stage": "wake_kaldi", "accepted": False, "rejected_by": "confusable"})
    assert record.kept and record.audio == {"wake": "wake.wav"}
    path = log.audio_path(record.id, "wake")
    # The pre-roll and a second after it: 2.5 s of 16 kHz, 16-bit, plus the header.
    assert path.stat().st_size == pytest.approx(2.5 * BYTE_RATE, abs=100)

    # Off: nothing saved, as before.
    log = CallLog(tmp_path / "off", {"keep_audio": False, "max_saved_calls": 100})
    assert not finished(log, "done").kept
