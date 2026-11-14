"""Alarms and reminders on the calendar, in Dutch, with English's names (see
voice_incubator/languages/en/calendar.py for what each is): when one is for
-- read from what was said ("morgen om half acht", "elke werkdag om zes uur",
"over 20 minuten", "vrijdag om vijf uur 's middags") -- and what the app says
about them.

Dutch says a clock time by the hour to come: "half acht" is 7:30, "kwart voor
acht" 7:45, "tien voor half acht" 7:20 (the pack's reading.clock). "Om" is
both "at" and what starts what to do ("om mama te bellen"), and "uur" both
o'clock and hours: "om zeven uur" is a time, "over zeven uur" one from now."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from . import reading
from .skills.numbers import parse_num
from .speech import _capital, clock, duration, join, join_or

# ----------------------------------------------------------------- reading

DAYS = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
CODES = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
_DAY = rf"(?:{'|'.join(DAYS)})"
_MONTHS = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
           "november", "december"]

_NUMBER_WORDS = {
    "nul", "een", "één", "twee", "drie", "vier", "vijf", "zes", "zeven", "acht", "negen", "tien", "elf", "twaalf",
    "dertien", "veertien", "vijftien", "zestien", "zeventien", "achttien", "negentien", "twintig", "dertig",
    "veertig", "vijftig", "half", "halve", "anderhalf", "anderhalve", "kwart", "driekwart",
}
_COMPOUND = re.compile(r"(?:een|twee|drie|vier|vijf|zes|zeven|acht|negen)(?:en|ën)(?:twintig|dertig|veertig|vijftig)")
"""A number of tens and ones written as one: "vijfentwintig"."""
_PARTS_OF_DAY = ("ochtend", "middag", "avond", "nacht", "vroeg")
_WHEN_WORDS = {
    "om", "op", "voor", "over", "in", "deze", "volgende", "aanstaande", "komende", "elke", "iedere", "elk", "ieder",
    "de", "het", "en", "'s", "s", "ochtends", "morgens", "middags", "avonds", "nachts", "uur", "uren", "minuut",
    "minuten", "kwartier", "middernacht", "vandaag", "vanavond", "vannacht", "vanochtend", "vanmorgen", "vanmiddag",
    "morgen", "overmorgen", "dagelijks", "dag", "dagen", "werkdag", "werkdagen", "doordeweeks", "doordeweekse",
    "weekend", "weekenden", "week", *_PARTS_OF_DAY, *DAYS, *(d + "s" for d in DAYS), *(d + "en" for d in DAYS),
    *_NUMBER_WORDS,
}
_EDGE = {"om", "op", "voor", "over", "in", "deze", "volgende", "aanstaande", "komende", "de", "het", "en", "een"}
"""Words a time is said with, but which alone are no time -- nor, at its end,
part of it: "morgen om negen uur | om de tandarts te bellen"."""
_STARTS = {
    "om", "op", "over", "in", "deze", "volgende", "aanstaande", "komende", "elke", "iedere", "elk", "ieder", "'s",
    "vandaag", "vanavond", "vannacht", "vanochtend", "vanmorgen", "vanmiddag", "morgen", "overmorgen", "dagelijks",
    "doordeweeks", *DAYS, *(d + "s" for d in DAYS),
}
"""Words a time said at the end of a reminder may start with."""

_UNITS = {"seconde": 1, "seconden": 1, "minuut": 60, "minuten": 60, "kwartier": 900, "uur": 3600, "uren": 3600}
"""A length from now, in seconds per one."""
_CLOCK_BETWEEN = (
    [], ["uur"], ["over"], ["voor"], ["over", "half"], ["voor", "half"], ["minuut", "over"], ["minuut", "voor"],
    ["minuten", "over"], ["minuten", "voor"], ["minuten", "over", "half"], ["minuten", "voor", "half"],
)
"""What may come between two numbers of one clock time: "zeven uur dertig",
"tien over zeven", "vijf voor half acht"."""


@dataclass
class When:
    """When an alarm or a reminder is: its first time (local), how it repeats
    (an RRULE, or None), and what was said besides (a reminder's text)."""

    start: datetime
    rrule: str | None = None
    rest: str = ""
    relative: bool = False
    """Said from now ("over 20 minuten")."""
    said: str = ""
    """The words that said when."""


def _plain(word: str) -> str:
    return word.lower().strip(",.!?")


def _is_number(word: str) -> bool:
    return bool(re.fullmatch(r"\d{1,2}(?::\d{2})?|\d{3,4}", word)) or word in _NUMBER_WORDS or bool(_COMPOUND.fullmatch(word))


def _is_when_word(word: str) -> bool:
    w = _plain(word)
    return w in _WHEN_WORDS or _is_number(w) or bool(re.fullmatch(r"\d{1,2}[.:]\d{2}", w))


def _run(words: list[str], from_end: bool) -> tuple[int, int]:
    """The longest run of time words at the start or the end: (begin, end)."""
    n = len(words)
    if from_end:
        begin = n
        while begin > 0 and _is_when_word(words[begin - 1]):
            begin -= 1
        end = n
    else:
        end = 0
        while end < n and _is_when_word(words[end]):
            end += 1
        begin = 0
        # Not "om", "de" ... at its end: they belong to what was said besides.
        while end > begin and _plain(words[end - 1]) in _EDGE:
            end -= 1
    # Nor "de", "het", "en" at its start.
    while begin < end and _plain(words[begin]) in ("de", "het", "en"):
        begin += 1
    return begin, end


def _joined(text: str) -> str:
    """What speech-to-text writes one way or another: "savonds" and "s
    avonds" are "'s avonds"; "morgenochtend" and "maandagavond" a day and a
    part of it; "halfacht" and "kwartover zes" a clock time's words."""
    hours = "een|twee|drie|vier|vijf|zes|zeven|acht|negen|tien|elf|twaalf"
    text = re.sub(rf"\b(half|kwart)(?=(?:over|voor|{hours})(?:\b|[a-z]))", r"\1 ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(kwart )(over|voor)(?=[a-z])", r"\1\2 ", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<![\w'’])['’]?s[ -]?(?=(?:ochtends|morgens|middags|avonds|nachts)\b)", "'s ", text,
                  flags=re.IGNORECASE)
    return re.sub(rf"\b(morgen|{'|'.join(DAYS)})({'|'.join(_PARTS_OF_DAY)})\b", r"\1 \2", text, flags=re.IGNORECASE)


def when(text: str, now: datetime, alarm: bool = False) -> When | None:
    """When ``text`` says: a time (and a day, or how it repeats), or a time
    from now; None when it says none. ``now`` is aware local time; an
    ``alarm`` said for another day without 's ochtends or 's avonds is in the
    morning."""
    words = _joined(text).split()
    best: tuple[When, int] | None = None
    for from_end in (False, True):
        begin, end = _run(words, from_end)
        found = None
        while begin < end:
            found = _read(" ".join(words[begin:end]), now, alarm)
            if found is not None and not from_end and end < len(words) and _bare(" ".join(words[begin:end])) \
                    and _plain(words[end]) not in _AFTER_TIME:
                found = None  # "om drie pakken melk te kopen": how many, not when
                break
            if found is not None:
                break
            # Not all of it is the time ("om tien minuten te rusten om vijf
            # uur"): less of it, from where it meets the rest, to a word a
            # time starts or ends with.
            if from_end:
                begin += 1
                while begin < end and _plain(words[begin]) not in _STARTS:
                    begin += 1
            else:
                end -= 1
                while end > begin and _plain(words[end - 1]) in _EDGE:
                    end -= 1
        if found is not None and (best is None or end - begin > best[1]):
            found.rest = " ".join(words[:begin] + words[end:]).strip(" ,")
            found.said = " ".join(words[begin:end])
            best = (found, end - begin)
    if best is None:
        # A clause puts its verb last: "dat de loodgieter vrijdag om drie uur
        # komt". A clock time in the middle, said as one ("uur", "7:30",
        # "half acht"): not "om twee pakken melk te kopen".
        for begin, end in _inner_runs(words):
            said = " ".join(words[begin:end])
            found = _read(said, now, alarm) if _CLOCKISH.search(_spaced(said)) else None
            if found is not None and (best is None or end - begin > best[1]):
                found.rest = " ".join(words[:begin] + words[end:]).strip(" ,")
                found.said = said
                best = (found, end - begin)
    return best[0] if best else None


_AFTER_TIME = {"om", "aan", "eraan", "er", "dat", "over", "te", "wakker"}
"""What a reminder (or "wakker") goes on with after a time said first."""


def _bare(said: str) -> bool:
    """Whether a time is only a number: "om drie", which may be how many."""
    s = _spaced(said)
    return not (_CLOCKISH.search(s) or re.search(
        rf" (?:{'|'.join(_PARTS_OF_DAY)}|ochtends|morgens|middags|avonds|nachts|vandaag|vanavond|vannacht|vanochtend"
        rf"|vanmorgen|vanmiddag|morgen|overmorgen|dagelijks|werkdag|werkdagen|weekend|{_DAY}|{_DAY}s|minuut|minuten"
        rf"|kwartier|uren) ", s))


_CLOCKISH = re.compile(
    rf" uur | \d{{1,2}}:\d{{2}} | middernacht | (?:half|kwart over|kwart voor) (?:\d+|{'|'.join(sorted(_NUMBER_WORDS))}) "
)
"""What says a time of day whatever is around it."""


def _inner_runs(words: list[str]) -> list[tuple[int, int]]:
    """Each run of time words between others, without edge words at its ends."""
    runs, n, i = [], len(words), 0
    while i < n:
        if not _is_when_word(words[i]):
            i += 1
            continue
        begin = i
        while i < n and _is_when_word(words[i]):
            i += 1
        end = i
        while begin < end and _plain(words[begin]) in ("de", "het", "en", "een"):
            begin += 1
        while end > begin and _plain(words[end - 1]) in _EDGE:
            end -= 1
        if 0 < begin and end < n and begin < end:
            runs.append((begin, end))
    return runs


def _spaced(said: str) -> str:
    """Lowercase, spaced at its ends, "19.30" as "19:30", without
    punctuation or the "'s" of "'s avonds"."""
    s = re.sub(r"(\d{1,2})[.:](\d{2})", r"\1:\2", said.lower())
    s = re.sub(r"[,.!?]", " ", s)
    s = re.sub(r"(?<!\w)['’]s\b", " ", s)
    return " " + " ".join(s.split()) + " "


def _length(s: str) -> float | None:
    """The seconds a length from now says ("over 20 minuten", "over een uur en
    een kwartier", "anderhalf uur"), the whole of ``s``; None when it isn't
    one. A whole number of "uur" without "over" is a clock time: "zeven uur"."""
    words = s.split()
    said_over = bool(words) and words[0] in ("over", "in")
    if said_over:
        words = words[1:]
    if not words or words[-1] not in _UNITS:
        return None
    total, amount, parts, whole_hours = 0.0, [], 0, False
    for word in words:
        if word not in _UNITS:
            if word == "en" and not amount and parts:
                continue  # "een uur | en | tien minuten"
            amount.append(word)
            continue
        said = " ".join(amount)
        if not said:
            if word != "kwartier":
                return None
            number = 1.0
        else:
            number = parse_num(said)
            if not number:
                return None
        whole_hours = whole_hours or (word == "uur" and float(number).is_integer())
        total += float(number) * _UNITS[word]
        amount, parts = [], parts + 1
    if amount or not total or (whole_hours and parts == 1 and not said_over):
        return None
    return total


def _read(said: str, now: datetime, alarm: bool) -> When | None:
    """A run of time words as a When; None when it isn't one (or names a day
    but no time: see ``wants_time``)."""
    s = _spaced(said)

    # From now: "over 20 minuten", "over een uur", "over een half uur" -- or
    # a length alone: speech-to-text, or the free text's edge, can drop the
    # "over".
    seconds = _length(s)
    if seconds is not None:
        return When(now + timedelta(seconds=seconds), relative=True)
    # A length that isn't from now is no time: "om tien minuten te rusten".
    if re.search(r" (?:minuut|minuten) (?!over |voor )| (?:seconde|seconden|kwartier|uren) ", s):
        return None

    rule, days = None, None
    if re.search(r" (?:elke|iedere|elk|ieder) (?:dag|ochtend|morgen|middag|avond|nacht) | dagelijks ", s):
        rule = "FREQ=DAILY"
    elif re.search(r" (?:(?:elke|iedere) (?:werkdag|doordeweekse dag)|op werkdagen|werkdagen|doordeweeks|door de week) ", s):
        rule, days = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", [0, 1, 2, 3, 4]
    elif re.search(r" (?:(?:elk|ieder) weekend|in het weekend|in de weekenden|op weekenden|weekenden) ", s):
        rule, days = "FREQ=WEEKLY;BYDAY=SA,SU", [5, 6]
    else:
        repeated = [i for i, d in enumerate(DAYS) if re.search(rf" (?:elke|iedere) (?:\w+ en )*{d} | {d}s | {d}en ", s)]
        if repeated:
            rule, days = "FREQ=WEEKLY;BYDAY=" + ",".join(CODES[i] for i in repeated), repeated

    date = _date(s, now) if rule is None else None

    # The time, without the days from now ("over drie dagen") its numbers aren't.
    s = re.sub(r" (?:over|in) \S+ dagen? ", " ", s)
    tokens = s.split()
    numbers = [i for i, w in enumerate(tokens) if _is_number(w) and w not in ("half", "halve", "kwart", "anderhalf",
                                                                             "anderhalve", "driekwart")]
    if not numbers and "middernacht" not in tokens:
        return None  # no time: a day alone is not enough
    if [tokens[i] for i in numbers] in (["een"], ["één"]):
        # "Een" is a number only as a time says it: "om een uur", "half een".
        i = numbers[0]
        if not ((i + 1 < len(tokens) and tokens[i + 1] == "uur") or (i and tokens[i - 1] in ("half", "over", "voor"))):
            return None
    # One time: two numbers only as a clock time says them ("zeven uur
    # dertig", "tien over half acht"), not "om vijf uur om tien".
    every = [i for i, w in enumerate(tokens) if _is_number(w) and w not in ("half", "halve", "kwart")]
    if any(tokens[a + 1 : b] not in _CLOCK_BETWEEN for a, b in zip(every, every[1:])):
        return None
    time = reading.clock(s)
    if time is None:
        return None
    hour, minute, meridiem = time
    if hour == 0 and meridiem is None and "middernacht" not in tokens:
        hour = 12  # "half een" is 12:30 or 0:30, whichever comes first
    said_words = set(tokens)
    if said_words & {"ochtend", "ochtends", "morgens", "vroeg", "vanochtend", "vanmorgen"} or re.search(
        r" (?:elke|iedere) morgen ", s
    ):
        meridiem = "am"
    elif said_words & {"middag", "middags", "vanmiddag", "avond", "avonds", "vanavond"}:
        meridiem = "pm"
    elif said_words & {"nacht", "nachts", "vannacht"}:
        # "Drie uur 's nachts" is early, "elf uur 's nachts" late.
        meridiem = "am" if hour < 6 or hour == 12 else "pm"
    if hour > 12:
        meridiem = None  # 24-hour: "19 uur"
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0

    def at(day: Any, h: int) -> datetime:
        return now.replace(year=day.year, month=day.month, day=day.day, hour=h % 24, minute=minute, second=0, microsecond=0)

    if meridiem is None and 1 <= hour <= 12:
        if date is None and rule is None:
            # The next time it comes round, in the morning or the evening.
            options = [at(now.date(), h) for h in (hour, hour + 12)]
            return When(min(o if o > now else o + timedelta(days=1) for o in options))
        # Another day: an alarm is in the morning; a reminder from 7 to 11
        # in the morning, else in the afternoon.
        if hour != 12 and not alarm and hour < 7:
            hour += 12
    if rule is not None:
        start = at(now.date(), hour)
        while start <= now or (days is not None and start.weekday() not in days):
            start += timedelta(days=1)
        return When(start, rule)
    if date is None:
        start = at(now.date(), hour)
        return When(start if start > now else start + timedelta(days=1))
    start = at(date, hour)
    if start <= now and date == now.date() and not re.search(r" (?:vandaag|vanavond|vanmiddag|vanochtend|vanmorgen) ", s):
        start += timedelta(days=7)  # "op maandag" on a Monday, the time gone: next week's
    return When(start) if start > now else None


def _date(s: str, now: datetime) -> Any:
    """The day ``s`` (lowercase, spaced at its ends) names, if it names one."""
    if " overmorgen " in s:
        return (now + timedelta(days=2)).date()
    if " morgen " in s and not re.search(r" (?:elke|iedere|de) morgen ", s):
        return (now + timedelta(days=1)).date()
    if re.search(r" (?:vandaag|vanavond|vanmiddag|vanochtend|vanmorgen) ", s):
        return now.date()
    date = None
    found = re.search(rf" (?:op |deze |aanstaande |komende |volgende )?({_DAY}) ", s)
    if found:
        ahead = (DAYS.index(found.group(1)) - now.weekday()) % 7
        date = (now + timedelta(days=ahead or (7 if f" volgende {found.group(1)} " in s else 0))).date()
    found = re.search(r" (?:over|in) (\S+) dagen? ", s)
    if found and parse_num(found.group(1)):
        date = (now + timedelta(days=int(parse_num(found.group(1))))).date()
    return date


def day(text: str, now: datetime) -> Any:
    """The day ``text`` names without a time ("van morgen", "op vrijdag"), or None."""
    return _date(_spaced(_joined(text)), now)


_NOT_ABOUT = {
    "de", "het", "een", "mijn", "m'n", "je", "jouw", "jij", "me", "mij", "ik", "om", "te", "aan", "eraan", "er",
    "over", "van", "voor", "dat", "en", "die", "herinnering", "herinneringen", "s",
}


def about(text: str) -> list[str]:
    """What a reminder is about, as words to compare: "mijn herinnering om
    mama te bellen morgen" -> ["mama", "bellen"]."""
    words = re.findall(r"[\w']+", _joined(text).lower())
    return [w for w in words if w not in _NOT_ABOUT and not _is_when_word(w)]


def wants_time(text: str) -> bool:
    """Whether ``text`` names a day or a repeat but no time ("morgen", "elke
    maandag"): asked what time."""
    s = _spaced(_joined(text))
    return bool(re.search(
        rf" (?:morgen|overmorgen|vandaag|vanavond|vanmiddag|vanochtend|vanmorgen|vannacht|elke|iedere|elk|ieder"
        rf"|dagelijks|werkdagen|doordeweeks|weekend|weekenden|{_DAY}|{_DAY}s|{_DAY}en) ", s))


_SWAPS = {"ik": "je", "me": "je", "mij": "je", "mijn": "je", "m'n": "je", "mezelf": "jezelf", "mijzelf": "jezelf"}
"""Said back to the speaker: "dat ik mama moet bellen" -> "je mama moet bellen"."""
_VERBS = {"ben": "bent", "heb": "hebt", "ga": "gaat", "kom": "komt", "wil": "wilt", "doe": "doet", "sta": "staat",
          "word": "wordt", "zal": "zult"}
"""A verb after "ik", as it is after "je"."""
_PARTICLES = {"op", "uit", "aan", "af", "in", "mee", "terug", "weg", "door", "na", "toe", "bij", "voor", "schoon",
              "buiten", "binnen", "open", "dicht", "langs"}
"""A separable verb's first part, joined to it: "op te ruimen" -> "opruimen"."""
_PREPOSITIONS = {"naar", "van", "met", "voor", "in", "op", "uit", "bij", "aan", "door", "over", "om", "tot", "zonder"}


def what(text: str) -> str:
    """A reminder's text, as it is said back and put on the calendar: "eraan
    om mijn moeder te bellen" -> "je moeder bellen", "aan de tandarts" ->
    "de tandarts"."""
    s = text.strip(" ,.?!")
    while True:
        shorter = re.sub(r"^(?:eraan|er aan|aan|om|dat|over)\b\s*", "", s, flags=re.IGNORECASE)
        if shorter == s:
            break
        s = shorter
    out, swapped = [], False
    for word in s.split():
        low = word.lower()
        out.append(_SWAPS.get(low, word))
        swapped = swapped or low == "ik"
    if swapped:
        out = [_VERBS.get(word.lower(), word) for word in out]
    # "mama te bellen": the infinitive alone, a separable verb's part on it.
    if len(out) >= 2 and out[-2].lower() == "te":
        verb = out[-1]
        out = out[:-2]
        if out and out[-1].lower() in _PARTICLES and (len(out) < 2 or out[-2].lower() not in _PREPOSITIONS):
            verb = out.pop() + verb
        out.append(verb)
    return " ".join(out)


# ---------------------------------------------------------------- speaking

EXAMPLES = {
    "alarm_time": "morgen om half acht",
    "alarm": "zeven uur",
    "alarm_other": "acht uur",
    "reminder": "om mama te bellen",
    "reminder_timed": "om vijf uur om mama te bellen",
    "reminder_day": "morgen om mama te bellen",
    "reminder_other": "om de kat te voeren",
    "reminder_nothing": "om",
    "call": "Mama bellen",
    "bins": "De vuilnisbak buitenzetten",
}
"""What the web UI's examples of what alarms and reminders say are made
from (alarms.outcome_examples), as speech-to-text writes them; see English's
for each."""

ALARM_WHEN = "Voor hoe laat moet ik de wekker zetten?"
REMINDER_WHEN = "Wanneer moet ik je eraan herinneren?"
REMINDER_WHAT = "Waaraan moet ik je herinneren?"
NO_ALARMS = "Er zijn geen wekkers gezet."
NO_REMINDERS = "Je hebt geen herinneringen."
CALENDAR_NEEDED = "Voor wekkers en herinneringen is de lokale agenda van Home Assistant nodig, en die kon ik niet instellen."
ALARM_TITLE = "Wekker"
"""An alarm's event, on the calendar."""


def said_when(start: datetime, rrule: str | None, now: datetime) -> str:
    """"7 uur 30", "morgen om 7 uur 30", "vrijdag om 9 uur", "elke werkdag om
    7 uur", "op 30 oktober om 9 uur"."""
    at = f"om {clock(start.hour, start.minute)}"
    if rrule:
        days = re.search(r"BYDAY=([A-Z,]+)", rrule)
        if not days:
            return f"elke dag {at}"
        codes = days.group(1).split(",")
        if codes == CODES[:5]:
            return f"elke werkdag {at}"
        if codes == CODES[5:]:
            return f"elk weekend {at}"
        return f"elke {join([DAYS[CODES.index(c)] for c in codes])} {at}"
    ahead = (start.date() - now.date()).days
    if ahead == 0:
        return clock(start.hour, start.minute)
    if ahead == 1:
        return f"morgen {at}"
    if ahead < 7:
        return f"{DAYS[start.weekday()]} {at}"
    return f"op {start.day} {_MONTHS[start.month - 1]} {at}"


def _at(start: datetime, rrule: str | None, now: datetime) -> str:
    """When, said after a verb: today's "om 7 uur 30", else as ``said_when``."""
    said = said_when(start, rrule, now)
    return f"om {said}" if not rrule and start.date() == now.date() else said


def _from_now(start: datetime, now: datetime) -> str:
    return duration(max(60, round((start - now).total_seconds() / 60) * 60))


def alarm_set(start: datetime, rrule: str | None, now: datetime) -> dict[str, str]:
    specific = f"Wekker gezet voor {said_when(start, rrule, now)}."
    return {"brief": "Wekker gezet.", "specific": specific, "verbose": f"{specific[:-1]}, over {_from_now(start, now)}."}


def reminder_set(what_said: str, start: datetime, rrule: str | None, now: datetime, relative: bool) -> dict[str, str]:
    at = f"over {_from_now(start, now)}" if relative else _at(start, rrule, now)
    told = f": {what_said}" if what_said else ""
    specific = f"Ik herinner je {at}{told}."
    verbose = specific if relative else f"Ik herinner je {at}, over {_from_now(start, now)}{told}."
    return {"brief": "Ik herinner je eraan.", "specific": specific, "verbose": verbose}


def reminder_listed(what_said: str) -> str:
    """A reminder without a time, put on the to-do list."""
    return f"{_capital(what_said)} toegevoegd aan je herinneringen."


def alarm_due(title: str, start: datetime) -> str:
    """What an alarm says when it rings: "Het is 7 uur 30."; a named one first
    says its name."""
    said = f"Het is {clock(start.hour, start.minute)}."
    return said if title.strip().lower() in ("", ALARM_TITLE.lower(), "alarm") else f"{_capital(title.strip())}. {said}"


def reminder_due(text: str) -> str:
    return f"Herinnering: {text.strip().rstrip('.')}."


def _listed(events: list[dict[str, Any]], now: datetime) -> list[str]:
    return [said_when(e["start"], e.get("rrule"), now) for e in events]


def _labels(reminders: list[dict[str, Any]], now: datetime) -> list[str]:
    return [f"{r['text']} {_at(r['start'], r.get('rrule'), now)}" for r in reminders]


def alarms_listed(alarms: list[dict[str, Any]], now: datetime) -> str:
    said = _listed(alarms, now)
    if len(said) == 1:
        return f"Je hebt een wekker voor {said[0]}."
    return f"Je hebt {len(said)} wekkers: {join(said)}."


def reminders_listed(reminders: list[dict[str, Any]], now: datetime) -> str:
    said = _labels(reminders, now)
    if len(said) == 1:
        return f"Je hebt één herinnering: {said[0]}."
    return f"Je hebt {len(said)} herinneringen: {join(said)}."


def alarm_cancelled(alarms: list[dict[str, Any]], now: datetime) -> dict[str, str]:
    said = _listed(alarms, now)
    if len(said) == 1:
        specific = f"Wekker voor {said[0]} geannuleerd."
    else:
        specific = f"{len(said)} wekkers geannuleerd."
    return {"brief": "Wekker geannuleerd." if len(said) == 1 else "Wekkers geannuleerd.", "specific": specific,
            "verbose": f"Wekkers voor {join(said)} geannuleerd." if len(said) > 1 else specific}


def which_alarm(alarms: list[dict[str, Any]], now: datetime) -> str:
    return f"Welke wekker? Je hebt wekkers voor {join(_listed(alarms, now))}."


def which_alarm_asked(alarms: list[dict[str, Any]], now: datetime) -> str:
    """Several alarms fit, asked of a satellite that hears the answer."""
    return f"De wekker voor {join_or(_listed(alarms, now))}?"


def alarm_labels(alarms: list[dict[str, Any]], now: datetime) -> list[str]:
    """How each is told apart (an answer to which_alarm_asked)."""
    return [f"de wekker voor {when}" for when in _listed(alarms, now)]


def alarm_not_found(asked: str, alarms: list[dict[str, Any]], now: datetime) -> str:
    return f"Er is geen wekker voor {asked}. {alarms_listed(alarms, now)}" if alarms else NO_ALARMS


def reminder_cancelled(reminders: list[dict[str, Any]], now: datetime) -> dict[str, str]:
    said = _labels(reminders, now)
    if len(said) == 1:
        specific = f"Herinnering {_at(reminders[0]['start'], reminders[0].get('rrule'), now)} geannuleerd: {reminders[0]['text']}."
    else:
        specific = f"{len(said)} herinneringen geannuleerd."
    return {"brief": "Herinnering geannuleerd." if len(said) == 1 else "Herinneringen geannuleerd.", "specific": specific,
            "verbose": f"Herinneringen geannuleerd: {join(said)}." if len(said) > 1 else specific}


def which_reminder(reminders: list[dict[str, Any]], now: datetime) -> str:
    return f"Welke herinnering? Je hebt {join(_labels(reminders, now))}."


def which_reminder_asked(reminders: list[dict[str, Any]], now: datetime) -> str:
    """Several reminders fit, asked of a satellite that hears the answer."""
    return f"{_capital(join_or(reminder_labels(reminders, now)))}?"


def reminder_labels(reminders: list[dict[str, Any]], now: datetime) -> list[str]:
    """How each is told apart (an answer to which_reminder_asked)."""
    return _labels(reminders, now)


def reminder_not_found(reminders: list[dict[str, Any]], now: datetime) -> str:
    return f"Zo'n herinnering heb ik niet gevonden. {reminders_listed(reminders, now)}" if reminders else NO_REMINDERS
