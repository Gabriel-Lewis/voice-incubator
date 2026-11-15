"""Labels on calls (voice_incubator/labels.py, voice_incubator/calls.py)."""

from __future__ import annotations

import json

import pytest

from voice_incubator import labels
from voice_incubator.calls import CallLog
from voice_incubator.protocol import BYTE_RATE

CLEAR = {"stage": "wake_kaldi", "accepted": True, "rejected_by": None, "lr_prefix": 0.4, "lr_last": 0.2,
         "confusable_margin": 0.0}
NARROW = {**CLEAR, "lr_last": -0.2, "confusable_margin": 0.05}


def suggested(outcome, *stages, kind="call"):
    return labels.suggest(kind, outcome, list(stages))


def test_confusable_and_rival_rejections_are_sure_false_wakes():
    s = suggested("wake rejected", {"stage": "wake_kaldi", "accepted": False, "rejected_by": "confusable"})
    assert (s.label, s.sure) == (labels.FALSE_WAKE, True)
    s = suggested("wake rejected", {"stage": "wake_kaldi", "accepted": False, "rejected_by": "last"},
                  {"stage": "wake_ratio", "rejected_by": "last", "overturned": False, "kept_by": "rival", "rival": "okay now"})
    assert (s.label, s.sure) == (labels.FALSE_WAKE, True)
    assert "okay now" in s.reason


def test_prefix_and_last_rejections_need_a_look():
    # Often a real wake word from across the room, or a child's.
    s = suggested("wake rejected", {"stage": "wake_kaldi", "accepted": False, "rejected_by": "prefix"},
                  {"stage": "wake_ratio", "rejected_by": "prefix", "overturned": False, "kept_by": "score"})
    assert (s.label, s.sure) == (labels.FALSE_WAKE, False)


def test_silence_and_never_mind_suggest_false_wakes():
    s = suggested("timeout", CLEAR, {"stage": "timeout", "why": "no speech was heard"})
    assert (s.label, s.sure) == (labels.FALSE_WAKE, False)
    s = suggested("done", CLEAR, {"stage": "recognition", "command": "satellites/never_mind"})
    assert (s.label, s.sure) == (labels.FALSE_WAKE, False)


def test_a_command_after_a_clear_accept_is_a_sure_good_wake():
    s = suggested("done", CLEAR, {"stage": "recognition", "command": "lights/turn_on"})
    assert (s.label, s.sure) == (labels.GOOD, True)
    s = suggested("done", NARROW, {"stage": "recognition", "command": "lights/turn_on"})
    assert (s.label, s.sure) == (labels.GOOD, False)
    overturned = {"stage": "wake_ratio", "overturned": True, "kept_by": None}
    s = suggested("done", {**CLEAR, "accepted": False, "rejected_by": "last"}, overturned,
                  {"stage": "recognition", "command": "lights/turn_on"})
    assert (s.label, s.sure) == (labels.GOOD, False)
    s = suggested("answered", {"stage": "wake_unverified", "wake_word": "hey_tater"})
    assert (s.label, s.sure) == (labels.GOOD, False)


def test_no_suggestion_without_a_wake_word_to_judge():
    assert suggested("done", CLEAR, kind="try") is None
    assert suggested("in progress", CLEAR) is None
    assert suggested("done", {"stage": "follow_up"}, CLEAR) is None
    assert suggested("answered elsewhere", {"stage": "answered_elsewhere"}) is None
    assert suggested("not recognized", CLEAR, {"stage": "recognition", "command": None}) is None


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
    assert log.list()[0]["suggested"]["label"] == labels.FALSE_WAKE
    assert log.set_label(false_wake.id, labels.FALSE_WAKE).label["by"] == "user"
    assert json.loads((tmp_path / false_wake.id / "trace.json").read_text())["label"]["label"] == labels.FALSE_WAKE

    with pytest.raises(ValueError):
        log.set_label(false_wake.id, "maybe")
    assert log.set_label("no-such-call", labels.GOOD) is None

    # Taken off again: as before it was labelled.
    assert log.set_label(false_wake.id, None).label is None
    assert json.loads((tmp_path / false_wake.id / "trace.json").read_text())["label"] is None
