"""Review labels on calls: was it really the wake word?

Every call from a satellite can carry a label -- ``good`` (the wake word was
said), ``false_wake`` (it wasn't) or ``discard`` (neither, or can't tell) --
set by a person on the Sessions page, or suggested from what the call itself
shows. A suggestion is only that until someone confirms it, and
is ``sure`` when the call leaves little doubt: Kaldi refusing a confusable,
or a wake word Kaldi accepted outright followed by a command that ran.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .commands import NEVER_MIND

GOOD = "good"
FALSE_WAKE = "false_wake"
DISCARD = "discard"
LABELS = (GOOD, FALSE_WAKE, DISCARD)


def _clear_accept(kaldi: dict[str, Any] | None) -> bool:
    """Kaldi accepted it with room to spare: both halves of the phrase scored
    better than the background (its thresholds let them fall below it) and
    no confusable came close (wyoming_wake_kaldi/verify.py)."""
    if not kaldi or not kaldi.get("accepted"):
        return False
    prefix, last, margin = kaldi.get("lr_prefix"), kaldi.get("lr_last"), kaldi.get("confusable_margin")
    numbers = all(isinstance(v, (int, float)) for v in (prefix, last))
    return numbers and prefix >= 0 and last >= 0 and not margin


@dataclass(frozen=True)
class Suggestion:
    label: str
    reason: str
    sure: bool

    def to_json(self) -> dict[str, Any]:
        return {"label": self.label, "reason": self.reason, "sure": self.sure}


def _last(stages: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for stage in reversed(stages):
        if stage.get("stage") == name:
            return stage
    return None


def suggest(kind: str, outcome: str, stages: list[dict[str, Any]]) -> Suggestion | None:
    """What a call's stages say about its wake word, or None when they say
    nothing (typed, a follow-up with no wake word, still going, or a wake word
    another satellite answered)."""
    if kind != "call" or outcome == "in progress":
        return None
    names = {s.get("stage") for s in stages}
    if "follow_up" in names or "answered_elsewhere" in names or "wake_refused_elsewhere" in names:
        return None

    kaldi = _last(stages, "wake_kaldi")
    ratio = _last(stages, "wake_ratio")
    if outcome == "wake rejected":
        rejected_by = (kaldi or {}).get("rejected_by") or (ratio or {}).get("rejected_by")
        if rejected_by == "confusable":
            return Suggestion(FALSE_WAKE, "Kaldi heard a confusable", True)
        if ratio is not None and ratio.get("kept_by") == "rival":
            return Suggestion(FALSE_WAKE, f"sounds like {ratio.get('rival')!r}", True)
        # prefix/last: often a real wake word said far away, or by a child.
        return Suggestion(FALSE_WAKE, f"Kaldi refused it ({rejected_by or 'unknown'})", False)

    timeout = _last(stages, "timeout")
    if outcome == "timeout" and timeout is not None and "no speech" in str(timeout.get("why")):
        return Suggestion(FALSE_WAKE, "nothing was said after it", False)

    recognition = _last(stages, "recognition") or {}
    command = recognition.get("command")
    if command == NEVER_MIND:
        return Suggestion(FALSE_WAKE, "“never mind” right after it", False)
    if outcome in ("not recognized", "error", "timeout", "cancelled", "ended by device"):
        return None

    overturned = bool(ratio and ratio.get("overturned"))
    accepted = bool(kaldi and kaldi.get("accepted"))
    if not overturned and _clear_accept(kaldi):
        return Suggestion(GOOD, "Kaldi accepted it and a command followed", True)
    if accepted or overturned:
        why = "the second opinion overturned Kaldi" if overturned else "Kaldi accepted it narrowly"
        return Suggestion(GOOD, f"{why}; a command followed", False)
    if "wake_unverified" in names:
        return Suggestion(GOOD, "a command followed (wake word not verified)", False)
    return None


def label_entry(label: str, by: str = "user") -> dict[str, Any]:
    """A label as a call keeps it: which, who set it, and when."""
    if label not in LABELS:
        raise ValueError(f"label: expected one of {', '.join(LABELS)}")
    return {"label": label, "by": by, "at": round(time.time(), 3)}

