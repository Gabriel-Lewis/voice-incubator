"""Labels on calls (voice_incubator/labels.py, voice_incubator/calls.py)."""

from __future__ import annotations

import json

import pytest

from voice_incubator import labels
from voice_incubator.calls import CallLog
from voice_incubator.protocol import BYTE_RATE

def finished(log, outcome, *stages, seconds=4.0, detection=1.5):
    record = log.begin("call", {"id": "kitchen-vpe"})
    record.marks["detection"] = detection
    for stage in stages:
        record.stage(stage["stage"], **{k: v for k, v in stage.items() if k != "stage"})
    log.finish(record, outcome, "", {"call": b"\1\0" * int(seconds * BYTE_RATE / 2), "command": b"\1\0" * 160})
    return record


def test_labels_are_saved(tmp_path):
    log = CallLog(tmp_path, {"keep_wake_audio": True, "max_saved_calls": 100})
    false_wake = finished(log, "wake rejected", {"stage": "wake_kaldi", "accepted": False, "rejected_by": "confusable"})
    assert log.set_label(false_wake.id, labels.FALSE_WAKE).label["by"] == "user"
    assert json.loads((tmp_path / false_wake.id / "trace.json").read_text())["label"]["label"] == labels.FALSE_WAKE

    with pytest.raises(ValueError):
        log.set_label(false_wake.id, "maybe")
    assert log.set_label("no-such-call", labels.GOOD) is None

    # Taken off again: as before it was labelled.
    assert log.set_label(false_wake.id, None).label is None
    assert json.loads((tmp_path / false_wake.id / "trace.json").read_text())["label"] is None
