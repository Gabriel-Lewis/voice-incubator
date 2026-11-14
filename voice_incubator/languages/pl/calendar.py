"""Alarms and reminders on the calendar, in Polish, with English's names (see
voice_incubator/languages/en/calendar.py for what each is): when one is for
-- read from what was said ("jutro o siódmej trzydzieści", "w dni robocze na
szóstą", "za 20 minut", "o siedemnastej w piątek", "wpół do ósmej") -- and
what the app says about them.

A time of day is said by its hour's ordinal, in the case its preposition
takes ("o siódmej", "na siódmą"), with halves and quarters before the next
hour ("wpół do ósmej" is 7:30, "za kwadrans ósma" 7:45): the pack's clock
(reading.py) reads it. A day is said by its name, in its case too ("w
środę", "w każdą środę", "we wtorki", "od poniedziałku do piątku"). Read
folded, so typed without diacritics too.

An alarm is said with "na" ("Ustawiono budzik na jutro na siódmą"), a
reminder with "o" ("Przypomnę ci jutro o dziewiątej: zadzwonić do mamy").
What a reminder is about is said back from the listener's side: "żebym
zadzwonił do mojej mamy" is "zadzwonić do twojej mamy" -- the past tense
after "żebym" as the infinitive, when it is one of the regular kinds;
otherwise "żebyś ..." -- and "że mam wizytę" is "masz wizytę"."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from . import reading
from .skills.dates import MONTH_OF
from .skills.numbers import count, fold, ordinal, parse_num, read_ordinal
from .speech import _capital, _clock, duration, join, join_or

# ----------------------------------------------------------------- reading

DAYS = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
CODES = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]

_DAY_ONE = [
    ("poniedzialek", "poniedzialku"), ("wtorek", "wtorku"), ("sroda", "srode", "srody"), ("czwartek", "czwartku"),
    ("piatek", "piatku"), ("sobota", "sobote", "soboty"), ("niedziela", "niedziele", "niedzieli"),
]
"""A weekday (folded), as one day is said: "w środę", "każdego czwartku"."""
_DAY_MANY = ["poniedzialki", "wtorki", "srody", "czwartki", "piatki", "soboty", "niedziele"]
"""Every one of a weekday (folded): "w poniedziałki". "W niedziele" is one
Sunday as often as every one (an "ę" said without its nasal): every Sunday
only beside another day ("w soboty i niedziele")."""
_DAY_FORMS = {form for forms in _DAY_ONE for form in forms} | set(_DAY_MANY)
_DAY_ADJECTIVES = ["poniedzialkow", "wtorkow", "srodow", "czwartkow", "piatkow", "sobotn", "niedzieln"]
"""A weekday's adjective (folded): "piątkowy budzik"."""


def _alternatives(forms) -> str:
    return "|".join(sorted(forms, key=len, reverse=True))


_WHEN_WORDS = {
    "o", "na", "w", "we", "za", "i", "oraz", "od", "godzinie", "godzine", "godzina", "godz",
    "rano", "rana", "ranem", "wieczorem", "wieczor", "wieczora", "nocy", "noc", "poludniu", "popoludniu", "poludnie",
    "poludniem", "polnoc", "polnocy", "dzis", "dzisiaj", "jutro", "pojutrze", "codziennie", "dzien", "dni", "dnia",
    "kazdy", "kazda", "kazde", "kazdego", "kazdej", "robocze", "roboczy", "roboczego", "roboczych", "powszednie",
    "powszedni", "powszedniego", "weekend", "weekendy", "weekendu", "tydzien", "tygodnie", "tygodni", "przyszly",
    "przyszla", "przyszle", "przyszlym", "najblizszy", "najblizsza", "najblizsze", "najblizszym", "ten", "te", "ta",
    "tym", "minut", "minuty", "minute", "minuta", "godzin", "godziny", "kwadrans", "kwadranse", "kwadransy", "pol",
    "wpol", "poltorej", "poltora", *_DAY_FORMS,
}
"""Words a time is said with (folded)."""
_EDGE = {"o", "na", "w", "we", "za", "i", "oraz", "od", "do", "po", "co", "z", "nad", "przed", "a"}
"""Words a time is said with, but which alone are no time: at its end, they
are what follows it ("o ósmej | o zakupach")."""
_STARTS = {
    "o", "na", "w", "we", "za", "od", "jutro", "dzis", "dzisiaj", "pojutrze", "co", "codziennie", "kazdy", "kazda",
    "kazdego", "kazdej", *_DAY_FORMS,
}
"""Words a time said at the end of a reminder may start with."""
_LEADING = {"mi", "nam", "prosze", "tez", "jeszcze"}
"""Words said between "przypomnij" and the reminder: not its."""
_AFTER_CO = {"dzien", "rano", "wieczor", "noc", "tydzien", "weekend", "dziennie", *(f for forms in _DAY_ONE for f in forms)}


@dataclass
class When:
    """When an alarm or a reminder is: its first time (local), how it repeats
    (an RRULE, or None), and what was said besides (a reminder's text)."""

    start: datetime
    rrule: str | None = None
    rest: str = ""
    relative: bool = False
    """Said from now ("za 20 minut")."""
    said: str = ""
    """The words that said when."""


def _plain(word: str) -> str:
    return fold(word.lower()).strip(",.!?;:")


def _number(word: str) -> bool:
    return bool(re.fullmatch(r"\d{1,2}(?:[:.]\d{2})?", word)) or parse_num(word) is not None or read_ordinal(word) is not None


def _is_when_word(word: str) -> bool:
    w = _plain(word)
    return w in _WHEN_WORDS or _number(w)


def _run(words: list[str], from_end: bool) -> tuple[int, int]:
    """The longest run of time words at the start or the end: (begin, end)."""
    n = len(words)
    plain = [_plain(w) for w in words]

    def ok(i: int) -> bool:
        w = plain[i]
        before = plain[i - 1] if i > 0 else ""
        after = plain[i + 1] if i + 1 < n else ""
        if w == "do":  # "wpół do ósmej", "od poniedziałku do piątku": not "do mamy"
            return before in ("wpol", "pol") or before in _DAY_FORMS
        if w == "po":  # "kwadrans po siódmej", "po południu": not "po pracy"
            return after == "poludniu" or before in ("kwadrans",) or before.startswith("minut") or _number(before)
        if w == "co":  # "co poniedziałek", "co rano": not "co kupić"
            return after in _AFTER_CO
        if w in ("z", "nad", "przed"):  # "z rana", "nad ranem", "przed południem"
            return after in ("rana", "ranem", "poludniem")
        return _is_when_word(words[i])

    if from_end:
        begin = n
        while begin > 0 and ok(begin - 1):
            begin -= 1
        end = n
    else:
        end = 0
        while end < n and ok(end):
            end += 1
        begin = 0
    # Not "i" at its start, nor a preposition at its end: they belong to
    # what was said besides.
    while begin < end and plain[begin] in ("i", "a", "oraz"):
        begin += 1
    while end > begin and plain[end - 1] in _EDGE:
        end -= 1
    return begin, end


def when(text: str, now: datetime, alarm: bool = False) -> When | None:
    """When ``text`` says: a time (and a day, or how it repeats), or a time
    from now; None when it says none. ``now`` is aware local time; an
    ``alarm`` said for another day without "rano" or "wieczorem" is in the
    morning."""
    words = text.split()
    while words and _plain(words[0]) in _LEADING:
        words = words[1:]
    best: tuple[When, int] | None = None
    for from_end in (False, True):
        begin, end = _run(words, from_end)
        found = None
        while begin < end:
            found = _read(" ".join(words[begin:end]), now, alarm)
            if found is not None:
                break
            # Not all of it is the time ("żebym odpoczął dziesięć minut o
            # siedemnastej"): less of it, from where it meets the rest, to a
            # word a time starts with.
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
            found.said = " ".join(words[begin:end]).strip(" ,")
            best = (found, end - begin)
    return best[0] if best else None


def _normal(text: str) -> str:
    """Lowercase, folded, without punctuation but a time's ("7:30", "7.30")."""
    s = fold(text.lower())
    s = re.sub(r"(?<!\d)[.:]|[.:](?!\d)|[,!?;]", " ", s)
    return " ".join(s.split())


_UNIT = r"minut[aey]?|minute|godzin[aey]?|godzine|kwadrans[eyow]*"


def _term(said: str) -> float | None:
    """Seconds in a length said: "20 minut", "godzinę", "pół godziny", "dwie
    i pół godziny", "trzy kwadranse"; None."""
    found = re.fullmatch(rf"(?:(.+?) )?({_UNIT})", said)
    if not found:
        return None
    value = 1.0 if found.group(1) is None else parse_num(found.group(1))
    if not value:
        return None
    unit = found.group(2)
    return float(value) * (60 if unit.startswith("minut") else 900 if unit.startswith("kwadrans") else 3600)


def _length(said: str) -> float | None:
    """Seconds from now: "za 20 minut", "za godzinę i kwadrans", or a length
    alone; None."""
    said = re.sub(r"^za ", "", said)
    whole = _term(said)
    if whole:
        return whole
    for joined in re.finditer(r" i ", said):
        first, second = _term(said[: joined.start()]), _term(said[joined.end():])
        if first and second:
            return first + second
    return None


def _read(said: str, now: datetime, alarm: bool) -> When | None:
    """A run of time words as a When; None when it isn't one (or names a day
    but no time: see ``wants_time``)."""
    t = " " + _normal(said) + " "
    # "o godzinie siódmej", "na godzinę siódmą": the hour's word, no length.
    t = re.sub(r" (o|na) (?:godz|godzinie|godzine|godzina) ", r" \1 ", t)

    # From now: "za 20 minut", "za godzinę", "za pół godziny", "za
    # godzinę i kwadrans" -- or a length alone: the free text's edge can
    # drop the "za".
    seconds = _length(t.strip())
    if seconds:
        return When(now + timedelta(seconds=seconds), relative=True)
    if re.search(r" (?:minut\w*|godzin\w*|kwadrans\w*|sekund\w*) ", t):
        # A length with more said is no time ("dziesięć minut o siedemnastej"),
        # but a clock's minutes are: "dziesięć minut po siódmej", "kwadrans
        # po siódmej", "za kwadrans ósma".
        clock_said = re.search(r" (?:minut\w*|kwadrans) po ", t) or re.search(r" za kwadrans (?!minut)", t)
        if not clock_said or re.search(r" (?:godzin\w*|sekund\w*) ", t):
            return None

    rule, days = None, None
    if re.search(r" (dni robocze|dni powszednie|dzien roboczy|dzien powszedni|dnia roboczego|dni roboczych"
                 r"|od poniedzialku do piatku) ", t):
        rule, days = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", [0, 1, 2, 3, 4]
    elif re.search(r" (codziennie|co dzien|co dziennie|kazdego dnia|kazdy dzien|co rano|kazdego ranka|kazdego rana"
                   r"|co wieczor|kazdego wieczoru|kazdego wieczora|co noc|kazdej nocy) ", t):
        rule = "FREQ=DAILY"
    elif re.search(r" (weekendy|co weekend|kazdy weekend|kazdego weekendu|w soboty i niedziele) ", t):
        rule, days = "FREQ=WEEKLY;BYDAY=SA,SU", [5, 6]
    else:
        repeated = []
        for i, forms in enumerate(_DAY_ONE):
            every = rf" (?:co|kazd\w*) (?:\S+ (?:i|oraz) )*(?:{_alternatives(forms)}) "
            many = rf" we? (?:\S+ (?:i|oraz) (?:we? )?){'+' if i == 6 else '*'}{_DAY_MANY[i]} "
            if re.search(every, t) or re.search(many, t):
                repeated.append(i)
        if repeated:
            rule, days = "FREQ=WEEKLY;BYDAY=" + ",".join(CODES[i] for i in repeated), repeated

    date = _date(t, now) if rule is None else None

    time = reading.clock(t)
    if time is None:
        return None  # no time: a day alone is not enough
    hour, minute, meridiem = time
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0

    def at(day: Any, h: int) -> datetime:
        return now.replace(year=day.year, month=day.month, day=day.day, hour=h % 24, minute=minute, second=0, microsecond=0)

    if meridiem is None and 1 <= hour <= 12:
        if date is None and rule is None:
            # The next time it comes round, in the morning or after noon.
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
    if start <= now and date == now.date() and not re.search(r" (dzis|dzisiaj) ", t):
        start += timedelta(days=7)  # "w środę" on a Wednesday, the time gone: next week's
    return When(start) if start > now else None


def _date(t: str, now: datetime) -> Any:
    """The day ``t`` (normal, spaced at its ends) names, if it names one."""
    if " pojutrze " in t:
        return (now + timedelta(days=2)).date()
    if " jutro " in t:
        return (now + timedelta(days=1)).date()
    if re.search(r" (dzis|dzisiaj) ", t):
        return now.date()
    date = None
    every = _alternatives(f for forms in _DAY_ONE for f in forms)
    found = re.search(rf" (?:we? )?(?:(ten|te|ta|tym|przyszl\w*|najblizsz\w*) )?({every}) ", t)
    if found:
        index = next(i for i, forms in enumerate(_DAY_ONE) if found.group(2) in forms)
        ahead = (index - now.weekday()) % 7
        next_week = bool(found.group(1)) and found.group(1).startswith("przyszl")
        date = (now + timedelta(days=ahead or (7 if next_week else 0))).date()
    found = re.search(r" za (?:(\S+) )?(dni|dnia|dzien|tydzien|tygodnie|tygodni) ", t)
    if found:
        number = 1 if found.group(1) is None else parse_num(found.group(1))
        if number:
            weeks = found.group(2).startswith(("tydz", "tyg"))
            date = (now + timedelta(days=int(number) * (7 if weeks else 1))).date()
    return date


def day(text: str, now: datetime) -> Any:
    """The day ``text`` names without a time ("jutrzejszy", "na piątek",
    "piątkowy"), or None."""
    t = " " + _normal(text) + " "
    if re.search(r" pojutrzejsz\w* ", t):
        return (now + timedelta(days=2)).date()
    if re.search(r" jutrzejsz\w* ", t):
        return (now + timedelta(days=1)).date()
    if re.search(r" dzisiejsz\w* ", t):
        return now.date()
    for index, stem in enumerate(_DAY_ADJECTIVES):
        if re.search(rf" {stem}\w* ", t):
            return (now + timedelta(days=(index - now.weekday()) % 7)).date()
    return _date(t, now)


_NOT_ABOUT = {fold(word) for word in (
    "mi mnie mój moja moje moją mojej mojego moim moich twój twoja twoje twoją twojej twojego twoim twoich ci ciebie "
    "się sobie do z ze że żeby żebym żebyś żebyśmy aby abym abyś by bym byś to ten ta te tego tej tym tę a "
    "przypomnienie przypomnienia przypomnień przypomnieniu przypomnij jest"
).split()}
_ENDINGS = sorted(
    ("ami", "ach", "ow", "om", "em", "ie", "ia", "il", "la", "li", "ly", "ac", "ic", "yc", "ec", "uc", "a", "e", "i", "y",
     "o", "u", "l", "c"),
    key=len, reverse=True,
)
"""Endings taken off a word (folded) to compare it whatever its case:
"mamy", "mamie" and "mama" are "mam"; "zadzwonić" and "zadzwonił"
"zadzwon"."""
_ALTERNATIONS = (("scie", "st"), ("dzie", "d"), ("cie", "t"), ("rze", "r"))
"""A locative's ending, and the consonant it changed (folded): "o dentyście"
is "dentyst", "w ogrodzie" "ogrod", "o kocie" "kot"."""


def _stem(word: str) -> str:
    for ending, said in _ALTERNATIONS:
        if word.endswith(ending) and len(word) - len(ending) >= 2:
            return word[: -len(ending)] + said
    for ending in _ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            return word[: -len(ending)]
    return word


def about(text: str) -> list[str]:
    """What a reminder is about, as words to compare, whatever their case:
    "moje przypomnienie o mamie jutro" -> ["mam"]."""
    words = re.findall(r"\w+", fold(text.lower()))
    return [_stem(w) for w in words if w not in _NOT_ABOUT and not _is_when_word(w)]


def wants_time(text: str) -> bool:
    """Whether ``text`` names a day or a repeat but no time ("jutro", "w
    każdy poniedziałek"): asked what time."""
    t = " " + _normal(text) + " "
    days = _alternatives(_DAY_FORMS)
    return bool(re.search(
        rf" (dzis|dzisiaj|jutro|pojutrze|codziennie|kazd\w*|robocze|powszednie|weekendy|{days}) ", t
    ) or re.search(rf" co (?:{_alternatives(_AFTER_CO)}) ", t))


_SWAPS = {
    "mi": "ci", "mnie": "ciebie", "mną": "tobą", "ja": "ty", "mój": "twój", "moja": "twoja", "moje": "twoje",
    "mojego": "twojego", "mojej": "twojej", "mojemu": "twojemu", "moją": "twoją", "moim": "twoim", "moich": "twoich",
    "moimi": "twoimi", "nam": "wam", "nas": "was", "my": "wy", "nasz": "wasz", "nasza": "wasza", "nasze": "wasze",
    "naszego": "waszego", "naszej": "waszej", "naszą": "waszą", "naszym": "waszym", "naszych": "waszych",
    "żebym": "żebyś", "abym": "abyś", "bym": "byś", "żebyśmy": "żebyście", "abyśmy": "abyście", "byśmy": "byście",
    "jestem": "jesteś", "mam": "masz", "muszę": "musisz", "mogę": "możesz", "chcę": "chcesz", "idę": "idziesz",
    "jadę": "jedziesz", "będę": "będziesz", "powinienem": "powinieneś", "powinnam": "powinnaś",
}
"""The speaker's words, said back to them."""
_TO = {"żebym", "żebyś", "żeby", "abym", "abyś", "aby", "bym", "byś", "żebyśmy", "abyśmy", "byśmy"}
"""What a reminder to do something starts with: "żebym zadzwonił"."""
_CLAUSE = ("żebyś", "abyś", "byś", "żebyście", "abyście", "byście", "żeby", "aby", "by")
"""What a reminder said back as a clause starts with: ", żebyś się nie spóźnił"."""
_IRREGULAR = {
    form: infinitive
    for infinitive, forms in {
        "pójść": "poszedł poszła poszli poszły", "wyjść": "wyszedł wyszła wyszli wyszły",
        "przyjść": "przyszedł przyszła przyszli przyszły", "wejść": "wszedł weszła weszli weszły",
        "zejść": "zszedł zeszła zeszli zeszły", "znaleźć": "znalazł znalazła znaleźli znalazły",
        "wynieść": "wyniósł wyniosła wynieśli wyniosły", "przynieść": "przyniósł przyniosła przynieśli przyniosły",
        "zanieść": "zaniósł zaniosła zanieśli zaniosły", "zjeść": "zjadł zjadła zjedli zjadły",
        "móc": "mógł mogła mogli mogły", "pomóc": "pomógł pomogła pomogli pomogły", "upiec": "upiekł upiekła upiekli upiekły",
    }.items()
    for form in forms.split()
}
_PAST = sorted(
    [(end, "ieć") for end in ("iał", "iała", "ieli", "iały")] + [(end, "ąć") for end in ("ął", "ęła", "ęli", "ęły")]
    + [(end, "ić") for end in ("ił", "iła", "ili", "iły")] + [(end, "yć") for end in ("ył", "yła", "yli", "yły")]
    + [(end, "ać") for end in ("ał", "ała", "ali", "ały")] + [(end, "uć") for end in ("uł", "uła", "uli", "uły")],
    key=lambda pair: len(pair[0]), reverse=True,
)
"""A past tense's ending, and its infinitive's: "zadzwonił" -> "zadzwonić",
"wzięła" -> "wziąć", "musiał" -> "musieć"."""


def _infinitive(word: str) -> str | None:
    """A verb in the past tense as its infinitive ("kupiła" -> "kupić"), an
    infinitive as it is; None when unsure ("leżał", "się")."""
    w = word.lower()
    if w.endswith(("ć", "c")) and len(w) > 2:
        return w
    if w in _IRREGULAR:
        return _IRREGULAR[w]
    for ending, infinitive in _PAST:
        if w.endswith(ending) and len(w) - len(ending) >= 2:
            stem = w[: -len(ending)]
            if infinitive == "ać" and stem.endswith(("cz", "sz", "ż", "rz")):
                return None  # "leżał" is "leżeć", "słyszał" "słyszeć"
            return stem + infinitive
    return None


def what(text: str) -> str:
    """A reminder's text, as it is said back: "żebym zadzwonił do mojej
    mamy" -> "zadzwonić do twojej mamy"; "że mam wizytę" -> "masz wizytę";
    "o zakupach" as it is."""
    words = text.strip(" ,.?!").split()
    while words and words[0].lower().strip(",") in ("mi", "nam"):
        words = words[1:]
    if len(words) == 1 and words[0].lower().strip(",") in (*_TO, "że", "iż", "o"):
        return ""  # what it is to be was not said
    if words and words[0].lower().strip(",") in ("że", "iż"):
        words = words[1:]
    elif words and words[0].lower().strip(",") in _TO and len(words) > 1:
        verb = _infinitive(words[1])
        if verb is not None:
            words = [verb, *words[2:]]
    return " ".join(_SWAPS.get(w.lower(), w) for w in words)


def _then(what_said: str, clause: str = ", ", about_it: str = " ", other: str = ": ") -> str:
    """What joins a reminder's text to what comes before it: a clause, what
    it is about ("o zakupach"), or what to do."""
    first = what_said.split()[0].lower() if what_said.split() else ""
    return clause if first in _CLAUSE else about_it if first == "o" else other


def _lead(text: str) -> str:
    """A reminder's text inside a sentence: its first word lowercase, when
    it is one of the app's ("Zadzwonić do mamy" -> "zadzwonić do mamy"), not
    a name."""
    words = text.split()
    if not words:
        return text
    first = words[0]
    if first[1:] == first[1:].lower() and (first.lower() in (*_CLAUSE, "o") or first.lower().endswith("ć")):
        return first[:1].lower() + text[1:]
    return text


# ---------------------------------------------------------------- speaking

EXAMPLES = {
    "alarm_time": "jutro na siódmą trzydzieści",
    "alarm": "siódmą",
    "alarm_other": "ósmą",
    "reminder": "żebym zadzwonił do mamy",
    "reminder_timed": "o siedemnastej, żebym zadzwonił do mamy",
    "reminder_day": "żebym zadzwonił do mamy jutro",
    "reminder_other": "żebym nakarmił kota",
    "reminder_nothing": "żebym",
    "call": "Zadzwonić do mamy",
    "bins": "Wynieść śmieci",
}
"""What the web UI's examples of what alarms and reminders say are made
from (alarms.outcome_examples), as speech-to-text writes them (see
English's)."""

ALARM_WHEN = "Na którą godzinę ustawić budzik?"
REMINDER_WHEN = "Kiedy mam ci przypomnieć?"
REMINDER_WHAT = "O czym mam ci przypomnieć?"
NO_ALARMS = "Nie ma żadnych budzików."
NO_REMINDERS = "Nie masz żadnych przypomnień."
CALENDAR_NEEDED = "Budziki i przypomnienia wymagają kalendarza Local Calendar w Home Assistant, a nie udało się go utworzyć."
ALARM_TITLE = "Budzik"
"""An alarm's event, on the calendar."""

_ON_DAY = ["w poniedziałek", "we wtorek", "w środę", "w czwartek", "w piątek", "w sobotę", "w niedzielę"]
_FOR_DAY = ["na poniedziałek", "na wtorek", "na środę", "na czwartek", "na piątek", "na sobotę", "na niedzielę"]
_EVERY = ["w każdy poniedziałek", "w każdy wtorek", "w każdą środę", "w każdy czwartek", "w każdy piątek",
          "w każdą sobotę", "w każdą niedzielę"]
_DAYS_MANY = ["poniedziałki", "wtorki", "środy", "czwartki", "piątki", "soboty", "niedziele"]


def _repeat(rrule: str) -> str:
    """How it repeats: "codziennie", "w dni robocze", "w każdą środę", "w
    poniedziałki i środy"."""
    days = re.search(r"BYDAY=([A-Z,]+)", rrule)
    if not days:
        return "codziennie"
    codes = days.group(1).split(",")
    if codes == CODES[:5]:
        return "w dni robocze"
    if codes == CODES[5:]:
        return "w weekendy"
    indexes = [CODES.index(c) for c in codes]
    if len(indexes) == 1:
        return _EVERY[indexes[0]]
    return ("we " if indexes[0] == 1 else "w ") + join([_DAYS_MANY[i] for i in indexes])


def _date_said(start: datetime) -> str:
    """"trzydziestego października"."""
    return f"{ordinal(start.day, 'gen')} {MONTH_OF[start.month - 1]}"


def said_when(start: datetime, rrule: str | None, now: datetime) -> str:
    """When a reminder is, as it follows a verb: "o siódmej trzydzieści",
    "jutro o siódmej trzydzieści", "w piątek o dziewiątej", "w dni robocze o
    siódmej", "trzydziestego października o dziewiątej"."""
    time = f"o {_clock(start.hour, start.minute, 'loc')}"
    if rrule:
        return f"{_repeat(rrule)} {time}"
    ahead = (start.date() - now.date()).days
    if ahead == 0:
        return time
    if ahead == 1:
        return f"jutro {time}"
    if ahead < 7:
        return f"{_ON_DAY[start.weekday()]} {time}"
    return f"{_date_said(start)} {time}"


def _for(start: datetime, rrule: str | None, now: datetime) -> str:
    """When an alarm is, as it is set for: "na siódmą trzydzieści", "na
    jutro na siódmą", "na szóstą w dni robocze"."""
    time = f"na {_clock(start.hour, start.minute, 'acc')}"
    if rrule:
        return f"{time} {_repeat(rrule)}"
    ahead = (start.date() - now.date()).days
    if ahead == 0:
        return time
    if ahead == 1:
        return f"na jutro {time}"
    if ahead < 7:
        return f"{_FOR_DAY[start.weekday()]} {time}"
    return f"na {_date_said(start)} {time}"


def _from_now(start: datetime, now: datetime) -> str:
    """How long until then, after "za": "jedną minutę", "5 godzin i 30 minut"."""
    return duration(max(60, round((start - now).total_seconds() / 60) * 60), adjective=True)


def alarm_set(start: datetime, rrule: str | None, now: datetime) -> dict[str, str]:
    specific = f"Ustawiono budzik {_for(start, rrule, now)}."
    return {"brief": "Ustawiono budzik.", "specific": specific, "verbose": f"{specific} Zadzwoni za {_from_now(start, now)}."}


def reminder_set(what_said: str, start: datetime, rrule: str | None, now: datetime, relative: bool) -> dict[str, str]:
    at = f"za {_from_now(start, now)}" if relative else said_when(start, rrule, now)
    specific = f"Przypomnę ci {at}{_then(what_said)}{what_said}." if what_said else f"Przypomnę ci {at}."
    verbose = specific if relative else f"{specific} To za {_from_now(start, now)}."
    return {"brief": "Przypomnę ci.", "specific": specific, "verbose": verbose}


def reminder_listed(what_said: str) -> str:
    """A reminder without a time, put on the to-do list."""
    return f"Zapisano przypomnienie{_then(what_said)}{what_said}."


def alarm_due(title: str, start: datetime) -> str:
    """What an alarm says when it rings: "Jest siódma trzydzieści."; a named
    one first says its name."""
    said = f"Jest {_clock(start.hour, start.minute)}."
    unnamed = ("", ALARM_TITLE.lower(), "alarm", "budzik")
    return said if title.strip().lower() in unnamed else f"{_capital(title.strip())}. {said}"


def reminder_due(text: str) -> str:
    """What a reminder says when it is due: "Przypomnienie: zadzwonić do
    mamy.", "Przypominam o zakupach.", "Przypominam, żebyś ..."."""
    said = text.strip().rstrip(".")
    lead = _lead(said)
    return _then(said, f"Przypominam, {lead}.", f"Przypominam {lead}.", f"Przypomnienie: {lead}.")


def _listed(events: list[dict[str, Any]], now: datetime) -> list[str]:
    return [said_when(e["start"], e.get("rrule"), now) for e in events]


def _alarms(alarms: list[dict[str, Any]], now: datetime) -> list[str]:
    return [_for(e["start"], e.get("rrule"), now) for e in alarms]


def _reminders(reminders: list[dict[str, Any]], now: datetime) -> list[str]:
    return [f"{_lead(r['text'])} {when}" for r, when in zip(reminders, _listed(reminders, now), strict=True)]


def alarms_listed(alarms: list[dict[str, Any]], now: datetime) -> str:
    said = _alarms(alarms, now)
    if len(said) == 1:
        return f"Masz budzik {said[0]}."
    return f"Masz {count(len(said), 'budzik', 'budziki', 'budzików')}: {join(said)}."


def reminders_listed(reminders: list[dict[str, Any]], now: datetime) -> str:
    said = _reminders(reminders, now)
    if len(said) == 1:
        return f"Masz jedno przypomnienie: {said[0]}."
    return f"Masz {count(len(said), 'przypomnienie', 'przypomnienia', 'przypomnień')}: {join(said)}."


def alarm_cancelled(alarms: list[dict[str, Any]], now: datetime) -> dict[str, str]:
    said = _alarms(alarms, now)
    if len(said) == 1:
        specific = f"Anulowano budzik {said[0]}."
    else:
        specific = f"Anulowano {count(len(said), 'budzik', 'budziki', 'budzików')}."
    return {"brief": "Anulowano budzik." if len(said) == 1 else "Anulowano budziki.", "specific": specific,
            "verbose": f"Anulowano budziki: {join(said)}." if len(said) > 1 else specific}


def which_alarm(alarms: list[dict[str, Any]], now: datetime) -> str:
    return f"Który budzik: {join_or(_alarms(alarms, now))}?"


def which_alarm_asked(alarms: list[dict[str, Any]], now: datetime) -> str:
    """Several alarms fit, asked of a satellite that hears the answer."""
    return f"{_capital(join_or(alarm_labels(alarms, now)))}?"


def alarm_labels(alarms: list[dict[str, Any]], now: datetime) -> list[str]:
    """How each is told apart (an answer to which_alarm_asked)."""
    return [f"budzik {when}" for when in _alarms(alarms, now)]


def alarm_not_found(asked: str, alarms: list[dict[str, Any]], now: datetime) -> str:
    return f"Nie ma budzika {asked}. {alarms_listed(alarms, now)}" if alarms else NO_ALARMS


def reminder_cancelled(reminders: list[dict[str, Any]], now: datetime) -> dict[str, str]:
    said = _reminders(reminders, now)
    if len(said) == 1:
        specific = f"Anulowano przypomnienie {_listed(reminders, now)[0]}: {_lead(reminders[0]['text'])}."
    else:
        specific = f"Anulowano {count(len(said), 'przypomnienie', 'przypomnienia', 'przypomnień')}."
    return {"brief": "Anulowano przypomnienie." if len(said) == 1 else "Anulowano przypomnienia.", "specific": specific,
            "verbose": f"Anulowano przypomnienia: {join(said)}." if len(said) > 1 else specific}


def which_reminder(reminders: list[dict[str, Any]], now: datetime) -> str:
    return f"Które przypomnienie: {join_or(_reminders(reminders, now))}?"


def which_reminder_asked(reminders: list[dict[str, Any]], now: datetime) -> str:
    """Several reminders fit, asked of a satellite that hears the answer."""
    return f"{_capital(join_or(reminder_labels(reminders, now)))}?"


def reminder_labels(reminders: list[dict[str, Any]], now: datetime) -> list[str]:
    """How each is told apart (an answer to which_reminder_asked)."""
    return _reminders(reminders, now)


def reminder_not_found(reminders: list[dict[str, Any]], now: datetime) -> str:
    return f"Nie ma takiego przypomnienia. {reminders_listed(reminders, now)}" if reminders else NO_REMINDERS
