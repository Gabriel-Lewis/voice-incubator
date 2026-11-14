"""Alarms and reminders on the calendar, in French, with English's names
(voice_incubator/languages/en/calendar.py): when one is for -- read from what
was said ("sept heures et demie demain", "tous les jours de la semaine à 6
heures", "dans 20 minutes", "à 17 heures vendredi") -- and what the app says
about them (voice_incubator/alarms.py).

French says a clock time with "heures" ("sept heures et demie", "huit heures
moins le quart", "dix-neuf heures trente", "19 h 30"), the part of the day
after it ("du matin", "de l'après-midi", "du soir"), and noon and midnight
by name. "Dans" says it is from now ("dans deux heures"); "à" a clock time.
Both are filler at the edge of free text, which the app trims: a length in
minutes alone is from now ("vingt minutes"), one in hours a clock time
("huit heures")."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from . import reading
from .skills.numbers import parse_num
from .speech import _capital, clock, duration, join, join_or

# ----------------------------------------------------------------- reading

DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
CODES = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
          "novembre", "décembre"]
_DAY = rf"(?:{'|'.join(DAYS)})"

_NUMBER_WORDS = {
    "zéro", "un", "une", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze",
    "treize", "quatorze", "quinze", "seize", "vingt", "trente", "quarante", "cinquante", "soixante", "demi", "demie",
    "quart", "quarts",
}
_WHEN_WORDS = {
    "à", "pour", "vers", "dans", "le", "la", "les", "de", "du", "des", "et", "ce", "cet", "cette", "chaque", "tous",
    "toutes", "prochain", "prochaine", "en", "au", "h", "heure", "heures", "minute", "minutes", "midi", "minuit",
    "moins", "matin", "matins", "après", "soir", "soirs", "nuit", "nuits", "aujourd'hui", "demain", "jour", "jours",
    "semaine", "week", "end", "ends", "weekend", "weekends", "ouvrables", "quotidiennement",
    *DAYS, *(d + "s" for d in DAYS), *_NUMBER_WORDS,
}
_ELIDED = re.compile(r"^(?:[ldjmtsc]|qu)'")
"""A word's elided article or pronoun: "l'après-midi", "d'heure", "d'appeler"."""
_STARTS = {"à", "pour", "vers", "dans", "le", "ce", "cet", "cette", "chaque", "tous", "toutes", "demain", "après",
           "aujourd'hui", "midi", "minuit", *DAYS}
"""Words a time said at the end of a reminder may start with."""
_TRAILING = {"de", "du", "d'", "des", "et", "le", "la", "les", "pour", "à", "au", "en", "dans", "ce", "cet", "cette",
             "vers", "chaque", "tous", "toutes"}
"""Words a time is said with, but which do not end one."""


@dataclass
class When:
    """When an alarm or a reminder is: its first time (local), how it repeats
    (an RRULE, or None), and what was said besides (a reminder's text)."""

    start: datetime
    rrule: str | None = None
    rest: str = ""
    relative: bool = False
    """Said from now ("dans 20 minutes")."""
    said: str = ""
    """The words that said when."""


def _is_when_word(word: str) -> bool:
    w = word.lower().strip(",.!?").replace("’", "'")
    if w in _WHEN_WORDS or re.fullmatch(r"\d{1,2}(?:h\d{0,2}|:\d{2})?", w):
        return True
    # "après-midi", "dix-sept", "week-end", "l'après-midi", "d'heure"; not
    # "d'appeler" or "rendez-vous".
    parts = [_ELIDED.sub("", p) for p in w.split("-") if p]
    return bool(parts) and (len(parts) > 1 or parts[0] != w) and all(
        p in _WHEN_WORDS or p.isdigit() for p in parts)


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
    # Not "et" at its start: it belongs to what was said besides.
    while begin < end and words[begin].lower() in ("et",):
        begin += 1
    return begin, end


def _joined(text: str) -> str:
    """The words speech-to-text splits: "aujourd hui"."""
    return re.sub(r"\baujourd\s+hui\b", "aujourd'hui", text.replace("’", "'"), flags=re.IGNORECASE)


def when(text: str, now: datetime, alarm: bool = False) -> When | None:
    """When ``text`` says: a time (and a day, or how it repeats), or a time
    from now; None when it says none. ``now`` is aware local time; an
    ``alarm`` said for another day without du matin or du soir is in the
    morning."""
    words = _joined(text).split()
    best: tuple[When, int] | None = None
    for from_end in (False, True):
        begin, end = _run(words, from_end)
        found = None
        while begin < end:
            # Not "de" or "pour" at its end: "dans dix minutes | de surveiller
            # le four".
            while end > begin and words[end - 1].lower().strip(",.!?") in _TRAILING:
                end -= 1
            if begin >= end:
                break
            found = _read(" ".join(words[begin:end]), now, alarm)
            if found is not None:
                break
            # Not all of it is the time ("de me reposer dix minutes à 17
            # heures"): less of it, from where it meets the rest, to a word a
            # time starts or ends with.
            if from_end:
                begin += 1
                while begin < end and words[begin].lower().strip(",.!?") not in _STARTS:
                    begin += 1
            else:
                end -= 1
        if found is not None and (best is None or end - begin > best[1]):
            found.rest = " ".join(words[:begin] + words[end:]).strip(" ,")
            found.said = " ".join(words[begin:end])
            best = (found, end - begin)
    return best[0] if best else None


def _plain(said: str) -> str:
    """Lowercase, its hyphens spaces and elisions apart, spaced at its ends:
    " sept heures de l' après midi "."""
    s = said.lower().replace("’", "'").replace(".", " ").replace(",", " ").replace("-", " ")
    s = re.sub(r"(?<![\w'])((?:[ldjmtsc]|qu)')(?=\w)", r"\1 ", s)
    s = re.sub(r"(\d)\s*h\s*(\d{2})\b", r"\1 h \2", s)
    s = re.sub(r"(\d)h\b", r"\1 h", s)
    return " " + " ".join(s.split()) + " "


def _amount(said: str) -> float | None:
    """A number said or written: "vingt", "45", "vingt et une"."""
    value = parse_num(said)
    return float(value) if value else None


def _ahead(s: str) -> float | None:
    """Seconds from now that ``s`` says, or None: "dans 20 minutes", "dans une
    heure et demie", "une demi heure", "un quart d' heure"; a length in minutes
    alone too, but in hours only after "dans" (else it is a clock time)."""
    t = s.strip()
    after_dans = t.startswith("dans ")
    if after_dans:
        t = t[5:]
    fixed = {"une demi heure": 1800, "une demie heure": 1800, "un quart d' heure": 900, "trois quarts d' heure": 2700}
    if t in fixed:
        return fixed[t]
    found = re.fullmatch(r"(.+?) minutes?", t)
    if found:
        amount = _amount(found.group(1))
        return amount * 60 if amount else None
    found = re.fullmatch(r"(.+?) heures?(?: et (demie|quart)| (.+?)(?: minutes?)?)?", t)
    if found and after_dans:
        hours = _amount(found.group(1))
        if not hours:
            return None
        extra = {"demie": 30, "quart": 15}.get(found.group(2) or "", 0)
        if found.group(3):
            minutes = _amount(found.group(3))
            if minutes is None:
                return None
            extra = minutes
        return hours * 3600 + extra * 60
    return None


def _read(said: str, now: datetime, alarm: bool) -> When | None:
    """A run of time words as a When; None when it isn't one (or names a day
    but no time: see ``wants_time``)."""
    s = _plain(said)

    seconds = _ahead(s)
    if seconds:
        return When(now + timedelta(seconds=seconds), relative=True)
    if " minute " in s or " minutes " in s:
        return None  # a length with more: "dix minutes | à 17 heures"

    rule, days = None, None
    if re.search(r" (tous les jours de la semaine|chaque jour de la semaine|en semaine|les jours de semaine"
                 r"|les jours de la semaine|du lundi au vendredi|les jours ouvrables|jours ouvrables) ", s):
        rule, days = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", [0, 1, 2, 3, 4]
    elif re.search(r" (tous les week ?ends?|chaque week ?end|le week ?end|les week ?ends?) ", s):
        rule, days = "FREQ=WEEKLY;BYDAY=SA,SU", [5, 6]
    elif re.search(r" (tous les jours|chaque jour|tous les matins|chaque matin|tous les soirs|chaque soir"
                   r"|toutes les nuits|chaque nuit|quotidiennement) ", s):
        rule = "FREQ=DAILY"
    else:
        repeated = [i for i, d in enumerate(DAYS) if re.search(rf" (?:tous les|chaque|les) (?:\w+ et )*{d}s? | {d}s ", s)]
        if repeated:
            rule, days = "FREQ=WEEKLY;BYDAY=" + ",".join(CODES[i] for i in repeated), repeated

    date = _date(s, now) if rule is None else None

    numbers = sorted(_NUMBER_WORDS - {"demi", "demie", "quart", "quarts"})
    if not re.search(r"\d|midi|minuit| (?:" + "|".join(numbers) + ") ", s):
        return None  # no time: a day alone is not enough
    time = reading.clock(s)
    if time is None:
        return None
    hour, minute, meridiem = time
    if " matin " in s:
        meridiem = "am"
    elif re.search(r" (après midi|soir) ", s):
        meridiem = "pm"
    elif " nuit " in s and hour <= 12:
        # "Onze heures de la nuit" is the night's start, "trois heures de la
        # nuit" its middle.
        meridiem = "pm" if 7 <= hour < 12 else "am"
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0

    def at(day: Any, h: int) -> datetime:
        return now.replace(year=day.year, month=day.month, day=day.day, hour=h % 24, minute=minute, second=0, microsecond=0)

    if meridiem is None and 1 <= hour <= 12:
        if date is None and rule is None:
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
    if date is None:
        start = at(now.date(), hour)
        return When(start if start > now else start + timedelta(days=1))
    if " cette nuit " in s and hour < 7:
        date += timedelta(days=1)  # "cette nuit à 3 heures": after midnight
    start = at(date, hour)
    if start <= now and date == now.date() and not re.search(r" (aujourd'hui|ce soir|ce matin|cet après midi) ", s):
        start += timedelta(days=7)  # "lundi" on a Monday, the time gone: next week's
    return When(start) if start > now else None


def _date(s: str, now: datetime) -> Any:
    """The day ``s`` (plain, spaced at its ends) names, if it names one."""
    if " après demain " in s:
        return (now + timedelta(days=2)).date()
    if " demain " in s:
        return (now + timedelta(days=1)).date()
    if re.search(r" (aujourd'hui|ce soir|ce matin|cet après midi|cette nuit) ", s):
        return now.date()
    date = None
    found = re.search(rf" ({_DAY})( prochain)? ", s)
    if found:
        ahead = (DAYS.index(found.group(1)) - now.weekday()) % 7
        date = (now + timedelta(days=ahead or (7 if found.group(2) else 0))).date()
    found = re.search(r" dans (\S+(?: et \S+| \S+)?) jours? ", s)
    if found and _amount(found.group(1)):
        date = (now + timedelta(days=int(_amount(found.group(1))))).date()
    return date


def day(text: str, now: datetime) -> Any:
    """The day ``text`` names without a time ("de demain", "pour vendredi"),
    or None."""
    return _date(_plain(_joined(text)), now)


_NOT_ABOUT = {
    "le", "la", "les", "l", "un", "une", "des", "de", "du", "d", "mon", "ma", "mes", "ton", "ta", "tes", "votre",
    "vos", "à", "au", "aux", "pour", "que", "qu", "propos", "concernant", "sur", "et", "me", "m", "moi", "te", "t",
    "toi", "vous", "rappel", "rappels", "celui", "celle",
}


def about(text: str) -> list[str]:
    """What a reminder is about, as words to compare: "mon rappel d'appeler
    maman demain" -> ["appeler", "maman"]."""
    words = [_ELIDED.sub("", w) for w in re.findall(r"[\w']+", _joined(text).lower())]
    return [w for w in words if w and w not in _NOT_ABOUT and not _is_when_word(w)]


def wants_time(text: str) -> bool:
    """Whether ``text`` names a day or a repeat but no time ("demain", "tous
    les lundis"): asked what time."""
    s = _plain(_joined(text))
    return bool(re.search(rf" (demain|aujourd'hui|ce soir|ce matin|cette nuit|tous|toutes|chaque|quotidiennement"
                          rf"|en semaine|week ?ends?|{_DAY}s?) ", s))


_SWAPS = {"mon": "votre", "ma": "votre", "mes": "vos", "moi": "vous", "me": "vous", "je": "vous", "moi même": "vous même"}


def what(text: str) -> str:
    """A reminder's text, as it is said back: "d'appeler ma mère" ->
    "appeler votre mère"."""
    s = _joined(text).strip(" ,.?!")
    s = re.sub(r"^(?:de|que|à propos de|pour)(?:\s+|$)|^(?:d|qu)'", "", s, flags=re.IGNORECASE)
    out = []
    for word in s.split():
        lower = word.lower()
        if lower[:2] in ("m'", "j'") and len(lower) > 2:
            out += ["vous", word[2:]]
        else:
            out.append(_SWAPS.get(lower, word))
    return " ".join(out)


# ---------------------------------------------------------------- speaking

EXAMPLES = {
    "alarm_time": "sept heures et demie demain",
    "alarm": "sept heures",
    "alarm_other": "huit heures",
    "reminder": "d'appeler maman",
    "reminder_timed": "d'appeler maman à dix-sept heures",
    "reminder_day": "d'appeler maman demain",
    "reminder_other": "de nourrir le chat",
    "reminder_nothing": "de",
    "call": "Appeler maman",
    "bins": "Sortir les poubelles",
}
"""What the web UI's examples of what alarms and reminders say are made
from (alarms.outcome_examples), as speech-to-text writes them: as English's
(voice_incubator/languages/en/calendar.py)."""

ALARM_WHEN = "Pour quelle heure dois-je mettre le réveil ?"
REMINDER_WHEN = "Quand dois-je vous le rappeler ?"
REMINDER_WHAT = "Que dois-je vous rappeler ?"
NO_ALARMS = "Aucun réveil n'est réglé."
NO_REMINDERS = "Vous n'avez aucun rappel."
CALENDAR_NEEDED = ("Les réveils et les rappels ont besoin du calendrier local de Home Assistant, et je n'ai pas pu "
                   "le créer.")
ALARM_TITLE = "Réveil"
"""An alarm's event, on the calendar."""


def _clock(hour: int, minute: int) -> str:
    """"7 heures 30", "midi", "minuit 15"."""
    if hour in (0, 12):
        return ("minuit" if hour == 0 else "midi") + (f" {minute}" if minute else "")
    return clock(hour, minute)


def said_when(start: datetime, rrule: str | None, now: datetime) -> str:
    """"à 7 heures 30", "demain à 7 heures 30", "vendredi à 9 heures", "à 7
    heures tous les jours de la semaine", "le 30 octobre à 9 heures": when
    an alarm or a reminder is, as said after it."""
    time = f"à {_clock(start.hour, start.minute)}"
    if rrule:
        days = re.search(r"BYDAY=([A-Z,]+)", rrule)
        if not days:
            return f"{time} tous les jours"
        codes = days.group(1).split(",")
        if codes == CODES[:5]:
            return f"{time} tous les jours de la semaine"
        if codes == CODES[5:]:
            return f"{time} le week-end"
        return f"{time} tous les {join([DAYS[CODES.index(c)] + 's' for c in codes])}"
    ahead = (start.date() - now.date()).days
    if ahead == 0:
        return time
    if ahead == 1:
        return f"demain {time}"
    if ahead == 2:
        return f"après-demain {time}"
    if ahead < 7:
        return f"{DAYS[start.weekday()]} {time}"
    return f"le {'1er' if start.day == 1 else start.day} {MONTHS[start.month - 1]} {time}"


def _of(said: str) -> str:
    """When, said after a noun: "de 7 heures 30", "de demain à 7 heures",
    "du 30 octobre à 9 heures", "d'après-demain à midi"."""
    if said.startswith("à "):
        return f"de {said[2:]}"
    if said.startswith("le "):
        return f"du {said[3:]}"
    return f"d'{said}" if said[:1] in "aeiouéèêàâh" else f"de {said}"


def _from_now(start: datetime, now: datetime) -> str:
    return duration(max(60, round((start - now).total_seconds() / 60) * 60))


def alarm_set(start: datetime, rrule: str | None, now: datetime) -> dict[str, str]:
    specific = f"Réveil réglé {said_when(start, rrule, now)}."
    return {"brief": "Réveil réglé.", "specific": specific, "verbose": f"{specific[:-1]}, dans {_from_now(start, now)}."}


def _infinitive(text: str) -> bool:
    """Whether a reminder's text is something to do ("appeler maman"), said
    after "de"; else it is said as it is, after a colon."""
    first = text.split()[0].lower() if text.split() else ""
    return bool(re.search(r"(?:er|ir|re)$", first)) and first not in _NOT_VERBS


_NOT_VERBS = {"leur", "notre", "votre", "sur", "pour", "hier", "mer", "mère", "père", "frère", "entre", "contre"}
"""Words that end as an infinitive does, and aren't one."""


def reminder_set(what_said: str, start: datetime, rrule: str | None, now: datetime, relative: bool) -> dict[str, str]:
    at = f"dans {_from_now(start, now)}" if relative else said_when(start, rrule, now)
    later = "" if relative else f", dans {_from_now(start, now)}"
    if not what_said:
        specific = f"Je vous le rappellerai {at}."
        verbose = f"Je vous le rappellerai {at}{later}."
    elif _infinitive(what_said):
        of = f"d'{what_said}" if what_said[:1].lower() in "aeiouéèêàâh" else f"de {what_said}"
        specific = f"Je vous rappellerai {of} {at}."
        verbose = f"Je vous rappellerai {of} {at}{later}."
    else:
        specific = f"Je vous le rappellerai {at} : {what_said}."
        verbose = f"Je vous le rappellerai {at}{later} : {what_said}."
    return {"brief": "Je vous le rappellerai.", "specific": specific, "verbose": verbose}


def reminder_listed(what_said: str) -> str:
    """A reminder without a time, put on the to-do list."""
    return f"J'ai ajouté {what_said} à vos rappels."


def alarm_due(title: str, start: datetime) -> str:
    """What an alarm says when it rings: "Il est 7 heures 30."; a named one
    first says its name."""
    said = f"Il est {_clock(start.hour, start.minute)}."
    return said if title.strip().lower() in ("", ALARM_TITLE.lower(), "alarm") else f"{_capital(title.strip())}. {said}"


def reminder_due(text: str) -> str:
    return f"Rappel : {text.strip().rstrip('.')}."


def _listed(events: list[dict[str, Any]], now: datetime) -> list[str]:
    return [said_when(e["start"], e.get("rrule"), now) for e in events]


def alarms_listed(alarms: list[dict[str, Any]], now: datetime) -> str:
    said = _listed(alarms, now)
    if len(said) == 1:
        return f"Vous avez un réveil {said[0]}."
    return f"Vous avez {len(said)} réveils : {join(said)}."


def reminders_listed(reminders: list[dict[str, Any]], now: datetime) -> str:
    said = [f"{r['text']} {s}" for r, s in zip(reminders, _listed(reminders, now), strict=True)]
    if len(said) == 1:
        return f"Vous avez un rappel : {said[0]}."
    return f"Vous avez {len(said)} rappels : {join(said)}."


def alarm_cancelled(alarms: list[dict[str, Any]], now: datetime) -> dict[str, str]:
    said = _listed(alarms, now)
    if len(said) == 1:
        specific = f"J'ai annulé le réveil {_of(said[0])}."
    else:
        specific = f"J'ai annulé {len(said)} réveils."
    return {"brief": "Réveil annulé." if len(said) == 1 else "Réveils annulés.", "specific": specific,
            "verbose": f"J'ai annulé les réveils {join([_of(s) for s in said])}." if len(said) > 1 else specific}


def which_alarm(alarms: list[dict[str, Any]], now: datetime) -> str:
    return f"Quel réveil ? Vous avez {join(alarm_labels(alarms, now))}."


def which_alarm_asked(alarms: list[dict[str, Any]], now: datetime) -> str:
    """Several alarms fit, asked of a satellite that hears the answer."""
    return f"{_capital(join_or(alarm_labels(alarms, now)))} ?"


def alarm_labels(alarms: list[dict[str, Any]], now: datetime) -> list[str]:
    """How each is told apart (an answer to which_alarm_asked)."""
    return [f"le réveil {_of(when)}" for when in _listed(alarms, now)]


def alarm_not_found(asked: str, alarms: list[dict[str, Any]], now: datetime) -> str:
    return f"Il n'y a pas de réveil {asked}. {alarms_listed(alarms, now)}" if alarms else NO_ALARMS


def reminder_cancelled(reminders: list[dict[str, Any]], now: datetime) -> dict[str, str]:
    said = [f"{r['text']} {when}" for r, when in zip(reminders, _listed(reminders, now), strict=True)]
    if len(said) == 1:
        specific = f"J'ai annulé le rappel {_of(_listed(reminders, now)[0])} : {reminders[0]['text']}."
    else:
        specific = f"J'ai annulé {len(said)} rappels."
    return {"brief": "Rappel annulé." if len(said) == 1 else "Rappels annulés.", "specific": specific,
            "verbose": f"J'ai annulé les rappels : {join(said)}." if len(said) > 1 else specific}


def which_reminder(reminders: list[dict[str, Any]], now: datetime) -> str:
    return f"Quel rappel ? Vous avez {join(reminder_labels(reminders, now))}."


def which_reminder_asked(reminders: list[dict[str, Any]], now: datetime) -> str:
    """Several reminders fit, asked of a satellite that hears the answer."""
    return f"{_capital(join_or(reminder_labels(reminders, now)))} ?"


def reminder_labels(reminders: list[dict[str, Any]], now: datetime) -> list[str]:
    """How each is told apart (an answer to which_reminder_asked)."""
    return [f"{r['text']} {when}" for r, when in zip(reminders, _listed(reminders, now), strict=True)]


def reminder_not_found(reminders: list[dict[str, Any]], now: datetime) -> str:
    return f"Je ne trouve pas ce rappel. {reminders_listed(reminders, now)}" if reminders else NO_REMINDERS
