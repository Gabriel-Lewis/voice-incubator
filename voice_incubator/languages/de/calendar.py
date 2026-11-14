"""Alarms and reminders on the calendar, in German, with English's names (see
voice_incubator/languages/en/calendar.py for what each is): when one is for
-- read from what was said ("morgen um halb acht", "jeden Werktag um 6",
"in 20 Minuten", "am Freitag um 17 Uhr") -- and what the app says about them.

German says a time anywhere in a reminder, its verb last: "erinnere mich
morgen um 9 daran, den Zahnarzt anzurufen", "erinnere mich daran, dass der
Klempner am Freitag um 3 kommt". So the time is the longest run of time words
anywhere in what was said, not only at its start or end. "Morgen" is
tomorrow, but "heute Morgen", "jeden Morgen" and "morgen früh" are mornings.
A reminder's text is said back as an infinitive: "den Zahnarzt anrufen"."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from . import reading
from .skills.dates import DAY_NAMES as _DAY_NAMES
from .skills.dates import MONTH_NAMES as _MONTH_NAMES
from .skills.numbers import parse_num
from .speech import _capital, _duration, clock, join, join_or

# ----------------------------------------------------------------- reading

DAYS = ["montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag"]
CODES = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
_DAY = rf"(?:{'|'.join(DAYS)})"

_NUMBER_WORDS = {
    "null", "ein", "eins", "eine", "einer", "einen", "zwei", "zwo", "drei", "vier", "fünf", "sechs", "sieben",
    "acht", "neun", "zehn", "elf", "zwölf", "dreizehn", "vierzehn", "fünfzehn", "sechzehn", "siebzehn",
    "achtzehn", "neunzehn", "zwanzig", "dreißig", "dreissig", "vierzig", "fünfzig", "hundert", "halb", "halbe",
    "halben", "viertel", "dreiviertel", "anderthalb", "eineinhalb",
}
_COMPOUND = re.compile(r"^(?:ein|zwei|drei|vier|fünf|sechs|sieben|acht|neun)und(?:zwanzig|dreißig|dreissig|vierzig|fünfzig)$")
_WHEN_WORDS = {
    "um", "am", "für", "in", "ab", "und", "nächsten", "nächste", "nächster", "diesen", "diese", "dieser",
    "kommenden", "kommende", "jeden", "jede", "jedes", "jedem", "heute", "morgen", "übermorgen", "früh",
    "morgens", "vormittag", "vormittags", "mittag", "mittags", "nachmittag", "nachmittags", "abend", "abends",
    "nacht", "nachts", "mitternacht", "uhr", "täglich", "tag", "tage", "tagen", "werktag", "werktage",
    "werktagen", "werktags", "wochentags", "wochenende", "wochenenden", "wochenends", "minute", "minuten",
    "stunde", "stunden", "viertelstunde", "dreiviertelstunde", "sonnabend", "sonnabends", "morgige", "morgigen",
    "heutige", "heutigen", *DAYS, *(d + "s" for d in DAYS), *_NUMBER_WORDS,
}
_EDGE = {"um", "am", "für", "in", "ab", "und", "nächsten", "nächste", "diesen", "diese", "kommenden", "jeden", "jede",
         "jedes", "jedem"}
"""Words a time is said with, but which alone are no time."""
_STARTS = {"um", "am", "ab", "für", "in", "heute", "morgen", "übermorgen", "jeden", "jede", "jedes", "diesen",
           "nächsten", "kommenden", "täglich", "werktags", "wochentags", "wochenends", *DAYS, *(d + "s" for d in DAYS)}
"""Words a time said in a reminder may start with."""
_MARKERS = {"um", "uhr", "halb", "viertel", "dreiviertel", "mittag", "mittags", "mitternacht"}
"""Words that make a number a time of day in a reminder: "um 5", "5 Uhr",
"halb 6" -- not "erinnere mich daran, zwei Eier zu kaufen"."""
_LEADING = ("daran", "dran", "dass", "darüber", "an")
"""What a reminder's text may start with, before its time: "daran, morgen
um 9 den Zahnarzt anzurufen"."""


@dataclass
class When:
    """When an alarm or a reminder is: its first time (local), how it repeats
    (an RRULE, or None), and what was said besides (a reminder's text)."""

    start: datetime
    rrule: str | None = None
    rest: str = ""
    relative: bool = False
    """Said from now ("in 20 Minuten")."""
    said: str = ""
    """The words that said when."""


def _plain(word: str) -> str:
    return word.lower().strip(",.!?;:„“\"'")


def _is_number(word: str) -> bool:
    w = _plain(word)
    return w in _NUMBER_WORDS or bool(_COMPOUND.match(w)) or w.isdigit()


def _is_when_word(word: str) -> bool:
    w = _plain(word)
    return w in _WHEN_WORDS or bool(_COMPOUND.match(w)) or bool(re.fullmatch(r"\d{1,2}([:.]\d{2})?", w))


def _runs(words: list[str]) -> list[tuple[int, int]]:
    """Each run of time words: (begin, end)."""
    n = len(words)

    def ok(i: int) -> bool:
        w = _plain(words[i])
        before = _plain(words[i - 1]) if i > 0 else ""
        after = _plain(words[i + 1]) if i + 1 < n else ""
        if w in ("nach", "vor"):  # "viertel nach sieben", "fünf vor halb acht": not "nach dem Ofen sehen"
            return (_is_number(before) or before in ("viertel", "minute", "minuten")) and (_is_number(after) or after == "halb")
        if w == "und":  # "Montag und Mittwoch", "montags und mittwochs"
            return _is_when_word(before) and _is_when_word(after) and before not in _EDGE and after not in _EDGE
        return _is_when_word(words[i])

    out, i = [], 0
    while i < n:
        if not ok(i):
            i += 1
            continue
        begin = i
        while i < n and ok(i):
            i += 1
        end = i
        # Not "und" at its start, nor a word a time is only said with at its end.
        while begin < end and _plain(words[begin]) == "und":
            begin += 1
        while end > begin and _plain(words[end - 1]) in _EDGE:
            end -= 1
        if begin < end:
            out.append((begin, end))
    return out


def _normalized(text: str) -> str:
    """What was said, spaced at its ends and without punctuation, with the day
    words German joins or says as phrases written one way: "Montagmorgen" is
    "Montag morgens", "morgen früh" "morgen morgens", "an Werktagen"
    "werktags"."""
    s = " " + re.sub(r"[,!?;„“\"]|:(?!\d)", " ", text) + " "
    s = re.sub(r"(\d)\.(\d{2})\b", r"\1:\2", s)
    s = re.sub(r"\.(?=\s)", " ", s)
    s = re.sub(rf"\b({_DAY}|heute|morgen)(morgen|vormittag|mittag|nachmittag|abend|nacht)\b", r"\1 \2", s,
               flags=re.IGNORECASE)
    for said, means in (
        (r"am morgen|in der früh|frühmorgens", "morgens"), (r"am vormittag", "vormittags"),
        (r"am nachmittag", "nachmittags"), (r"am abend", "abends"), (r"in der nacht", "nachts"),
        (r"am mittag", "mittags"),
        (r"heute (?:morgen|früh)", "heute morgens"), (r"morgen (?:morgen|früh)", "morgen morgens"),
        (r"(heute|morgen|" + _DAY + r") (vormittag|mittag|nachmittag|abend|nacht)", r"\1 \2s"),
        (rf"({_DAY}) morgen", r"\1 morgens"),
        (r"jeden morgen", "täglich morgens"), (r"jeden vormittag", "täglich vormittags"),
        (r"jeden mittag", "täglich mittags"), (r"jeden nachmittag", "täglich nachmittags"),
        (r"jeden abend", "täglich abends"), (r"jede nacht", "täglich nachts"),
        (r"an werktagen|an jedem werktag|unter der woche|von montag bis freitag|montags bis freitags", "werktags"),
        (r"an wochenenden|an jedem wochenende|jedes wochenende|am wochenende", "wochenends"),
        (rf"an jedem ({_DAY})", r"jeden \1"),
    ):
        s = re.sub(rf"(?<=\s)(?:{said})(?=\s)", means, s, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", s)


def when(text: str, now: datetime, alarm: bool = False) -> When | None:
    """When ``text`` says: a time (and a day, or how it repeats), or a time
    from now; None when it says none. ``now`` is aware local time; an
    ``alarm`` said for another day without morgens or abends is in the
    morning."""
    words = _normalized(text).split()
    best: tuple[When, int, int] | None = None
    for begin, end in _runs(words):
        found = None
        # Not all of it may be the time: less of it, the longest first, from
        # a word a time starts with.
        spans = sorted(((b, e) for b in range(begin, end) for e in range(end, b, -1)
                        if b == begin or _plain(words[b]) in _STARTS), key=lambda span: span[0] - span[1])
        for b, e in spans:
            found = _read(words[b:e], now, alarm, at_start=b == 0 or all(_plain(w) in _LEADING for w in words[:b]))
            if found is not None:
                break
        if found is not None and (best is None or e - b > best[2] - best[1]):
            best = (found, b, e)
    if best is None:
        return None
    found, begin, end = best
    found.rest = " ".join(words[:begin] + words[end:]).strip(" ,")
    found.said = " ".join(words[begin:end])
    return found


_AMOUNTS = {"ein": 1.0, "eine": 1.0, "einer": 1.0, "einen": 1.0, "einer halben": 0.5, "eine halbe": 0.5, "halben": 0.5,
            "halbe": 0.5, "anderthalb": 1.5, "eineinhalb": 1.5, "einer viertel": 0.25, "einer dreiviertel": 0.75}


def _read(run: list[str], now: datetime, alarm: bool, at_start: bool = True) -> When | None:
    """A run of time words as a When; None when it isn't one (or names a day
    but no time: see ``wants_time``). A length alone, without "in", is from
    now only at the start of what was said."""
    s = " " + " ".join(_plain(w) for w in run) + " "

    # From now: "in 20 Minuten", "in einer Stunde", "in einer halben Stunde",
    # "in einer Viertelstunde" -- or a length alone: speech-to-text, or the
    # free text's edge, can drop the "in".
    found = re.search(r" (in )?(?:(\S+(?: \S+)?) (minuten?|stunden?)|(einer |eine )?(viertelstunde|dreiviertelstunde)) ", s)
    if found:
        if not found.group(1) and not at_start:
            return None
        if found.group(5):
            seconds = 900.0 if found.group(5) == "viertelstunde" else 2700.0
        else:
            said = found.group(2)
            amount = _AMOUNTS[said] if said in _AMOUNTS else parse_num(said)
            seconds = float(amount or 0) * (60 if found.group(3).startswith("minute") else 3600)
        rest = s.replace(found.group(0), " ").strip()
        if seconds and not rest:
            return When(now + timedelta(seconds=seconds), relative=True)
        # "fünf Minuten nach halb sieben" is a time of day; anything else
        # besides a length is not one.
        if not re.match(r"(?:nach|vor) ", rest):
            return None

    rule, days = None, None
    if re.search(r" (jeden tag|täglich|alle tage) ", s):
        rule = "FREQ=DAILY"
    elif re.search(r" (jeden werktag|werktags|wochentags) ", s):
        rule, days = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", [0, 1, 2, 3, 4]
    elif re.search(r" (wochenends) ", s):
        rule, days = "FREQ=WEEKLY;BYDAY=SA,SU", [5, 6]
    else:
        said_days = [*DAYS[:5], "samstag|sonnabend", "sonntag"]
        repeated = [i for i, d in enumerate(said_days)
                    if re.search(rf" (?:jeden|jedem) (?:\w+ und )*(?:{d}) | (?:{d})s ", s)]
        if repeated:
            rule, days = "FREQ=WEEKLY;BYDAY=" + ",".join(CODES[i] for i in repeated), repeated

    date = _date(s, now) if rule is None else None

    clock_said = re.sub(r" in \S+ tagen? ", " ", s)
    numbers = sorted(_NUMBER_WORDS - {"ein", "eine", "einer", "einen", "halbe", "halben", "viertel", "dreiviertel",
                                      "anderthalb", "eineinhalb"})
    if not re.search(r"\d|mittags?|mitternacht| (?:" + "|".join(numbers) + r") |\w+und\w+zig| ein uhr ", clock_said):
        return None  # no time: a day alone is not enough
    words = clock_said.split()
    if not alarm and not (_MARKERS & set(words) or re.search(r"\d[:.]\d", clock_said)):
        return None  # a number in a reminder, not its time
    # "um ein Uhr mittags" is 13:00; "Mittag" alone noon.
    if re.search(r" mittags? ", clock_said) and reading.clock(re.sub(r" mittags? ", " ", clock_said)) is not None:
        clock_said = re.sub(r" mittags? ", " nachmittags ", clock_said)
    time = reading.clock(clock_said)
    if time is None:
        return None
    hour, minute, meridiem = time
    night = bool(re.search(r" nachts? ", s))
    if night and hour == 12:
        hour, meridiem = 0, "am"
    elif night and hour < 5:
        meridiem = "am"  # "um 2 Uhr nachts"
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0

    def at(day: Any, h: int) -> datetime:
        return now.replace(year=day.year, month=day.month, day=day.day, hour=h % 24, minute=minute, second=0, microsecond=0)

    if night and date is not None and date == now.date() and hour < 5:
        date = date + timedelta(days=1)  # "heute Nacht um 2": after midnight
    if meridiem is None and 1 <= hour <= 12:
        if date is None and rule is None:
            # The next time it comes round, morning or afternoon.
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
    if start <= now and date == now.date() and not re.search(r" (heute|heutige|heutigen) ", s):
        start += timedelta(days=7)  # "am Montag" on a Monday, the time gone: next week's
    return When(start) if start > now else None


def _date(s: str, now: datetime) -> Any:
    """The day ``s`` (lowercase, spaced at its ends) names, if it names one."""
    if re.search(r" übermorgen ", s):
        return (now + timedelta(days=2)).date()
    if re.search(r" (morgen|morgige|morgigen|morgiger) ", s):
        return (now + timedelta(days=1)).date()
    if re.search(r" (heute|heutige|heutigen|heutiger) ", s):
        return now.date()
    date = None
    found = re.search(rf" (?:am |an |diesen |kommenden |nächsten |am kommenden |am nächsten )?({_DAY}|sonnabend) ", s)
    if found:
        index = DAYS.index(found.group(1)) if found.group(1) in DAYS else 5
        ahead = (index - now.weekday()) % 7
        date = (now + timedelta(days=ahead or (7 if re.search(rf" nächsten {found.group(1)} ", s) else 0))).date()
    found = re.search(r" in (\S+) tagen? ", s)
    if found and parse_num(found.group(1)):
        date = (now + timedelta(days=int(parse_num(found.group(1))))).date()
    return date


def day(text: str, now: datetime) -> Any:
    """The day ``text`` names without a time ("morgen", "die morgige", "am Freitag"), or None."""
    return _date(_normalized(text).lower(), now)


_NOT_ABOUT = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer", "eines", "mein", "meine",
    "meinen", "meinem", "meiner", "meines", "dein", "deine", "deinen", "deinem", "deiner", "deines", "mich", "mir",
    "dich", "dir", "ich", "du", "zu", "an", "daran", "dran", "dass", "für", "von", "über", "und", "erinnerung",
    "erinnerungen", "wecker", "zum", "zur",
}


def about(text: str) -> list[str]:
    """What a reminder is about, as words to compare: "meine Erinnerung,
    morgen Mama anzurufen" -> ["mama", "anrufen"]."""
    words = re.findall(r"[\wäöüß]+", text.lower())
    words = [_infinitive(w) for w in words]
    return [w for w in words if w not in _NOT_ABOUT and not _is_when_word(w)]


def wants_time(text: str) -> bool:
    """Whether ``text`` names a day or a repeat but no time ("morgen", "jeden
    Montag"): asked what time."""
    s = _normalized(text).lower()
    return bool(re.search(rf" (heute|morgen|übermorgen|jeden|jede|jedes|täglich|werktags|wochentags|wochenends|"
                          rf"sonnabends?|{_DAY}s?) ", s))


_SEPARABLE = sorted(
    ("ab", "an", "auf", "aus", "bei", "ein", "fest", "fort", "her", "herein", "heraus", "herunter", "hin", "hinaus",
     "los", "mit", "nach", "raus", "rein", "runter", "rüber", "vor", "vorbei", "weg", "weiter", "zu", "zurück",
     "zusammen", "hoch", "heim", "statt", "teil", "frei", "kennen", "sauber"),
    key=len, reverse=True,
)
"""Prefixes a verb's "zu" goes after: "anzurufen" is "anrufen"."""


def _infinitive(word: str) -> str:
    """A zu-infinitive as the infinitive: "anzurufen" -> "anrufen"."""
    for prefix in _SEPARABLE:
        if word.startswith(prefix + "zu") and len(word) > len(prefix) + 4 and re.search(r"(?:en|ern|eln|n)$", word):
            return prefix + word[len(prefix) + 2:]
    return word


def what(text: str) -> str:
    """A reminder's text, as it is said back: an infinitive, to do --
    "daran, meine Mama anzurufen" -> "deine Mama anrufen"."""
    s = text.strip(" ,.?!")
    s = re.sub(r"^(?:(?:daran|dran|darüber)\b[\s,]*)?(?:dass\b\s*)?", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^an\b\s*", "", s, flags=re.IGNORECASE)
    swaps = {"mich": "dich", "mir": "dir", "ich": "du", "mein": "dein", "meine": "deine", "meinen": "deinen",
             "meinem": "deinem", "meiner": "deiner", "meines": "deines"}
    said = s.replace(",", " ").split()
    if "ich" in (w.lower() for w in said):  # "dass ich Tabletten nehmen muss": "du ... musst"
        swaps |= {"bin": "bist", "habe": "hast", "hab": "hast", "muss": "musst", "will": "willst", "soll": "sollst",
                  "kann": "kannst", "darf": "darfst", "möchte": "möchtest", "werde": "wirst"}
    words = [swaps.get(w.lower(), w) for w in said]
    if len(words) >= 2 and words[-2].lower() == "zu":
        del words[-2]  # "Milch zu kaufen": "Milch kaufen"
    elif words:
        words[-1] = _infinitive(words[-1])
    return " ".join(words)


# ---------------------------------------------------------------- speaking

EXAMPLES = {
    "alarm_time": "morgen um halb acht",
    "alarm": "sieben",
    "alarm_other": "acht",
    "reminder": "daran mama anzurufen",
    "reminder_timed": "um 17 uhr daran mama anzurufen",
    "reminder_day": "morgen daran mama anzurufen",
    "reminder_other": "daran die katze zu füttern",
    "reminder_nothing": "daran",
    "call": "Mama anrufen",
    "bins": "Den Müll rausbringen",
}
"""What the web UI's examples of what alarms and reminders say are made
from (alarms.outcome_examples), as speech-to-text writes them -- lowercase,
as the reminder and alarm slots hold them: an alarm's time (``alarm_time``:
one set; ``alarm``: the 7 o'clock one cancelled; ``alarm_other``: one there
is none at), a reminder (``reminder``: one there is; ``reminder_timed``: one
set with a time; ``reminder_day``: one cancelled by its day;
``reminder_other``: one there is none of; ``reminder_nothing``: what is said
when what to be reminded of is missing), and two reminders' titles on the
calendar (``call``, the 17 Uhr one; ``bins``)."""

ALARM_WHEN = "Für wann soll ich den Wecker stellen?"
REMINDER_WHEN = "Wann soll ich dich erinnern?"
REMINDER_WHAT = "Woran soll ich dich erinnern?"
NO_ALARMS = "Es ist kein Wecker gestellt."
NO_REMINDERS = "Du hast keine Erinnerungen."
CALENDAR_NEEDED = ("Für Wecker und Erinnerungen braucht es den lokalen Kalender von Home Assistant, "
                   "und ich konnte ihn nicht einrichten.")
ALARM_TITLE = "Wecker"
"""An alarm's event, on the calendar."""


def said_when(start: datetime, rrule: str | None, now: datetime) -> str:
    """"7 Uhr 30", "morgen um 7 Uhr 30", "Freitag um 9 Uhr", "jeden Werktag
    um 7 Uhr", "den 30. Oktober um 9 Uhr": after "für" ("Wecker für morgen
    um 7 Uhr") or on its own."""
    time = clock(start.hour, start.minute)
    at = "um " + time
    if rrule:
        days = re.search(r"BYDAY=([A-Z,]+)", rrule)
        if not days:
            return f"jeden Tag {at}"
        codes = days.group(1).split(",")
        if codes == CODES[:5]:
            return f"jeden Werktag {at}"
        return f"jeden {join([_DAY_NAMES[CODES.index(c)] for c in codes])} {at}"
    ahead = (start.date() - now.date()).days
    if ahead == 0:
        return time
    if ahead == 1:
        return f"morgen {at}"
    if ahead < 7:
        return f"{_DAY_NAMES[start.weekday()]} {at}"
    return f"den {start.day}. {_MONTH_NAMES[start.month - 1]} {at}"


def _at(start: datetime, rrule: str | None, now: datetime) -> str:
    """When, said in a sentence: "um 17 Uhr", "morgen um 9 Uhr", "am Freitag
    um 9 Uhr", "am 30. Oktober um 9 Uhr"."""
    said = said_when(start, rrule, now)
    if said.startswith("den "):
        return "am " + said[4:]
    if said.startswith(tuple(_DAY_NAMES)):
        return "am " + said
    return said if said.startswith(("morgen", "jeden")) else f"um {said}"


_INSIDE = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer", "dein", "deine", "deinen",
    "deinem", "deiner", "du", "nach", "zum", "zur", "zu", "mit", "bei", "für", "an", "auf", "in", "im",
}


def _inside(text: str) -> str:
    """A reminder's text in a sentence: "den Müll rausbringen", its first
    letter lowercase where that word is no noun."""
    first = text.split(" ", 1)[0]
    return text[:1].lower() + text[1:] if first.lower() in _INSIDE else text


def _from_now(start: datetime, now: datetime) -> str:
    """"in einer Stunde", "in 20 Minuten"."""
    return "in " + _duration(max(60, round((start - now).total_seconds() / 60) * 60), dative=True)


def alarm_set(start: datetime, rrule: str | None, now: datetime) -> dict[str, str]:
    specific = f"Wecker für {said_when(start, rrule, now)} gestellt."
    return {"brief": "Wecker gestellt.", "specific": specific, "verbose": f"{specific[:-1]}, {_from_now(start, now)}."}


def reminder_set(what_said: str, start: datetime, rrule: str | None, now: datetime, relative: bool) -> dict[str, str]:
    at = _from_now(start, now) if relative else _at(start, rrule, now)
    later = at if relative else f"{at}, {_from_now(start, now)}"
    specific = f"Ich erinnere dich {at}: {_capital(what_said)}." if what_said else f"Ich erinnere dich {at}."
    verbose = f"Ich erinnere dich {later}: {_capital(what_said)}." if what_said else f"Ich erinnere dich {later}."
    return {"brief": "Ich erinnere dich.", "specific": specific, "verbose": verbose}


def reminder_listed(what_said: str) -> str:
    """A reminder without a time, put on the to-do list."""
    return f"Zu deinen Erinnerungen hinzugefügt: {_capital(what_said)}."


def alarm_due(title: str, start: datetime) -> str:
    """What an alarm says when it rings: "Es ist 7 Uhr 30."; a named one
    first says its name."""
    said = f"Es ist {clock(start.hour, start.minute)}."
    return said if title.strip().lower() in ("", ALARM_TITLE.lower(), "alarm") else f"{_capital(title.strip())}. {said}"


def reminder_due(text: str) -> str:
    return f"Erinnerung: {text.strip().rstrip('.')}."


def _listed(events: list[dict[str, Any]], now: datetime) -> list[str]:
    return [said_when(e["start"], e.get("rrule"), now) for e in events]


def alarms_listed(alarms: list[dict[str, Any]], now: datetime) -> str:
    said = _listed(alarms, now)
    if len(said) == 1:
        return f"Du hast einen Wecker für {said[0]}."
    return f"Du hast {len(said)} Wecker: {join(said)}."


def reminders_listed(reminders: list[dict[str, Any]], now: datetime) -> str:
    said = reminder_labels(reminders, now)
    if len(said) == 1:
        return f"Du hast eine Erinnerung: {said[0]}."
    return f"Du hast {len(said)} Erinnerungen: {join(said)}."


def alarm_cancelled(alarms: list[dict[str, Any]], now: datetime) -> dict[str, str]:
    said = _listed(alarms, now)
    if len(said) == 1:
        specific = f"Wecker für {said[0]} gelöscht."
    else:
        specific = f"{len(said)} Wecker gelöscht."
    return {"brief": "Wecker gelöscht.", "specific": specific,
            "verbose": f"Wecker für {join(said)} gelöscht." if len(said) > 1 else specific}


def which_alarm(alarms: list[dict[str, Any]], now: datetime) -> str:
    return f"Welcher Wecker? Du hast Wecker für {join(_listed(alarms, now))}."


def which_alarm_asked(alarms: list[dict[str, Any]], now: datetime) -> str:
    """Several alarms fit, asked of a satellite that hears the answer."""
    return f"{_capital(join_or(alarm_labels(alarms, now)))}?"


def alarm_labels(alarms: list[dict[str, Any]], now: datetime) -> list[str]:
    """How each is told apart (an answer to which_alarm_asked)."""
    return [f"der Wecker für {when}" for when in _listed(alarms, now)]


def alarm_not_found(asked: str, alarms: list[dict[str, Any]], now: datetime) -> str:
    return f"Es gibt keinen Wecker für {asked}. {alarms_listed(alarms, now)}" if alarms else NO_ALARMS


def reminder_cancelled(reminders: list[dict[str, Any]], now: datetime) -> dict[str, str]:
    said = reminder_labels(reminders, now)
    if len(said) == 1:
        first = reminders[0]
        specific = f"Erinnerung für {said_when(first['start'], first.get('rrule'), now)} gelöscht: {first['text']}."
    else:
        specific = f"{len(said)} Erinnerungen gelöscht."
    return {"brief": "Erinnerung gelöscht." if len(said) == 1 else "Erinnerungen gelöscht.", "specific": specific,
            "verbose": f"Erinnerungen gelöscht: {join(said)}." if len(said) > 1 else specific}


def which_reminder(reminders: list[dict[str, Any]], now: datetime) -> str:
    return f"Welche Erinnerung? {_capital(join_or(reminder_labels(reminders, now)))}?"


def which_reminder_asked(reminders: list[dict[str, Any]], now: datetime) -> str:
    """Several reminders fit, asked of a satellite that hears the answer."""
    return f"{_capital(join_or(reminder_labels(reminders, now)))}?"


def reminder_labels(reminders: list[dict[str, Any]], now: datetime) -> list[str]:
    """How each is told apart (an answer to which_reminder_asked): "um 17 Uhr
    Mama anrufen"."""
    return [f"{_at(r['start'], r.get('rrule'), now)} {_inside(r['text'])}" for r in reminders]


def reminder_not_found(reminders: list[dict[str, Any]], now: datetime) -> str:
    return f"So eine Erinnerung gibt es nicht. {reminders_listed(reminders, now)}" if reminders else NO_REMINDERS
