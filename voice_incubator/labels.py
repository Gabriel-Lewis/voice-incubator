"""Review labels on calls: was it really the wake word?

Every call from a satellite can carry a label -- ``good`` (the wake word was
said), ``false_wake`` (it wasn't) or ``discard`` (neither, or can't tell) --
set by a person on the Sessions page.
"""

from __future__ import annotations

import time
from typing import Any

GOOD = "good"
FALSE_WAKE = "false_wake"
DISCARD = "discard"
LABELS = (GOOD, FALSE_WAKE, DISCARD)


def label_entry(label: str, by: str = "user") -> dict[str, Any]:
    """A label as a call keeps it: which, who set it, and when."""
    if label not in LABELS:
        raise ValueError(f"label: expected one of {', '.join(LABELS)}")
    return {"label": label, "by": by, "at": round(time.time(), 3)}
