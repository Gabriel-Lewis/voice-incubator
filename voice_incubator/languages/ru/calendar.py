"""Alarms and reminders on the calendar, in Russian, with English's names
(voice_incubator/languages/en/calendar.py): when one is for -- read from what
was said ("на семь тридцать", "завтра в 9", "по будням в 6:45", "через 20
минут", "в пять вечера в пятницу") -- and what the app says about them.

A clock time is said on either clock ("в семь тридцать", "в 19:30", "в семь
вечера") or by the hour it leads to ("в половине восьмого", "четверть
восьмого", "без четверти восемь": the pack's ``reading.clock``); "утра" and
"ночи" are before noon, "дня" and "вечера" after -- but "в одиннадцать ночи"
is 23:00. A day is "сегодня", "завтра", "послезавтра", a weekday in the
accusative ("в среду", "в следующую пятницу") or "через 3 дня"; a repeat is
"каждый день", "по будням", "по выходным", "каждый вторник", "по средам и
пятницам". Said back, a time of day is on a 24-hour clock ("на 7:30
завтра", "в 17:00 по вторникам"), and what to be reminded of is said as it
was ("позвонить маме"), "мой" as "ваш"."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from . import reading
from .numerals import cardinal, ordinal, plural
from .skills.numbers import fold, parse_num
from .speech import _capital, clock, duration, join, join_or

# ----------------------------------------------------------------- reading

DAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
CODES = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]

_ON_DAY = ["в понедельник", "во вторник", "в среду", "в четверг", "в пятницу", "в субботу", "в воскресенье"]
"""On that day (the accusative): "в 9:00 в пятницу"."""
_EVERY_DAY = ["понедельникам", "вторникам", "средам", "четвергам", "пятницам", "субботам", "воскресеньям"]
"""Every one of them, after "по": "по вторникам"."""
_MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
           "ноября", "декабря"]

_WEEKDAY = [
    re.compile(p)
    for p in (r"понедельник\w*", r"вторник\w*", r"сред[аыуеи]\w*", r"четверг\w*", r"пятниц\w*", r"суббот\w*",
              r"воскресень\w*")
]
"""Each weekday in any case: "среда", "в среду", "по средам"."""

_WHEN_WORDS = {
    "в", "во", "на", "к", "ко", "через", "по", "и", "этот", "эту", "следующий", "следующую",
    "следующее", "каждый", "каждую", "каждое", "каждые", "ежедневно", "сегодня", "завтра", "послезавтра",
    "утра", "утром", "утро", "дня", "днем", "день", "дни", "дней", "вечера", "вечером", "вечер", "ночи", "ночью",
    "ночь", "полдень", "полудня", "полночь", "полуночи", "час", "часа", "часов", "часам", "минут", "минуты",
    "минуту", "минута", "секунд", "секунды", "секунду", "полчаса", "четверть", "четверти", "половина",
    "половину", "половине", "половины", "без", "ровно", "будни", "будням", "будний", "будние", "будним",
    "рабочие", "рабочим", "рабочий", "выходные", "выходным", "выходной", "неделю", "недели", "недель",
    "первого", "второго", "третьего", "четвертого", "пятого", "шестого", "седьмого", "восьмого", "девятого",
    "десятого", "одиннадцатого", "двенадцатого",
}
_STARTS = {
    "в", "во", "на", "к", "ко", "через", "по", "каждый", "каждую", "каждое", "каждые", "ежедневно", "сегодня",
    "завтра", "послезавтра", "этот", "эту", "следующий", "следующую", "следующее",
}
"""Words a time said at the end of a reminder may start with (or a weekday)."""
_EDGE = {"и"}
"""Words at a time's edges that belong to what was said besides."""
_DAY_WORDS = {"завтрашн": "завтра", "послезавтрашн": "послезавтра", "сегодняшн": "сегодня"}
"""A day said as an adjective ("завтрашний будильник"), as the day."""


@dataclass
class When:
    """When an alarm or a reminder is: its first time (local), how it repeats
    (an RRULE, or None), and what was said besides (a reminder's text)."""

    start: datetime
    rrule: str | None = None
    rest: str = ""
    relative: bool = False
    """Said from now ("через 20 минут")."""
    said: str = ""
    """The words that said when."""


def _plain(word: str) -> str:
    """A word as compared: lowercase, "ё" as "е", without punctuation."""
    return fold(word).strip(",.!?;:«»\"")


def _weekday(word: str) -> int | None:
    """The weekday ``word`` (plain) names, in any case; None."""
    return next((i for i, p in enumerate(_WEEKDAY) if p.fullmatch(word)), None)


def _is_number(word: str) -> bool:
    if re.fullmatch(r"\d{1,2}(:\d{2})?", word):
        return True
    if re.fullmatch(r"пол\w+ого", word):  # "полвосьмого"
        return True
    try:
        return parse_num(word) is not None
    except (ValueError, StopIteration):
        return False


def _is_when_word(word: str) -> bool:
    w = _plain(word)
    return w in _WHEN_WORDS or _weekday(w) is not None or _is_number(w) or any(w.startswith(a) for a in _DAY_WORDS)


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
    # Not "и" at its edges: it belongs to what was said besides.
    while begin < end and _plain(words[begin]) in _EDGE:
        begin += 1
    while end > begin and _plain(words[end - 1]) in _EDGE:
        end -= 1
    return begin, end


def _joined(text: str) -> str:
    """The day speech-to-text splits: "после завтра"."""
    return re.sub(r"\bпосле\s+завтра", "послезавтра", text, flags=re.IGNORECASE)


def when(text: str, now: datetime, alarm: bool = False) -> When | None:
    """When ``text`` says: a time (and a day, or how it repeats), or a time
    from now; None when it says none. ``now`` is aware local time; an
    ``alarm`` said for another day without "утра" or "вечера" is in the
    morning."""
    words = _joined(text).split()
    best: tuple[When, int] | None = None
    for from_end in (False, True):
        begin, end = _run(words, from_end)
        found = None
        while begin < end:
            found = _read(" ".join(words[begin:end]), now, alarm)
            if found is not None:
                break
            # Not all of it is the time ("отдохнуть 10 минут в 5 вечера"):
            # less of it, from where it meets the rest, to a word a time
            # starts or ends with.
            if from_end:
                begin += 1
                while begin < end and not _starts(words[begin]):
                    begin += 1
            else:
                end -= 1
        if found is not None and (best is None or end - begin > best[1]):
            found.rest = " ".join(words[:begin] + words[end:]).strip(" ,")
            found.said = " ".join(words[begin:end])
            best = (found, end - begin)
    return best[0] if best else None


def _starts(word: str) -> bool:
    w = _plain(word)
    return w in _STARTS or _weekday(w) is not None


def _words(said: str) -> list[str]:
    """A time said, as words to read: lowercase, "ё" as "е", "7.30" as
    "7:30", without punctuation."""
    s = re.sub(r"(\d{1,2})[.:](\d{2})\b", r"\1:\2", fold(said))
    return re.sub(r"[,!?;«»\"]|\.(?!\d)", " ", s).split()


_UNIT = re.compile(r"(секунд[аыу]?)|(минут[аыу]?)|(час(?:а|ов)?)")
_LEADS = re.compile(r"(?:пол)?(?:первого|второго|третьего|четвертого|пятого|шестого|седьмого|восьмого|девятого"
                    r"|десятого|одиннадцатого|двенадцатого)")
"""The hour a time leads to: "десять минут восьмого", "полвосьмого"."""


def _length(words: list[str]) -> tuple[float | None, int, bool]:
    """A length said at the start of ``words`` -- "20 минут", "час и десять
    минут", "полтора часа", "полчаса", "четверть часа" -- as (seconds, the
    words it took, whether it has hours); (None, 0, False) when there is none."""
    total, index, taken, hours = 0.0, 0, 0, False
    amount: list[str] = []
    while index < len(words):
        word = words[index]
        if word == "полчаса":
            total, index, taken, amount = total + 1800, index + 1, index + 1, []
            continue
        if word == "и" and taken and not amount:  # "час и десять минут"
            index += 1
            continue
        unit = _UNIT.fullmatch(word)
        if unit:
            value = parse_num(" ".join(amount)) if amount else 1.0
            if value is None:
                break
            if words[index + 1 : index + 3] == ["с", "половиной"]:  # "час с половиной"
                value, index = value + 0.5, index + 2
            seconds = 1 if unit.group(1) else 60 if unit.group(2) else 3600
            hours = hours or seconds == 3600
            total, index, taken, amount = total + value * seconds, index + 1, index + 1, []
            continue
        if (_is_number(word) and ":" not in word) or (word in ("с", "половиной") and amount):
            amount.append(word)
            index += 1
            if len(amount) <= 4:
                continue
        break
    return (total, taken, hours) if taken and total else (None, 0, False)


def _has_length(words: list[str]) -> bool:
    """Whether ``words`` say a length besides a time of day -- "10 минут в 5
    вечера", "2 часа в 5 вечера" -- not as part of it: "десять минут
    восьмого", "без десяти минут восемь", "в 7 часов 30 минут", "в семь
    часов утра"."""
    numbers = [i for i, w in enumerate(words) if _is_number(w) and not _LEADS.fullmatch(w)]
    for index, word in enumerate(words):
        unit = _UNIT.fullmatch(word)
        if not unit or index == 0 or not _is_number(words[index - 1]):
            continue
        if unit.group(3):  # hours: a length when another number follows, but its minutes
            later = [i for i in numbers if i > index]
            if later and not (later[0] == index + 1 and len(later) == 1):
                return True
        elif not (
            (index + 1 < len(words) and _LEADS.fullmatch(words[index + 1]))
            or "без" in words[:index]
            or (index >= 2 and (_UNIT.fullmatch(words[index - 2]) or _Z.fullmatch(words[index - 2])))
        ):
            return True
    return False


_Z = re.compile(r"\d{1,2}|ноль|нуль")
"""Before a minute count, an hour said without its word: "в 7 ноль 5 минут"."""


def _read(said: str, now: datetime, alarm: bool) -> When | None:
    """A run of time words as a When; None when it isn't one (or names a day
    but no time: see ``wants_time``)."""
    words = _words(said)

    # Some days from now: "через 3 дня", "через неделю" -- a day, not a time.
    offset = None
    for index, word in enumerate(words):
        if word != "через":
            continue
        tail = words[index + 1 :]
        unit = next((i for i, w in enumerate(tail[:2]) if re.fullmatch(r"день|дня|дней|неделю|недели|недель", w)), None)
        if unit is None:
            continue
        count = parse_num(" ".join(tail[:unit])) if unit else 1.0
        if count:
            offset = int(count) * (7 if tail[unit].startswith("недел") else 1)
            words = words[:index] + tail[unit + 1 :]
            break

    # From now: "через 20 минут", "через час", "через полтора часа" -- or a
    # few minutes alone ("на 20 минут"); with nothing else said.
    if "через" in words:
        index = words.index("через")
        seconds, taken, _ = _length(words[index + 1 :])
        if seconds is None or words[:index] + words[index + 1 + taken :] or offset is not None:
            return None
        return When(now + timedelta(seconds=seconds), relative=True)
    bare = words[1:] if words[:1] == ["на"] else words
    seconds, taken, hours = _length(bare)
    if seconds is not None and taken == len(bare) and not hours and offset is None:
        return When(now + timedelta(seconds=seconds), relative=True)
    if seconds is not None and taken == len(bare) and not bare[0].isdigit() and not _is_number(bare[0]):
        return None  # "час", "полчаса": a length, not a time of day

    if _has_length(words):
        return None  # "отдохнуть 10 минут | в 5 вечера": the length is the reminder's

    s = " " + " ".join(words) + " "
    rule, days = None, None
    if re.search(r" (?:каждый день|ежедневно|каждое утро|каждый вечер|каждую ночь) ", s):
        rule = "FREQ=DAILY"
    elif re.search(r" (?:по будням|в будни|по будним дням|в будние дни|каждый будний день|по рабочим дням"
                   r"|в рабочие дни|каждый рабочий день) ", s):
        rule, days = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", [0, 1, 2, 3, 4]
    elif re.search(r" (?:по выходным|в выходные|каждые выходные|каждый выходной|по выходным дням) ", s):
        rule, days = "FREQ=WEEKLY;BYDAY=SA,SU", [5, 6]
    else:
        repeated = _repeated(words)
        if repeated:
            rule, days = "FREQ=WEEKLY;BYDAY=" + ",".join(CODES[i] for i in repeated), repeated

    date = _date(s, now) if rule is None else None
    if offset is not None and rule is None:
        date = (now + timedelta(days=offset)).date()

    # The time of day, without the words of the day: "в 7 утра в субботу".
    time = reading.clock(" ".join(w for w in words if _weekday(w) is None))
    if time is None:
        return None  # no time: a day alone is not enough
    hour, minute, meridiem = time
    if meridiem == "am" and 9 <= hour <= 11 and re.search(r" (?:ночи|ночью) ", s):
        meridiem = "pm"  # "в одиннадцать ночи": 23:00
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0

    def at(day: Any, h: int) -> datetime:
        return now.replace(year=day.year, month=day.month, day=day.day, hour=h % 24, minute=minute, second=0, microsecond=0)

    if meridiem is None and 1 <= hour <= 12:
        if date is None and rule is None:
            # The next time it comes round, before noon or after.
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
    if start <= now and date == now.date() and " сегодня " not in s:
        start += timedelta(days=7)  # "в среду" on a Wednesday, the time gone: next week's
    return When(start) if start > now else None


def _repeated(words: list[str]) -> list[int]:
    """The weekdays said as every one of them: "каждый вторник", "каждую
    среду и пятницу", "по средам", "по понедельникам и четвергам"."""
    found: list[int] = []
    every = False
    for word in words:
        day = _weekday(word)
        if word in ("каждый", "каждую", "каждое", "каждые"):
            every = True
        elif day is not None:
            if (every or word.endswith(("ам", "ям"))) and day not in found:
                found.append(day)
        elif word not in ("и", "по"):
            every = False
    return sorted(found)


def _date(s: str, now: datetime) -> Any:
    """The day ``s`` (lowercase, spaced at its ends) names, if it names one."""
    if " послезавтра " in s:
        return (now + timedelta(days=2)).date()
    if " завтра " in s:
        return (now + timedelta(days=1)).date()
    if " сегодня " in s:
        return now.date()
    words = s.split()
    for index, word in enumerate(words):
        day = _weekday(word)
        if day is not None:
            ahead = (day - now.weekday()) % 7
            following = index > 0 and words[index - 1].startswith("следующ")
            return (now + timedelta(days=ahead or (7 if following else 0))).date()
    found = re.search(r" через (?:(\S+) )?(день|дня|дней|неделю|недели|недель) ", s)
    if found:
        count = parse_num(found.group(1)) if found.group(1) else 1.0
        if count:
            return (now + timedelta(days=int(count) * (7 if found.group(2).startswith("недел") else 1))).date()
    return None


def _days_said(text: str) -> str:
    """``text`` as words, a day said as an adjective as the day itself:
    "завтрашний" -> "завтра"."""
    out = []
    for word in _words(_joined(text)):
        stem = next((a for a in sorted(_DAY_WORDS, key=len, reverse=True) if word.startswith(a)), None)
        out.append(_DAY_WORDS[stem] if stem else word)
    return " " + " ".join(out) + " "


def day(text: str, now: datetime) -> Any:
    """The day ``text`` names without a time ("на завтра", "завтрашний", "в
    пятницу"), or None."""
    return _date(_days_said(text), now)


_NOT_ABOUT = {
    "мой", "моя", "мое", "мои", "мою", "моей", "моем", "моего", "моему", "моих", "моим", "ваш", "ваша", "ваше",
    "ваши", "вашу", "вашей", "вашем", "вашего", "ваших", "напоминание", "напоминания", "напоминаний",
    "напоминанием", "про", "о", "об", "что", "чтобы", "насчет", "для", "мне", "меня", "вам", "вас", "это", "этот",
    "эту", "то", "тот", "с", "со",
}
_ENDINGS = sorted((
    "ться", "тись", "ами", "ями", "ого", "его", "ому", "ему", "ыми", "ими", "ать", "ять", "ить", "еть", "уть",
    "ешь", "ишь", "ах", "ях", "ов", "ев", "ей", "ой", "ий", "ый", "ая", "яя", "ое", "ее", "ые", "ие", "ую", "юю",
    "ом", "ем", "ам", "ям", "ых", "их", "ым", "им", "ть", "а", "я", "о", "е", "ы", "и", "у", "ю", "ь", "й",
), key=len, reverse=True)


def _stem(word: str) -> str:
    """A word without its ending, as words are compared: "маме" and "маму"
    are "мам", "позвонить" and "позвони" "позвон"."""
    for ending in _ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            return word[: -len(ending)]
    return word


def about(text: str) -> list[str]:
    """What a reminder is about, as words to compare (stems): "моё
    напоминание позвонить маме завтра" -> ["позвон", "мам"]."""
    words = [_plain(w) for w in re.findall(r"[\w-]+", _joined(text))]
    return [_stem(w) for w in words if w and w not in _NOT_ABOUT and not _is_when_word(w)]


def wants_time(text: str) -> bool:
    """Whether ``text`` names a day or a repeat but no time ("завтра",
    "каждый понедельник"): asked what time."""
    s = _days_said(text)
    words = s.split()
    return bool(re.search(r" (?:сегодня|завтра|послезавтра|каждый|каждую|каждое|каждые|ежедневно|будням|будни"
                          r"|выходным|выходные) ", s) or any(_weekday(w) is not None for w in words))


_SWAPS = {
    "мой": "ваш", "моя": "ваша", "мое": "ваше", "моё": "ваше", "мои": "ваши", "мою": "вашу", "моей": "вашей",
    "моего": "вашего", "моему": "вашему", "моим": "вашим", "моих": "ваших", "моем": "вашем", "моём": "вашем",
    "моими": "вашими", "мне": "вам", "меня": "вас", "мной": "вами", "мною": "вами",
}
"""Said back to the one who asked: "позвонить моей маме" -> "позвонить вашей маме"."""


def what(text: str) -> str:
    """A reminder's text, as it is said back: "позвонить моей маме" ->
    "позвонить вашей маме"; "что мне нужно к врачу" -> "вам нужно к врачу"."""
    s = text.strip(" ,.?!")
    s = re.sub(r"^(?:мне|нам)\b[\s,]*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^(?:о том,? что|что|чтобы)\b[\s,]*", "", s, flags=re.IGNORECASE)

    def swap(found: re.Match) -> str:
        word = found.group(0)
        said = _SWAPS.get(word.lower())
        if said is None:
            return word
        return _capital(said) if word[:1].isupper() else said

    return re.sub(r"\w+", swap, s)


# ---------------------------------------------------------------- speaking

EXAMPLES = {
    "alarm_time": "семь тридцать завтра",
    "alarm": "семь",
    "alarm_other": "восемь",
    "reminder": "позвонить маме",
    "reminder_timed": "в пять вечера позвонить маме",
    "reminder_day": "позвонить маме завтра",
    "reminder_other": "покормить кошку",
    "reminder_nothing": "что",
    "call": "Позвонить маме",
    "bins": "Вынести мусор",
}
"""What the web UI's examples of what alarms and reminders say are made
from (alarms.outcome_examples), as speech-to-text writes them -- the keys
English's (voice_incubator/languages/en/calendar.py) says."""

ALARM_WHEN = "На какое время поставить будильник?"
REMINDER_WHEN = "Когда напомнить?"
REMINDER_WHAT = "О чём напомнить?"
NO_ALARMS = "Будильников нет."
NO_REMINDERS = "Напоминаний нет."
CALENDAR_NEEDED = "Для будильников и напоминаний нужен локальный календарь Home Assistant, а его не удалось настроить."
ALARM_TITLE = "Будильник"
"""An alarm's event, on the calendar."""


def said_when(start: datetime, rrule: str | None, now: datetime) -> str:
    """"7:30", "7:30 завтра", "9:00 в пятницу", "7:00 по будням", "9:00
    тридцатого октября": after "на" (an alarm) or "в" (a reminder)."""
    time = clock(start.hour, start.minute)
    if rrule:
        days = re.search(r"BYDAY=([A-Z,]+)", rrule)
        if not days:
            return f"{time} каждый день"
        codes = days.group(1).split(",")
        if codes == CODES[:5]:
            return f"{time} по будням"
        if codes == CODES[5:]:
            return f"{time} по выходным"
        return f"{time} по {join([_EVERY_DAY[CODES.index(c)] for c in codes])}"
    ahead = (start.date() - now.date()).days
    if ahead == 0:
        return time
    if ahead == 1:
        return f"{time} завтра"
    if ahead < 7:
        return f"{time} {_ON_DAY[start.weekday()]}"
    return f"{time} {ordinal(start.day, 'n', 'gen')} {_MONTHS[start.month - 1]}"


def _from_now(start: datetime, now: datetime) -> str:
    """How long until then, after "через": "одну минуту", "2 часа и 5 минут"."""
    return duration(max(60, round((start - now).total_seconds() / 60) * 60), adjective=True)


def _count(n: int, gender: str) -> str:
    """A count before a noun of ``gender``, as Piper should read it: "одно"
    (напоминание), "21"."""
    if gender != "m" and n % 10 in (1, 2) and n % 100 not in (11, 12):
        return cardinal(n, gender)
    return str(n)


def alarm_set(start: datetime, rrule: str | None, now: datetime) -> dict[str, str]:
    specific = f"Будильник поставлен на {said_when(start, rrule, now)}."
    return {"brief": "Будильник поставлен.", "specific": specific,
            "verbose": f"{specific[:-1]}, через {_from_now(start, now)}."}


def _plainly(what_said: str) -> bool:
    """Whether what to be reminded of is said straight after "напомню": what
    to do ("позвонить маме") or what about ("про стоматолога")."""
    first = what_said.split()[0].lower() if what_said.split() else ""
    return first in ("про", "о", "об", "насчет", "насчёт") or bool(re.search(r"(?:ть|ти|чь|ться|тись)$", first))


def reminder_set(what_said: str, start: datetime, rrule: str | None, now: datetime, relative: bool) -> dict[str, str]:
    at = f"через {_from_now(start, now)}" if relative else f"в {said_when(start, rrule, now)}"
    soon = "" if relative else f", через {_from_now(start, now)}"
    if not what_said:
        specific, verbose = f"Напомню {at}.", f"Напомню {at}{soon}."
    elif _plainly(what_said):
        specific, verbose = f"Напомню {what_said} {at}.", f"Напомню {what_said} {at}{soon}."
    else:
        specific, verbose = f"Напомню {at}: {what_said}.", f"Напомню {at}{soon}: {what_said}."
    return {"brief": "Хорошо, напомню.", "specific": specific, "verbose": verbose}


def reminder_listed(what_said: str) -> str:
    """A reminder without a time, put on the to-do list."""
    return f"Добавлено в напоминания: {what_said}."


def alarm_due(title: str, start: datetime) -> str:
    """What an alarm says when it rings: "Сейчас 7:30."; a named one first
    says its name."""
    said = f"Сейчас {clock(start.hour, start.minute)}."
    named = title.strip().lower() in ("", ALARM_TITLE.lower(), "alarm")
    return said if named else f"{_capital(title.strip())}. {said}"


def reminder_due(text: str) -> str:
    return f"Напоминание: {text.strip().rstrip('.')}."


def _listed(events: list[dict[str, Any]], now: datetime) -> list[str]:
    return [said_when(e["start"], e.get("rrule"), now) for e in events]


def alarms_listed(alarms: list[dict[str, Any]], now: datetime) -> str:
    said = _listed(alarms, now)
    if len(said) == 1:
        return f"У вас будильник на {said[0]}."
    n = len(said)
    return f"У вас {n} {plural(n, 'будильник', 'будильника', 'будильников')}: {join([f'на {s}' for s in said])}."


def _reminders(reminders: list[dict[str, Any]], now: datetime) -> list[str]:
    """Each, by what it is and when: "Позвонить маме в 17:00"."""
    return [f"{r['text']} в {when}" for r, when in zip(reminders, _listed(reminders, now), strict=True)]


def reminders_listed(reminders: list[dict[str, Any]], now: datetime) -> str:
    said = _reminders(reminders, now)
    if len(said) == 1:
        return f"У вас одно напоминание: {said[0]}."
    n = len(said)
    return f"У вас {_count(n, 'n')} {plural(n, 'напоминание', 'напоминания', 'напоминаний')}: {join(said)}."


def alarm_cancelled(alarms: list[dict[str, Any]], now: datetime) -> dict[str, str]:
    said = _listed(alarms, now)
    n = len(said)
    if n == 1:
        specific = f"Будильник на {said[0]} отменён."
    else:
        specific = f"{plural(n, 'Отменён', 'Отменены', 'Отменено')} {n} {plural(n, 'будильник', 'будильника', 'будильников')}."
    return {"brief": "Будильник отменён." if n == 1 else "Будильники отменены.", "specific": specific,
            "verbose": f"Отменены будильники {join([f'на {s}' for s in said])}." if n > 1 else specific}


def which_alarm(alarms: list[dict[str, Any]], now: datetime) -> str:
    return f"Какой будильник? Есть будильники {join([f'на {s}' for s in _listed(alarms, now)])}."


def which_alarm_asked(alarms: list[dict[str, Any]], now: datetime) -> str:
    """Several alarms fit, asked of a satellite that hears the answer."""
    return f"Будильник {join_or([f'на {s}' for s in _listed(alarms, now)])}?"


def alarm_labels(alarms: list[dict[str, Any]], now: datetime) -> list[str]:
    """How each is told apart (an answer to which_alarm_asked)."""
    return [f"будильник на {s}" for s in _listed(alarms, now)]


def alarm_not_found(asked: str, alarms: list[dict[str, Any]], now: datetime) -> str:
    asked = re.sub(r"^(?:на|в|во)\s+", "", asked.strip(), flags=re.IGNORECASE)
    return f"Будильника на {asked} нет. {alarms_listed(alarms, now)}" if alarms else NO_ALARMS


def reminder_cancelled(reminders: list[dict[str, Any]], now: datetime) -> dict[str, str]:
    said = _reminders(reminders, now)
    n = len(said)
    if n == 1:
        specific = f"Отменено напоминание в {_listed(reminders, now)[0]}: {reminders[0]['text']}."
    else:
        specific = f"{plural(n, 'Отменено', 'Отменены', 'Отменено')} {_count(n, 'n')} {plural(n, 'напоминание', 'напоминания', 'напоминаний')}."
    return {"brief": "Напоминание отменено." if n == 1 else "Напоминания отменены.", "specific": specific,
            "verbose": f"Отменены напоминания: {join(said)}." if n > 1 else specific}


def which_reminder(reminders: list[dict[str, Any]], now: datetime) -> str:
    return f"Какое напоминание? Есть такие: {join(_reminders(reminders, now))}."


def which_reminder_asked(reminders: list[dict[str, Any]], now: datetime) -> str:
    """Several reminders fit, asked of a satellite that hears the answer."""
    return f"{_capital(join_or(reminder_labels(reminders, now)))}?"


def reminder_labels(reminders: list[dict[str, Any]], now: datetime) -> list[str]:
    """How each is told apart (an answer to which_reminder_asked)."""
    return _reminders(reminders, now)


def reminder_not_found(reminders: list[dict[str, Any]], now: datetime) -> str:
    return f"Такого напоминания нет. {reminders_listed(reminders, now)}" if reminders else NO_REMINDERS
