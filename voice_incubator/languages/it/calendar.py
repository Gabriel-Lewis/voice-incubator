"""Alarms and reminders on the calendar, in Italian, with English's names
(voice_incubator/languages/en/calendar.py): when one is for -- read from what
was said ("le sette e mezza di domani", "ogni giorno feriale alle 6", "tra 20
minuti", "venerdì alle 17") -- and what the app says about them.

Italian says a time with its article ("le sette", "l'una"), joined to its
preposition ("alle sette", "all'una", "dalle sette"), and on a 24-hour clock
as often as with "di mattina", "del pomeriggio", "di sera" (the pack's
reading.clock reads it). A weekday with its article is every one of them
("il martedì alle 19"), as "ogni martedì" is; without, the next ("martedì
alle 19"). From now is "tra" or "fra" ("tra 10 minuti"); "per 10 minuti" is
a length, never when."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from . import reading
from .skills.clock import minutes
from .skills.numbers import fold, parse_num
from .speech import _capital, clock, duration, join, join_or

# ----------------------------------------------------------------- reading

DAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
CODES = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
          "novembre", "dicembre"]

_FOLDED_DAYS = [fold(d) for d in DAYS]
_PLURAL_DAYS = {"sabati": 5, "domeniche": 6}
"""Weekdays said in the plural ("tutti i sabati"); the others are the same."""
_DAY_FORMS = {d: i for i, d in enumerate(_FOLDED_DAYS)} | _PLURAL_DAYS
_DAY = rf"(?:{'|'.join(sorted(_DAY_FORMS, key=len, reverse=True))})"

_NUMBER_WORDS = {
    "zero", "uno", "una", "un", "un'", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove", "dieci",
    "undici", "dodici", "tredici", "quattordici", "quindici", "sedici", "diciassette", "diciotto", "diciannove",
    "venti", "trenta", "quaranta", "cinquanta", "mezza", "mezzo", "quarto", "quarti",
}
_WHEN_WORDS = {
    "alle", "all'", "alla", "al", "a", "le", "la", "l'", "il", "i", "per", "di", "del", "della", "dei", "delle", "dell'",
    "da", "dal", "dalle", "entro", "verso", "tra", "fra", "e", "meno", "in", "punto", "nel", "nei", "ogni", "tutti",
    "tutte", "giorno", "giorni", "settimana", "settimane", "questo", "questa", "prossimo", "prossima", "oggi", "domani",
    "dopodomani", "dopo", "domattina", "stasera", "stanotte", "stamattina", "stamani", "mattina", "mattino",
    "mattine", "pomeriggio", "pomeriggi", "sera", "sere", "notte", "notti", "mezzogiorno", "mezzanotte", "ore", "ora",
    "minuti", "minuto", "secondi", "secondo", "feriale", "feriali", "lavorativo", "lavorativi", "fine", "weekend",
    "quotidianamente", "un'ora", "mezz'ora", "d'ora", "l'una", "all'una", "dell'una", "dall'una",
    *_DAY_FORMS, *_NUMBER_WORDS,
}
_STARTS = {
    "alle", "all'una", "a", "al", "per", "entro", "verso", "tra", "fra", "oggi", "domani", "dopodomani", "domattina",
    "stasera", "stanotte", "stamattina", "stamani", "ogni", "tutti", "tutte", "il", "la", "le", "l'una", "questo",
    "questa", "prossimo", "prossima", "mezzogiorno", "mezzanotte", "dal", "dalle", *_DAY_FORMS,
}
"""Words a time said at the end of a reminder may start with."""

_LENGTH_UNITS = ("minuto", "minuti", "secondo", "secondi")
_UNIT_WORDS = {*_LENGTH_UNITS, "ora", "ore", "giorno", "giorni", "settimana", "settimane"}


def _has_length(s: str) -> bool:
    """Whether ``s`` (normal) says a length of time ("10 minuti", "un'ora",
    "ventiquattro ore"): not "alle ore 17"."""
    words = s.split()
    for index, word in enumerate(words):
        if word in _LENGTH_UNITS or re.fullmatch(r"(?:un|mezz|d)'or[ae]", word):
            return True
        if word in ("ora", "ore") and index and (words[index - 1] in ("un", "una", "uno") or words[index - 1].isdigit()
                                                 or _is_number(words[index - 1])):
            return True
    return False


@dataclass
class When:
    """When an alarm or a reminder is: its first time (local), how it repeats
    (an RRULE, or None), and what was said besides (a reminder's text)."""

    start: datetime
    rrule: str | None = None
    rest: str = ""
    relative: bool = False
    """Said from now ("tra 20 minuti")."""
    said: str = ""
    """The words that said when."""


def _word(word: str) -> str:
    return fold(word.lower().replace("’", "'").strip(",.!?;"))


def _is_when_word(word: str) -> bool:
    w = _word(word)
    return w in _WHEN_WORDS or bool(re.fullmatch(r"\d{1,2}(?:[:.]\d{2})?", w)) or _is_number(w)


def _is_number(word: str) -> bool:
    """A number word to 59 ("ventitré", "quarantacinque")."""
    if word in _NUMBER_WORDS:
        return True
    value = parse_num(word) if re.fullmatch(r"[a-z]+", word) else None
    return value is not None and value == int(value) and 0 <= value < 60


def _run(words: list[str], from_end: bool) -> tuple[int, int]:
    """The longest run of time words at the start or the end: (begin, end)."""
    n = len(words)
    if from_end:
        begin = n
        while begin > 0 and _is_when_word(words[begin - 1]):
            begin -= 1
        end = n
    else:
        # After "che", which stays the reminder's: "che venerdì alle 3 arriva
        # l'idraulico".
        begin = 1 if n > 1 and _word(words[0]) == "che" else 0
        end = begin
        while end < n and _is_when_word(words[end]):
            end += 1
    # Not "e" at its start: it joins what was said besides.
    while begin < end and _word(words[begin]) in ("e", "ed"):
        begin += 1
    return begin, end


def _joined(text: str) -> str:
    """What speech-to-text splits: "dopo domani", "un' ora", "mezz' ora"."""
    text = text.replace("’", "'")
    text = re.sub(r"\bdopo\s+domani\b", "dopodomani", text, flags=re.IGNORECASE)
    return re.sub(r"\b(un|mezz|d)'\s+(or[ae])\b", r"\1'\2", text, flags=re.IGNORECASE)


def when(text: str, now: datetime, alarm: bool = False) -> When | None:
    """When ``text`` says: a time (and a day, or how it repeats), or a time
    from now; None when it says none. ``now`` is aware local time; an
    ``alarm`` said for another day without di mattina or di sera is in the
    morning."""
    words = _joined(text).split()
    best: tuple[When, int] | None = None
    for from_end in (False, True):
        begin, end = _run(words, from_end)
        found = None
        while begin < end:
            # Not a number whose unit is left out ("per dieci | minuti").
            cut = end < len(words) and _word(words[end]) in _UNIT_WORDS
            found = None if cut else _read(" ".join(words[begin:end]), now, alarm)
            if found is not None:
                break
            # Not all of it is the time ("di riposare per 10 minuti alle 17"):
            # less of it, from where it meets the rest, to a word a time
            # starts or ends with.
            if from_end:
                begin += 1
                while begin < end and _word(words[begin]) not in _STARTS:
                    begin += 1
            else:
                end -= 1
        if found is not None and (best is None or end - begin > best[1]):
            found.rest = " ".join(words[:begin] + words[end:]).strip(" ,")
            found.said = " ".join(words[begin:end])
            best = (found, end - begin)
    return best[0] if best else None


def _normal(said: str) -> str:
    """Lowercase, without accents or punctuation, spaced at its ends: "Alle
    19.30, domani" -> " alle 19:30 domani "."""
    s = fold(_joined(said).lower())
    s = re.sub(r"(\d{1,2})\.(\d{2})\b", r"\1:\2", s)
    s = re.sub(r"[,.!?;]", " ", s)
    s = re.sub(r"\b(?:a|da|de)ll'(?=una\b)", "l'", s)
    return " " + " ".join(s.split()) + " "


def _read(said: str, now: datetime, alarm: bool) -> When | None:
    """A run of time words as a When; None when it isn't one (or names a day
    but no time: see ``wants_time``)."""
    s = _normal(said)

    # From now: "tra 20 minuti", "fra un'ora e mezza", "tra mezz'ora" -- or a
    # length alone: speech-to-text, or the free text's edge, can drop the
    # "tra". A length with anything else ("per 10 minuti alle 17") is none.
    if _has_length(s):
        body = re.sub(r"^ (?:tra|fra|entro|di qui a) ", " ", s).strip()
        seconds = re.fullmatch(r"(\S+) second[oi]", body)
        amount = (parse_num(seconds.group(1)) or 0) / 60 if seconds else minutes(body)
        if not amount:
            return None
        return When(now + timedelta(minutes=float(amount)), relative=True)

    rule, days = _rule(s)
    date = _date(s, now) if rule is None else None

    # The time, without what counts days ("tra 3 giorni") or the article of a
    # repeated day ("il lunedì"): no day alone.
    timed = re.sub(r" (?:tra|fra) \S+ (?:giorn[oi]|settiman[ae]) ", " ", s)
    vague = {"un", "un'", "una", "uno", "mezza", "mezzo", "quarto", "quarti"}
    if not re.search(r"\d|mezzogiorno|mezzanotte|\bl'una\b", timed) and not any(
        _is_number(w) for w in timed.split() if w not in vague
    ):
        return None
    time = reading.clock(timed)
    if time is None:
        return None
    hour, minute, meridiem = time
    if re.search(r" (?:mattina|mattino|mattine|stamattina|stamani|domattina) ", s):
        meridiem = "am"
    elif re.search(r" (?:pomeriggio|pomeriggi|sera|sere|stasera) ", s):
        meridiem = "pm"
    elif re.search(r" (?:notte|notti|stanotte) ", s) and hour != 12:
        meridiem = "pm" if hour >= 7 else "am"
        if " stanotte " in s and hour < 7 and rule is None:
            date = (now + timedelta(days=1)).date()  # "stanotte alle 3": the night to come
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0

    def at(day: Any, h: int) -> datetime:
        return now.replace(year=day.year, month=day.month, day=day.day, hour=h % 24, minute=minute, second=0, microsecond=0)

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
    if start <= now and date == now.date() and not re.search(r" (?:oggi|stasera|stanotte|stamattina|stamani) ", s):
        start += timedelta(days=7)  # "lunedì" on a Monday, the time gone: next week's
    return When(start) if start > now else None


_ARTICLE = r"(?:ogni|tutti i|tutte le|(?<!per )il|(?<!per )la|i|le)"
"""Before a weekday, every one of them: "ogni lunedì", "il lunedì", "tutti i
sabati", "le domeniche"; not "per il lunedì" (that one)."""


def _rule(s: str) -> tuple[str | None, list[int] | None]:
    """How ``s`` (normal) repeats: an RRULE and its weekdays, or None."""
    if re.search(
        r" (?:ogni giorno (?:feriale|lavorativo|della settimana)|(?:nei |i )?giorni (?:feriali|lavorativi)"
        r"|dal lunedi al venerdi|durante la settimana) ", s
    ):
        return "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", [0, 1, 2, 3, 4]
    if re.search(r" (?:ogni|tutti i|nei|il) (?:fine settimana|weekend) ", s):
        return "FREQ=WEEKLY;BYDAY=SA,SU", [5, 6]
    if re.search(
        r" (?:ogni giorno|tutti i giorni|ogni mattina|ogni sera|ogni notte|tutte le mattine|tutte le sere"
        r"|tutte le notti|quotidianamente) ", s
    ):
        return "FREQ=DAILY", None
    repeated = sorted({
        i for form, i in _DAY_FORMS.items()
        if re.search(rf" {_ARTICLE} (?:{_DAY} e (?:il |la |i |le )?)*{form} ", s)
    })
    if repeated:
        return "FREQ=WEEKLY;BYDAY=" + ",".join(CODES[i] for i in repeated), repeated
    return None, None


def _date(s: str, now: datetime) -> Any:
    """The day ``s`` (normal) names, if it names one."""
    if " dopodomani " in s:
        return (now + timedelta(days=2)).date()
    if re.search(r" (?:domani|domattina) ", s):
        return (now + timedelta(days=1)).date()
    if re.search(r" (?:oggi|stasera|stanotte|stamattina|stamani) ", s):
        return now.date()
    date = None
    found = re.search(rf" ({_DAY})(?= )", s)
    if found:
        index = _DAY_FORMS[found.group(1)]
        ahead = (index - now.weekday()) % 7
        nxt = re.search(rf" (?:il |la )?prossim[oa] {found.group(1)} | {found.group(1)} prossim[oa] ", s)
        date = (now + timedelta(days=ahead or (7 if nxt else 0))).date()
    found = re.search(r" (?:tra|fra) (\S+) (giorn[oi]|settiman[ae]) ", s)
    if found and parse_num(found.group(1)):
        count = int(parse_num(found.group(1)))
        date = (now + timedelta(days=count * (7 if found.group(2).startswith("settiman") else 1))).date()
    return date


def day(text: str, now: datetime) -> Any:
    """The day ``text`` names without a time ("di domani", "di venerdì"), or None."""
    return _date(_normal(text), now)


_NOT_ABOUT = {
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di", "del", "della", "dello", "dei", "degli", "delle",
    "a", "al", "alla", "allo", "ai", "agli", "alle", "da", "dal", "dalla", "in", "nel", "nella", "su", "sul",
    "sulla", "per", "con", "che", "e", "mi", "ti", "me", "te", "mio", "mia", "miei", "mie", "tuo", "tua", "tuoi",
    "tue", "promemoria", "quello", "quella", "riguardo",
}


def about(text: str) -> list[str]:
    """What a reminder is about, as words to compare: "il mio promemoria di
    chiamare la mamma domani" -> ["chiamare", "mamma"]."""
    words = [re.sub(r"^\w+'", "", w) for w in re.findall(r"[\w']+", fold(_joined(text).lower()))]
    return [w for w in words if w and w not in _NOT_ABOUT and not _is_when_word(w)]


def wants_time(text: str) -> bool:
    """Whether ``text`` names a day or a repeat but no time ("domani", "ogni
    lunedì"): asked what time."""
    s = _normal(text)
    return bool(re.search(
        rf" (?:domani|domattina|dopodomani|oggi|stasera|stanotte|stamattina|stamani|ogni|tutti i giorni|feriali"
        rf"|fine settimana|weekend|{_DAY}) ", s,
    ))


_SWAPS = {"mio": "tuo", "mia": "tua", "miei": "tuoi", "mie": "tue", "mi": "ti", "me": "te", "io": "tu"}


def what(text: str) -> str:
    """A reminder's text, as it is said back: "di chiamare mia mamma" ->
    "chiamare tua mamma"."""
    s = text.strip(" ,.?!").replace("’", "'")
    s = re.sub(r"^(?:di|che|per|riguardo a|riguardo al|riguardo alla|a proposito di)\b\s*|^d'", "", s, flags=re.IGNORECASE)
    return " ".join(_SWAPS.get(w.lower(), w) for w in s.split())


def _told(what_said: str) -> str:
    """What to remind of, after "ti ricorderò": "di" before a verb ("di
    chiamare tua mamma"), "che" before a clause ("che arriva l'idraulico")."""
    first = fold(what_said.split()[0].lower()) if what_said.split() else ""
    verb = re.search(r"(?:are|ere|ire|rre)(?:mi|ti|si|ci|vi|lo|la|li|le|ne|gli|glielo|gliela)?$", first)
    return f"di {what_said}" if verb else f"che {what_said}"


# ---------------------------------------------------------------- speaking

EXAMPLES = {
    "alarm_time": "sette e mezza di domani",
    "alarm": "sette",
    "alarm_other": "otto",
    "reminder": "di chiamare la mamma",
    "reminder_timed": "alle 17 di chiamare la mamma",
    "reminder_day": "di chiamare la mamma domani",
    "reminder_other": "di dare da mangiare al gatto",
    "reminder_nothing": "di",
    "call": "Chiamare la mamma",
    "bins": "Portare fuori la spazzatura",
}
"""What the web UI's examples of what alarms and reminders say are made
from (alarms.outcome_examples), as speech-to-text writes them: an alarm's
time (``alarm_time``: one set; ``alarm``: the 7 o'clock one cancelled;
``alarm_other``: one there is none at), a reminder (``reminder``: one there
is; ``reminder_timed``: one set with a time; ``reminder_day``: one cancelled
by its day; ``reminder_other``: one there is none of; ``reminder_nothing``:
what is said when what to be reminded of is missing), and two reminders'
titles on the calendar (``call``, the 5 pm one; ``bins``)."""

ALARM_WHEN = "Per che ora devo mettere la sveglia?"
REMINDER_WHEN = "Quando te lo devo ricordare?"
REMINDER_WHAT = "Cosa ti devo ricordare?"
NO_ALARMS = "Non ci sono sveglie."
NO_REMINDERS = "Non hai promemoria."
CALENDAR_NEEDED = ("Le sveglie e i promemoria hanno bisogno del calendario locale di Home Assistant, e non sono "
                   "riuscito a configurarlo.")
ALARM_TITLE = "Sveglia"
"""An alarm's event, on the calendar."""


def said_when(start: datetime, rrule: str | None, now: datetime) -> str:
    """"le 7 e 30", "le 7 e 30 di domani", "le 9 di venerdì", "le 7 nei
    giorni feriali", "le 9 del 30 ottobre" -- with its article, as
    ``_alle`` and ``_delle`` join it to a preposition."""
    time = clock(start.hour, start.minute)
    if rrule:
        days = re.search(r"BYDAY=([A-Z,]+)", rrule)
        if not days:
            return f"{time} ogni giorno"
        codes = days.group(1).split(",")
        if codes == CODES[:5]:
            return f"{time} nei giorni feriali"
        if codes == CODES[5:]:
            return f"{time} nel fine settimana"
        return f"{time} ogni {join([DAYS[CODES.index(c)] for c in codes])}"
    ahead = (start.date() - now.date()).days
    if ahead == 0:
        return time
    if ahead == 1:
        return f"{time} di domani"
    if ahead < 7:
        return f"{time} di {DAYS[start.weekday()]}"
    of = "dell'" if start.day in (8, 11) else "del "
    return f"{time} {of}{'primo' if start.day == 1 else start.day} {MONTHS[start.month - 1]}"


def _alle(said: str) -> str:
    """At a time: "alle 7", "all'una", "a mezzogiorno"; one said otherwise
    ("di domani") as it is."""
    if said.startswith(("le ", "l'")):
        return "al" + said
    if said.startswith(("mezzogiorno", "mezzanotte")):
        return "a " + said
    if re.match(r"\d", said):
        return "alle " + said
    return said


def _delle(said: str) -> str:
    """Of a time: "delle 7", "dell'una", "di mezzogiorno"."""
    if said.startswith(("le ", "l'")):
        return "del" + said
    if said.startswith(("mezzogiorno", "mezzanotte")):
        return "di " + said
    return said


def _from_now(start: datetime, now: datetime) -> str:
    return duration(max(60, round((start - now).total_seconds() / 60) * 60))


def alarm_set(start: datetime, rrule: str | None, now: datetime) -> dict[str, str]:
    specific = f"Sveglia impostata per {said_when(start, rrule, now)}."
    return {"brief": "Sveglia impostata.", "specific": specific,
            "verbose": f"{specific[:-1]}, tra {_from_now(start, now)}."}


def reminder_set(what_said: str, start: datetime, rrule: str | None, now: datetime, relative: bool) -> dict[str, str]:
    at = f"tra {_from_now(start, now)}" if relative else _alle(said_when(start, rrule, now))
    specific = f"Ti ricorderò {_told(what_said)} {at}." if what_said else f"Te lo ricorderò {at}."
    verbose = specific if relative else f"{specific[:-1]}, tra {_from_now(start, now)}."
    return {"brief": "Te lo ricorderò.", "specific": specific, "verbose": verbose}


def reminder_listed(what_said: str) -> str:
    """A reminder without a time, put on the to-do list."""
    return f"Ho aggiunto {what_said} ai tuoi promemoria."


def alarm_due(title: str, start: datetime) -> str:
    """What an alarm says when it rings: "Sono le 7 e 30."; a named one first
    says its name."""
    time = clock(start.hour, start.minute)
    said = f"Sono {time}." if time.startswith("le ") else f"È {time}."
    return said if title.strip().lower() in ("", ALARM_TITLE.lower()) else f"{_capital(title.strip())}. {said}"


def reminder_due(text: str) -> str:
    return f"Promemoria: {text.strip().rstrip('.')}."


def _listed(events: list[dict[str, Any]], now: datetime) -> list[str]:
    return [said_when(e["start"], e.get("rrule"), now) for e in events]


def alarms_listed(alarms: list[dict[str, Any]], now: datetime) -> str:
    said = _listed(alarms, now)
    if len(said) == 1:
        return f"Hai una sveglia {_alle(said[0])}."
    return f"Hai {len(said)} sveglie: {join([_alle(s) for s in said])}."


def reminders_listed(reminders: list[dict[str, Any]], now: datetime) -> str:
    said = [f"{r['text']} {_alle(s)}" for r, s in zip(reminders, _listed(reminders, now), strict=True)]
    if len(said) == 1:
        return f"Hai un promemoria: {said[0]}."
    return f"Hai {len(said)} promemoria: {join(said)}."


def alarm_cancelled(alarms: list[dict[str, Any]], now: datetime) -> dict[str, str]:
    said = _listed(alarms, now)
    if len(said) == 1:
        specific = f"Ho annullato la sveglia {_delle(said[0])}."
    else:
        specific = f"Ho annullato {len(said)} sveglie."
    return {"brief": "Sveglia annullata." if len(said) == 1 else "Sveglie annullate.", "specific": specific,
            "verbose": f"Ho annullato le sveglie {join([_delle(s) for s in said])}." if len(said) > 1 else specific}


def which_alarm(alarms: list[dict[str, Any]], now: datetime) -> str:
    return f"Quale sveglia? Hai {join([f'quella {_delle(s)}' for s in _listed(alarms, now)])}."


def which_alarm_asked(alarms: list[dict[str, Any]], now: datetime) -> str:
    """Several alarms fit, asked of a satellite that hears the answer."""
    return f"{_capital(join_or([f'quella {_delle(s)}' for s in _listed(alarms, now)]))}?"


def alarm_labels(alarms: list[dict[str, Any]], now: datetime) -> list[str]:
    """How each is told apart (an answer to which_alarm_asked)."""
    return [f"la sveglia {_delle(s)}" for s in _listed(alarms, now)]


def alarm_not_found(asked: str, alarms: list[dict[str, Any]], now: datetime) -> str:
    return f"Non c'è nessuna sveglia {_alle(asked)}. {alarms_listed(alarms, now)}" if alarms else NO_ALARMS


def reminder_cancelled(reminders: list[dict[str, Any]], now: datetime) -> dict[str, str]:
    said = [f"{r['text']} {_alle(when)}" for r, when in zip(reminders, _listed(reminders, now), strict=True)]
    if len(said) == 1:
        specific = f"Ho annullato il promemoria {_delle(_listed(reminders, now)[0])}: {reminders[0]['text']}."
    else:
        specific = f"Ho annullato {len(said)} promemoria."
    return {"brief": "Promemoria annullato." if len(said) == 1 else "Promemoria annullati.", "specific": specific,
            "verbose": f"Ho annullato i promemoria: {join(said)}." if len(said) > 1 else specific}


def which_reminder(reminders: list[dict[str, Any]], now: datetime) -> str:
    return f"Quale promemoria? Hai {join(reminder_labels(reminders, now))}."


def which_reminder_asked(reminders: list[dict[str, Any]], now: datetime) -> str:
    """Several reminders fit, asked of a satellite that hears the answer."""
    return f"{_capital(join_or(reminder_labels(reminders, now)))}?"


def reminder_labels(reminders: list[dict[str, Any]], now: datetime) -> list[str]:
    """How each is told apart (an answer to which_reminder_asked)."""
    return [f"{r['text']} {_alle(when)}" for r, when in zip(reminders, _listed(reminders, now), strict=True)]


def reminder_not_found(reminders: list[dict[str, Any]], now: datetime) -> str:
    return f"Non c'è nessun promemoria così. {reminders_listed(reminders, now)}" if reminders else NO_REMINDERS
