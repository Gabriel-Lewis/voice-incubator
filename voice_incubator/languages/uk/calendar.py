"""Alarms and reminders on the calendar, in Ukrainian: when one is for -- read
from what was said ("на сьому тридцять завтра", "по буднях о шостій", "через
двадцять хвилин", "о п'ятій вечора в п'ятницю") -- and what the app says
about them, with English's names (voice_incubator/languages/en/calendar.py;
voice_incubator/alarms.py calls them).

A time of day is its hour's ordinal in the case its preposition asks for ("о
сьомій", "на сьому", "сьома ранку"), or a cardinal ("на сім тридцять"),
read by the pack's clock (reading.clock: "пів на восьму" is 7:30, "за
чверть восьма" 7:45, "чверть на восьму" 7:15). "Ранку" is the morning, "дня"
and "вечора" the afternoon and evening, "ночі" the night: "о десятій ночі"
is 22:00, "о другій ночі" 2:00. A day is "сьогодні", "завтра",
"післязавтра", a weekday in the accusative ("у понеділок", "у середу"), or
"через три дні"; a repeat "щодня", "по буднях", "по вихідних", a weekday
with "що-" or "кожного" or in the plural ("щопонеділка", "кожної середи",
"по понеділках і середах"). From now is "через" (or "за") and a length:
"через двадцять хвилин", "через годину", "через півтори години".

A reminder's text is what is left ("подзвонити мамі", "що прийде
сантехнік"): its time is at its start or its end, and is said with a
preposition ("о п'ятій") or with the part of the day ("сьома ранку") -- a
bare "другу" in "подзвонити другу" is a friend, not two o'clock. An alarm's
words are all its time.

What is said names times with "о" ("завтра о сьомій тридцять", "по буднях
о шостій сорок п'ять") and a reminder's text after a colon ("Нагадаю о
сімнадцятій: подзвонити мамі"), so nothing has to agree with it."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from . import reading
from .numerals import NUMBER_WORDS, ORDINAL_ENDINGS, cardinal, ordinal, plural
from .skills.dates import MONTHS_OF
from .skills.numbers import parse_num
from .speech import _at, _capital, clock, duration, join, join_or

# ----------------------------------------------------------------- reading

DAYS = ["понеділок", "вівторок", "середа", "четвер", "п'ятниця", "субота", "неділя"]
CODES = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]

_ON = ["понеділок", "вівторок", "середу", "четвер", "п'ятницю", "суботу", "неділю"]
"""A weekday after "у" or "на" (the accusative): "у середу"."""
_OF = ["понеділка", "вівторка", "середи", "четверга", "п'ятниці", "суботи", "неділі"]
"""After "кожного", "наступного", "до" (the genitive): "кожної середи"."""
_EVERY = ["що" + d for d in _OF]
"""Every one: "щопонеділка", "щосереди"."""
_PLURAL = [
    *(["понеділках", "вівторках", "середах", "четвергах", "п'ятницях", "суботах", "неділях"]),
    *(["понеділкам", "вівторкам", "середам", "четвергам", "п'ятницям", "суботам", "неділям"]),
]
"""After "по" (every one): "по понеділках", and, as often said, "по понеділкам"."""

_DAY_FORMS: dict[str, tuple[int, bool]] = {
    **{w: (i, False) for names in (DAYS, _ON, _OF) for i, w in enumerate(names)},
    **{w: (i % 7, True) for names in (_EVERY, _PLURAL) for i, w in enumerate(names)},
}
"""A weekday's word -> (its index, whether it says every one)."""


def _ordinals() -> set[str]:
    """An hour's ordinal, one word, in any case and gender: "сьома", "сьому",
    "сьомій", "двадцятої"."""
    return {ordinal(hour, form) for hour in range(0, 25) for form in ORDINAL_ENDINGS if " " not in ordinal(hour, form)}


_ORDINALS = _ordinals()
_MINUTE_UNITS = {"хвилин", "хвилина", "хвилини", "хвилину", "хв"}
_HOUR_UNITS = {"година", "години", "годин", "годину", "год", "годинку"}
_CLOCK_WORDS = {
    "пів", "напів", "опів", "чверть", "чверті", "за", "без", "на", "нуль", "ноль",
    "опівночі", "північ", "півночі", "опівдні", "полудень", "полудня", "південь",
    *_MINUTE_UNITS, *_HOUR_UNITS, "годині",
}
"""Words of a clock time besides its numbers: "пів на восьму", "за чверть
восьма", "десять хвилин на восьму", "о сьомій годині"."""
_NOON = {"опівдні", "полудень", "полудня", "південь"}
_MIDNIGHT = {"опівночі", "північ", "півночі"}

_MORNING = {"ранку", "вранці", "зранку", "ранок", "щоранку"}
_AFTERNOON = {"дня", "вдень", "пополудні", "пообіді", "вечора", "увечері", "ввечері", "вечір", "щовечора"}
_NIGHT = {"ночі", "вночі", "уночі", "щоночі"}
_PARTS = _MORNING | _AFTERNOON | _NIGHT
"""The part of the day a time is in."""

_DATE_WORDS = {"сьогодні", "завтра", "післязавтра"}
_NEXT = {"наступного", "наступної", "наступний", "наступну"}
_THIS = {"цього", "цієї", "цей", "цю", "цієї"}
_EVERY_WORDS = {"кожного", "кожної", "кожен", "кожний", "кожну", "кожна", "кожні"}
_DAY_UNITS = {"день", "дні", "днів", "добу", "доби", "діб"}

_DAILY = [("щодня",), ("щоранку",), ("щовечора",), ("щоночі",), ("кожного", "дня"), ("кожен", "день"),
          ("кожний", "день"), ("кожного", "ранку"), ("кожного", "вечора"), ("кожної", "ночі"), ("кожен", "ранок"),
          ("кожен", "вечір"), ("кожну", "ніч")]
_WEEKDAYS = [("щобудня",), ("по", "буднях"), ("по", "будням"), ("у", "будні"), ("в", "будні"), ("будніми", "днями"),
             ("кожного", "буднього", "дня"), ("кожен", "будній", "день"), ("по", "робочих", "днях"),
             ("по", "робочим", "дням"), ("у", "робочі", "дні"), ("в", "робочі", "дні")]
_WEEKENDS = [("по", "вихідних"), ("по", "вихідним"), ("у", "вихідні"), ("в", "вихідні"), ("кожні", "вихідні"),
             ("щовихідних",)]

_PREPOSITIONS = {"о", "об", "на", "в", "у", "до", "з", "по", "і", "й", "та", "рівно"}
"""What may stand before or between a time's parts without being one."""
_AT = {"о", "об", "на", "в", "у"}
"""What introduces a clock time in a reminder: "о п'ятій", "на сьому", "в сім"."""
_JOINERS = {"і", "й", "та"}

_WHEN_WORDS = {
    *_PREPOSITIONS, "через", "по", *NUMBER_WORDS, *_ORDINALS, *_CLOCK_WORDS, *_PARTS, *_DATE_WORDS, *_NEXT, *_THIS,
    *_EVERY_WORDS, *_DAY_UNITS, *_DAY_FORMS, "дня", "ранок", "вечір", "ніч", "будні", "буднях", "будням", "будніми",
    "буднього", "будній", "вихідні", "вихідних", "вихідним", "робочих", "робочим", "робочі", "днях", "дням", "днями",
    "після", "обіду", "півгодини", "півтори", "півтора", "половиною", "кома",
    *(w for phrase in _DAILY + _WEEKDAYS + _WEEKENDS for w in phrase),
}
_GOES_ON = {*NUMBER_WORDS, *_ORDINALS, *_MINUTE_UNITS, *_HOUR_UNITS, *_DAY_UNITS, "кома", "з", "половиною", "години"}
"""Words that carry on the one before: a time is not cut before them."""
_STARTS = {
    *_AT, "через", "за", "без", "пів", "напів", "опів", "чверть", "по", *_DATE_WORDS, *_NEXT, *_THIS, *_EVERY_WORDS,
    *_DAY_FORMS, "щодня", "щоранку", "щовечора", "щоночі", "щобудня", "щовихідних", *_MIDNIGHT, *_NOON,
}
"""Words a time said at the end of a reminder may start with."""


@dataclass
class When:
    """When an alarm or a reminder is: its first time (local), how it repeats
    (an RRULE, or None), and what was said besides (a reminder's text)."""

    start: datetime
    rrule: str | None = None
    rest: str = ""
    relative: bool = False
    """Said from now ("через двадцять хвилин")."""
    said: str = ""
    """The words that said when."""


def _plain(word: str) -> str:
    return word.lower().strip(",.!?;:«»\"").replace("’", "'").replace("ʼ", "'")


def _hour_word(word: str) -> bool:
    """An hour's ordinal, also as a transcript may write it: joined to "о"
    ("осьомій"), or without its last "й" ("сьомі")."""
    for candidate in (word, word + "й") if word.endswith("і") else (word,):
        for joined in ("", "об", "о"):
            if candidate.startswith(joined) and candidate[len(joined):] in _ORDINALS:
                return True
    return False


def _is_when_word(word: str) -> bool:
    w = _plain(word)
    return w in _WHEN_WORDS or _hour_word(w) or bool(re.fullmatch(r"\d{1,2}(?:[:.]\d{2})?", w))


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
    # Not "і" or "а" at its start: they belong to what was said besides.
    while begin < end and _plain(words[begin]) in (*_JOINERS, "а"):
        begin += 1
    return begin, end


def _joined(text: str) -> str:
    """The words speech-to-text splits: "після завтра", "що дня", "що
    понеділка"; and "пʼять" with the model's apostrophe."""
    text = text.replace("’", "'").replace("ʼ", "'")
    text = re.sub(r"\bпісля\s+завтра\b", "післязавтра", text, flags=re.IGNORECASE)
    every = "|".join(["дня", "ранку", "вечора", "ночі", "будня", *_OF])
    return re.sub(rf"\bщо\s+({every})\b", r"що\1", text, flags=re.IGNORECASE)


def when(text: str, now: datetime, alarm: bool = False) -> When | None:
    """When ``text`` says: a time (and a day, or how it repeats), or a time
    from now; None when it says none. ``now`` is aware local time; an
    ``alarm`` said for another day without "ранку" or "вечора" is in the
    morning, and its words are all its time."""
    words = _joined(text).split()
    best: tuple[When, int] | None = None
    for from_end in (False, True):
        begin, end = _run(words, from_end)
        found = None
        while begin < end:
            # At the very start a reminder's time may lack its preposition: the
            # matcher takes a leading "на" or "у" for filler ("на п'яту ...").
            found = _read(" ".join(words[begin:end]), now, alarm, bare=alarm or begin == 0)
            if found is not None:
                break
            # Not all of it is the time ("відпочити десять хвилин о п'ятій"):
            # less of it, from where it meets the rest, to a word a time
            # starts or ends with.
            if from_end:
                begin += 1
                while begin < end and _plain(words[begin]) not in _STARTS and not _hour_word(_plain(words[begin])):
                    begin += 1
            else:
                # Not between a number and its unit: "на дві | години".
                end -= 1
                while end > begin and _plain(words[end]) in _GOES_ON:
                    end -= 1
        if found is not None and (best is None or end - begin > best[1]):
            found.rest = " ".join(words[:begin] + words[end:]).strip(" ,")
            found.said = " ".join(words[begin:end])
            best = (found, end - begin)
    return best[0] if best else None


def _tokens(said: str) -> list[str]:
    """What was said as words to read: lowercase, "7.30" as "7:30", "осьомій"
    as "о сьомій", "півгодини" as "пів години"."""
    text = said.lower().replace("’", "'").replace("ʼ", "'")
    text = re.sub(r"(\d{1,2})[.h](\d{2})\b", r"\1:\2", text)
    text = re.sub(r"\bпівгодини\b", "пів години", text)
    text = re.sub(r"\bгодинку\b", "годину", text)
    out = []
    for word in re.findall(r"\d{1,2}:\d{2}|\d+|[а-яіїєґ'-]+|[a-z]+", text):
        word = word.strip("-")
        if word.endswith("і") and word not in _ORDINALS and word + "й" in _ORDINALS:
            word += "й"  # "сьомі": "сьомій"
        for joined in ("об", "о"):
            if word.startswith(joined) and word not in _WHEN_WORDS and word[len(joined):] in _ORDINALS:
                out.append(joined)
                word = word[len(joined):]
                break
        if word:
            out.append(word)
    return out


def _phrases(words: list[str], phrases: list[tuple[str, ...]], used: set[int]) -> tuple[str, ...] | None:
    """The first of ``phrases`` in ``words``: its words (and the prepositions
    before it) marked ``used``; None."""
    for phrase in phrases:
        for i in range(len(words) - len(phrase) + 1):
            if tuple(words[i : i + len(phrase)]) == phrase and not used & set(range(i, i + len(phrase))):
                used.update(range(i, i + len(phrase)))
                _before(words, i, used)
                return phrase
    return None


def _before(words: list[str], i: int, used: set[int]) -> None:
    """The prepositions before word ``i`` belong with it: "у понеділок"."""
    j = i - 1
    while j >= 0 and words[j] in _PREPOSITIONS and j not in used:
        used.add(j)
        j -= 1


def _length(words: list[str]) -> float | None:
    """A length said ("двадцять хвилин", "годину", "півтори години", "годину і
    десять хвилин") as seconds; None when ``words`` are something else."""
    s = " ".join(words)
    hours = r"(?:година|години|годин|годину|год)"
    minutes = r"(?:хвилина|хвилини|хвилин|хвилину|хв)"

    def amount(said: str | None, unit: str) -> float | None:
        # Without a number, one: "годину", "хвилину" (not "години").
        if said is None:
            return 1.0 if unit in ("година", "годину", "хвилина", "хвилину") else None
        return parse_num(said)

    found = re.fullmatch(rf"(?:(.+?) )?({hours}) (?:(?:і|й|та) )?(.+?) ({minutes})", s)
    if found:
        h, m = amount(found.group(1), found.group(2)), amount(found.group(3), found.group(4))
        return None if h is None or m is None else h * 3600 + m * 60
    found = re.fullmatch(rf"(?:(.+?) )?({hours}|{minutes})", s)
    if found:
        value = amount(found.group(1), found.group(2))
        if value is None or value <= 0:
            return None
        return value * (60 if re.fullmatch(minutes, found.group(2)) else 3600)
    return None


def _is_length(words: list[str]) -> bool:
    """Whether ``words`` hold a length that is no part of a clock time:
    "десять хвилин", "дві години" -- not "за п'ять хвилин восьма", "десять
    хвилин на восьму" or "о сьомій годині"."""
    for i, word in enumerate(words):
        after = words[i + 1] if i + 1 < len(words) else ""
        if word in _MINUTE_UNITS:
            if after in _ORDINALS or (after == "на" and i + 2 < len(words) and words[i + 2] in _ORDINALS):
                continue
            return True
        if word in _HOUR_UNITS and not (i and words[i - 1] in _ORDINALS) and word != "годині":
            return True
    return False


def _read(said: str, now: datetime, alarm: bool, bare: bool = False) -> When | None:
    """A run of time words as a When; None when it isn't one (or names a day
    but no time: see ``wants_time``). ``bare``: a clock time without a
    preposition or a part of the day ("сьому") is one."""
    words = _tokens(said)
    if not words:
        return None

    # From now: "через двадцять хвилин", "за годину"; an alarm's length alone
    # too ("вісім годин").
    lead = words[0] in ("через", "за")
    seconds = _length(words[1:] if lead else words)
    if seconds is not None:
        if not lead and not alarm:
            return None  # "відпочити десять хвилин": the reminder's own
        return When(now + timedelta(seconds=seconds), relative=True)
    if _is_length(words):
        return None

    used: set[int] = set()
    rule, days, daily = None, None, _phrases(words, _DAILY, used)
    if daily:
        rule = "FREQ=DAILY"
    elif _phrases(words, _WEEKDAYS, used):
        rule, days = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", [0, 1, 2, 3, 4]
    elif _phrases(words, _WEEKENDS, used):
        rule, days = "FREQ=WEEKLY;BYDAY=SA,SU", [5, 6]
    date, said_today, next_week, repeated = None, False, False, []
    every = False
    for i, word in enumerate(words):
        if i in used:
            continue
        if word in _EVERY_WORDS:
            every = True
            used.add(i)
            _before(words, i, used)
        elif word in _DAY_FORMS:
            index, plural_said = _DAY_FORMS[word]
            used.add(i)
            _before(words, i, used)
            if plural_said or every or (i and words[i - 1] == "по"):
                repeated.append(index)
            elif date is None:
                date = index
        elif word in _JOINERS and (every or repeated):
            used.add(i)
        elif word in _NEXT or word in _THIS:
            next_week = next_week or word in _NEXT
            used.add(i)
            _before(words, i, used)
        else:
            every = False
    if rule is None and repeated:
        repeated = sorted(set(repeated))
        rule, days = "FREQ=WEEKLY;BYDAY=" + ",".join(CODES[i] for i in repeated), repeated

    day = None
    if rule is None:
        if isinstance(date, int):
            ahead = (date - now.weekday()) % 7
            day = (now + timedelta(days=ahead or (7 if next_week else 0))).date()
        for i, word in enumerate(words):
            if word in _DATE_WORDS:
                used.add(i)
                _before(words, i, used)
                said_today = word == "сьогодні"
                day = (now + timedelta(days=("сьогодні", "завтра", "післязавтра").index(word))).date()
        found = _in_days(words, used)
        if found is not None:
            day = (now + timedelta(days=found)).date()
    else:
        for i, word in enumerate(words):
            if word in _DATE_WORDS:
                used.add(i)  # "щодня, починаючи з завтра": the rule's

    # The part of the day: "ранку", "вечора", "після обіду".
    part = None
    for i, word in enumerate(words):
        if i in used:
            continue
        if word in _PARTS or (word == "після" and i + 1 < len(words) and words[i + 1] == "обіду"):
            part = "am" if word in _MORNING else "night" if word in _NIGHT else "pm"
            used.add(i)
            _before(words, i, used)
            if word == "після":
                used.add(i + 1)
    if daily and part is None:  # "щоранку", "кожного вечора": the part of the day too
        said = set(daily)
        part = ("am" if said & {"щоранку", "ранку", "ранок"} else "pm" if said & {"щовечора", "вечора", "вечір"}
                else "night" if said & {"щоночі", "ночі", "ніч"} else None)

    # What is left is the clock time, introduced by a preposition or not.
    rest = [w for i, w in enumerate(words) if i not in used]
    introduced = False
    while rest and rest[0] in _PREPOSITIONS:
        introduced = introduced or rest[0] in _AT
        rest.pop(0)
    while rest and rest[-1] in _PREPOSITIONS:
        rest.pop()
    numbers = [w for w in rest if w in NUMBER_WORDS or w in _ORDINALS or re.fullmatch(r"\d{1,2}(?::\d{2})?", w)]
    if not numbers and not set(rest) & (_NOON | _MIDNIGHT):
        return None  # no time: a day alone is not enough
    if any(not (w in NUMBER_WORDS or w in _ORDINALS or w in _CLOCK_WORDS or re.fullmatch(r"\d{1,2}(?::\d{2})?", w))
           for w in rest):
        return None
    if sum(1 for w in rest if w in _ORDINALS and w not in NUMBER_WORDS) > 1:
        return None  # "другу о п'ятій": two hours
    clocked = any(w in ("пів", "напів", "опів", "чверть", "чверті", "за", "без") or ":" in w for w in rest)
    if not bare and not (introduced or part or clocked or set(rest) & (_NOON | _MIDNIGHT)):
        return None  # "подзвонити другу": a friend, not two o'clock
    time = reading.clock(" ".join(rest))
    if time is None:
        return None
    hour, minute, meridiem = time
    if set(rest) & _NOON:
        meridiem = "pm"
    if part == "night":
        meridiem = "pm" if 7 <= hour <= 11 else "am"
        if hour == 12:
            hour = 0
    elif part is not None:
        meridiem = part
    if hour > 12:
        meridiem = None  # 24-hour
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0

    def at(on: Any, h: int) -> datetime:
        return now.replace(year=on.year, month=on.month, day=on.day, hour=h % 24, minute=minute, second=0, microsecond=0)

    if meridiem is None and 1 <= hour <= 12:
        if day is None and rule is None:
            # The next time it comes round, in the morning or the afternoon.
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
    if day is None:
        start = at(now.date(), hour)
        return When(start if start > now else start + timedelta(days=1))
    start = at(day, hour)
    if start <= now and day == now.date() and not said_today:
        start += timedelta(days=7)  # "у понеділок" on a Monday, the time gone: next week's
    return When(start) if start > now else None


def _in_days(words: list[str], used: set[int]) -> int | None:
    """How many days ahead "через три дні", "через день" says (its words
    marked ``used``), or None."""
    for i, word in enumerate(words):
        if word != "через" or i in used:
            continue
        for j in range(i + 1, min(i + 4, len(words))):
            if words[j] in _DAY_UNITS:
                said = " ".join(words[i + 1 : j])
                count = 1 if not said else parse_num(said)
                if count:
                    used.update(range(i, j + 1))
                    return int(count)
                break
    return None


def _date(words: list[str], now: datetime) -> Any:
    """The day ``words`` name without a time, if they name one."""
    used: set[int] = set()
    for word in words:
        if word in _DATE_WORDS:
            return (now + timedelta(days=("сьогодні", "завтра", "післязавтра").index(word))).date()
    found = _in_days(words, used)
    if found is not None:
        return (now + timedelta(days=found)).date()
    for i, word in enumerate(words):
        if word in _DAY_FORMS and not _DAY_FORMS[word][1]:
            ahead = (_DAY_FORMS[word][0] - now.weekday()) % 7
            next_week = any(w in _NEXT for w in words[max(0, i - 2) : i])
            return (now + timedelta(days=ahead or (7 if next_week else 0))).date()
    return None


def day(text: str, now: datetime) -> Any:
    """The day ``text`` names without a time ("завтрашній", "на п'ятницю"), or None."""
    words = _tokens(_joined(text))
    for word in words:
        for stem, ahead in (("післязавтрашн", 2), ("завтрашн", 1), ("сьогоднішн", 0)):
            if word.startswith(stem):
                return (now + timedelta(days=ahead)).date()
    return _date(words, now)


_NOT_ABOUT = {
    "мені", "мене", "нам", "нас", "мій", "моя", "моє", "мою", "мої", "моїй", "моєму", "мого", "моєї", "моїм", "моїх",
    "твій", "твоя", "твоє", "твою", "твої", "твоїй", "твоєму", "твого", "твоєї", "твоїм", "твоїх", "тобі", "тебе",
    "про", "що", "щоб", "аби", "і", "й", "та", "а", "нагадування", "нагадувань", "те", "це", "той", "для", "по", "за",
    "з", "до", "від",
}
_ENDINGS = sorted(["ами", "ями", "ого", "ього", "ому", "ьому", "ої", "ьої", "ою", "ею", "єю", "ий", "ій", "их", "іх",
                   "им", "ім", "ів", "їв", "ах", "ях", "ам", "ям", "ом", "ем", "єм", "а", "я", "у", "ю", "і", "ї",
                   "и", "е", "є", "о", "ь", "й"], key=len, reverse=True)


def _stem(word: str) -> str:
    """A word without its case's ending, to compare: "стоматолога" and
    "стоматологу" are "стоматолог"."""
    for ending in _ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            return word[: -len(ending)]
    return word


def about(text: str) -> list[str]:
    """What a reminder is about, as words to compare (their stems): "моє
    нагадування подзвонити мамі завтра" -> ["подзвонит", "мам"]."""
    words = re.findall(r"[\w']+", _joined(text).lower())
    return [_stem(w) for w in words if w not in _NOT_ABOUT and not _is_when_word(w)]


_WANTS = {
    *_DATE_WORDS, *_DAY_FORMS, *_EVERY_WORDS, "щодня", "щоранку", "щовечора", "щоночі", "щобудня", "щовихідних",
    "будні", "буднях", "будням", "вихідні", "вихідних", "вихідним", "ввечері", "увечері", "вранці", "зранку", "вночі",
}


def wants_time(text: str) -> bool:
    """Whether ``text`` names a day or a repeat but no time ("завтра",
    "щопонеділка"): asked what time."""
    return any(w in _WANTS for w in _tokens(_joined(text)))


_SWAPS = {
    "мені": "тобі", "мене": "тебе", "мною": "тобою", "я": "ти", "мій": "твій", "моя": "твоя", "моє": "твоє",
    "мою": "твою", "мої": "твої", "моїй": "твоїй", "моєму": "твоєму", "мого": "твого", "моєї": "твоєї", "моїм": "твоїм",
    "моїх": "твоїх", "моїми": "твоїми", "собі": "собі",
}


def what(text: str) -> str:
    """A reminder's text, as it is said back: "що мені треба до лікаря" ->
    "тобі треба до лікаря", "подзвонити моїй мамі" -> "подзвонити твоїй
    мамі"."""
    s = text.strip(" ,.?!").replace("’", "'").replace("ʼ", "'")
    s = re.sub(r"^(?:мені|нам)\b[\s,]*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^(?:що|щоб|аби|про)\b[\s,]*", "", s, flags=re.IGNORECASE)
    return " ".join(_SWAPS.get(w.lower(), w) for w in s.split())


# ---------------------------------------------------------------- speaking

EXAMPLES = {
    "alarm_time": "сьому тридцять завтра",
    "alarm": "сьому",
    "alarm_other": "восьму",
    "reminder": "подзвонити мамі",
    "reminder_timed": "о п'ятій вечора подзвонити мамі",
    "reminder_day": "подзвонити мамі завтра",
    "reminder_other": "погодувати кота",
    "reminder_nothing": "про",
    "call": "Подзвонити мамі",
    "bins": "Винести сміття",
}
"""What the web UI's examples of what alarms and reminders say are made
from (alarms.outcome_examples), as the slots hold them -- an alarm's after
its "на" ("постав будильник на сьому"), the command's cue: an alarm's time
(``alarm_time``: one set; ``alarm``: the 7 o'clock one cancelled;
``alarm_other``: one there is none at), a reminder (``reminder``: one there
is; ``reminder_timed``: one set with a time; ``reminder_day``: one cancelled
by its day; ``reminder_other``: one there is none of; ``reminder_nothing``:
what is said when what to be reminded of is missing), and two reminders'
titles on the calendar (``call``, the 5 pm one; ``bins``)."""

ALARM_WHEN = "На котру годину поставити будильник?"
REMINDER_WHEN = "Коли нагадати?"
REMINDER_WHAT = "Про що нагадати?"
NO_ALARMS = "Будильників немає."
NO_REMINDERS = "Нагадувань немає."
CALENDAR_NEEDED = "Для будильників і нагадувань потрібен локальний календар Home Assistant, а його не вдалося налаштувати."
ALARM_TITLE = "Будильник"
"""An alarm's event, on the calendar."""

_EVERY_SAID = ["щопонеділка", "щовівторка", "щосереди", "щочетверга", "щоп'ятниці", "щосуботи", "щонеділі"]


def said_when(start: datetime, rrule: str | None, now: datetime) -> str:
    """"о сьомій тридцять", "завтра о сьомій тридцять", "у п'ятницю о дев'ятій",
    "по буднях о сьомій", "тридцятого жовтня о дев'ятій"."""
    time = _at(start.hour, start.minute)
    if rrule:
        days = re.search(r"BYDAY=([A-Z0-9,+-]+)", rrule)
        if not days:
            return f"щодня {time}" if "DAILY" in rrule else f"щотижня {time}"
        codes = [c[-2:] for c in days.group(1).split(",") if c[-2:] in CODES]
        if codes == CODES[:5]:
            return f"по буднях {time}"
        if codes == CODES[5:]:
            return f"по вихідних {time}"
        return f"{join([_EVERY_SAID[CODES.index(c)] for c in codes]) or 'щотижня'} {time}"
    ahead = (start.date() - now.date()).days
    if ahead == 0:
        return time
    if ahead == 1:
        return f"завтра {time}"
    if ahead < 7:
        return f"у {_ON[start.weekday()]} {time}"
    return f"{ordinal(start.day, 'gen')} {MONTHS_OF[start.month - 1]} {time}"


def _from_now(start: datetime, now: datetime) -> str:
    """How long until then, after "через": "одну годину і п'ять хвилин"."""
    return duration(max(60, round((start - now).total_seconds() / 60) * 60), adjective=True)


def alarm_set(start: datetime, rrule: str | None, now: datetime) -> dict[str, str]:
    said = said_when(start, rrule, now)
    specific = f"Будильник дзвонитиме {said}." if rrule else f"Будильник задзвонить {said}."
    first = "найближчий через" if rrule else "це через"
    return {"brief": "Будильник поставлено.", "specific": specific,
            "verbose": f"{specific[:-1]}, {first} {_from_now(start, now)}."}


def reminder_set(what_said: str, start: datetime, rrule: str | None, now: datetime, relative: bool) -> dict[str, str]:
    at = f"через {_from_now(start, now)}" if relative else said_when(start, rrule, now)
    specific = f"Нагадаю {at}: {what_said}." if what_said else f"Нагадаю {at}."
    verbose = specific if relative else f"{specific} {'Найближче' if rrule else 'Це'} через {_from_now(start, now)}."
    return {"brief": "Нагадаю.", "specific": specific, "verbose": verbose}


def reminder_listed(what_said: str) -> str:
    """A reminder without a time, put on the to-do list."""
    return f"Додано до нагадувань: {what_said}."


def alarm_due(title: str, start: datetime) -> str:
    """What an alarm says when it rings: "Зараз сьома тридцять."; a named one
    first says its name."""
    said = f"Зараз {clock(start.hour, start.minute)}."
    named = title.strip()
    return said if named.lower() in ("", ALARM_TITLE.lower(), "alarm") else f"{_capital(named)}. {said}"


def reminder_due(text: str) -> str:
    return f"Нагадування: {text.strip().rstrip('.')}."


def _listed(events: list[dict[str, Any]], now: datetime) -> list[str]:
    return [said_when(e["start"], e.get("rrule"), now) for e in events]


def _alarms(count: int) -> str:
    """"два будильники", "п'ять будильників"."""
    return f"{cardinal(count)} {plural(count, 'будильник', 'будильники', 'будильників')}"


def _reminders(count: int) -> str:
    """"одне нагадування", "п'ять нагадувань"."""
    return f"{cardinal(count, 'n')} {plural(count, 'нагадування', 'нагадування', 'нагадувань')}"


def _texts(reminders: list[dict[str, Any]], now: datetime) -> list[str]:
    """Each reminder's text and when: "Подзвонити мамі о сімнадцятій"."""
    return [f"{r['text']} {when}" for r, when in zip(reminders, _listed(reminders, now), strict=True)]


def alarms_listed(alarms: list[dict[str, Any]], now: datetime) -> str:
    said = _listed(alarms, now)
    if len(said) == 1:
        return f"Є будильник {said[0]}."
    return f"Є {_alarms(len(said))}: {join(said)}."


def reminders_listed(reminders: list[dict[str, Any]], now: datetime) -> str:
    said = _texts(reminders, now)
    if len(said) == 1:
        return f"Є одне нагадування: {said[0]}."
    return f"Є {_reminders(len(said))}: {join(said)}."


def alarm_cancelled(alarms: list[dict[str, Any]], now: datetime) -> dict[str, str]:
    said = _listed(alarms, now)
    if len(said) == 1:
        specific = f"Скасовано будильник {said[0]}."
    else:
        specific = f"Скасовано {_alarms(len(said))}."
    return {"brief": "Будильник скасовано." if len(said) == 1 else "Будильники скасовано.", "specific": specific,
            "verbose": f"Скасовано будильники: {join(said)}." if len(said) > 1 else specific}


def which_alarm(alarms: list[dict[str, Any]], now: datetime) -> str:
    return f"Який будильник? Їх кілька: {join(_listed(alarms, now))}."


def which_alarm_asked(alarms: list[dict[str, Any]], now: datetime) -> str:
    """Several alarms fit, asked of a satellite that hears the answer."""
    return f"Будильник {join_or(_listed(alarms, now))}?"


def alarm_labels(alarms: list[dict[str, Any]], now: datetime) -> list[str]:
    """How each is told apart (an answer to which_alarm_asked)."""
    return [f"будильник {when}" for when in _listed(alarms, now)]


def alarm_not_found(asked: str, alarms: list[dict[str, Any]], now: datetime) -> str:
    return f"Немає будильника {asked}. {alarms_listed(alarms, now)}" if alarms else NO_ALARMS


def reminder_cancelled(reminders: list[dict[str, Any]], now: datetime) -> dict[str, str]:
    said = _texts(reminders, now)
    if len(said) == 1:
        specific = f"Скасовано нагадування {_listed(reminders, now)[0]}: {reminders[0]['text']}."
    else:
        specific = f"Скасовано {_reminders(len(said))}."
    return {"brief": "Нагадування скасовано.", "specific": specific,
            "verbose": f"Скасовано нагадування: {join(said)}." if len(said) > 1 else specific}


def which_reminder(reminders: list[dict[str, Any]], now: datetime) -> str:
    return f"Яке нагадування? Їх кілька: {join(_texts(reminders, now))}."


def which_reminder_asked(reminders: list[dict[str, Any]], now: datetime) -> str:
    """Several reminders fit, asked of a satellite that hears the answer."""
    return f"{_capital(join_or(reminder_labels(reminders, now)))}?"


def reminder_labels(reminders: list[dict[str, Any]], now: datetime) -> list[str]:
    """How each is told apart (an answer to which_reminder_asked)."""
    return _texts(reminders, now)


def reminder_not_found(reminders: list[dict[str, Any]], now: datetime) -> str:
    return f"Такого нагадування немає. {reminders_listed(reminders, now)}" if reminders else NO_REMINDERS
