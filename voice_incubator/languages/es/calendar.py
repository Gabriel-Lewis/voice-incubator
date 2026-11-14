"""Alarms and reminders on the calendar, in Spanish, with English's names (see
voice_incubator/languages/en/calendar.py): when one is for -- read from what
was said ("mañana a las siete y media", "todos los días laborables a las 6",
"dentro de 20 minutos", "el viernes a las cinco de la tarde") -- and what the
app says about them.

"Mañana" is both tomorrow and the morning: "mañana por la mañana" is
tomorrow morning, "a las siete de la mañana" 7 am, "el recordatorio de
mañana" tomorrow's. A time is read by the pack's clock (reading.clock: "y
media", "y cuarto", "menos cuarto", "de la tarde", 24-hour "las 19"); said
back on a 24-hour clock, as the app says one ("a las 19 y 30", "a la una").
A reminder is said back as it was said, in the second person: "llamar a mi
madre" is "llamar a tu madre", "que llame al fontanero" "que llames al
fontanero"."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from . import reading
from .skills.clock import minutes_in
from .skills.numbers import parse_num
from .speech import _capital, clock, duration, join, join_or

# ----------------------------------------------------------------- reading

DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
CODES = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


def _fold(text: str) -> str:
    """Lowercase, without accents: "Miércoles" -> "miercoles"."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


_FOLDED_DAYS = [_fold(d) for d in DAYS]
_DAY = rf"(?:{'|'.join(_FOLDED_DAYS)})"
_MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
           "noviembre", "diciembre"]

_HOUR_WORDS = {
    "cero", "una", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce",
    "trece", "catorce", "quince", "dieciseis", "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno",
    "veintiuna", "veintiun", "veintidos", "veintitres", "veinticuatro", "veinticinco", "veintiseis", "veintisiete",
    "veintiocho", "veintinueve", "treinta", "cuarenta", "cincuenta",
}
"""Numbers a clock time is said with (folded): an hour or its minutes."""
_NUMBER_WORDS = {*_HOUR_WORDS, "un", "media", "medio", "cuarto", "cuartos"}
_WHEN_WORDS = {
    "a", "al", "las", "la", "el", "los", "de", "del", "en", "para", "por", "dentro", "este", "esta", "proximo",
    "proxima", "viene", "todos", "todas", "cada", "y", "menos", "punto", "am", "pm",
    "hoy", "manana", "mananas", "pasado", "tarde", "tardes", "noche", "noches", "madrugada", "mediodia", "medianoche",
    "dia", "dias", "diario", "diariamente", "laborable", "laborables", "semana", "fin", "fines", "finde", "findes",
    "minuto", "minutos", "hora", "horas", *_FOLDED_DAYS, *(d + "s" for d in _FOLDED_DAYS), *_NUMBER_WORDS,
}
_EDGE = {"a", "al", "las", "la", "el", "los", "de", "del", "en", "para", "por", "y", "este", "esta", "que"}
"""Words a time is said with, but which alone are no time."""
_STARTS = {"a", "al", "para", "el", "este", "esta", "hoy", "manana", "pasado", "todos", "todas", "cada", "los",
           "dentro", "en", "mediodia", "medianoche", *_FOLDED_DAYS}
"""Words a time said at the end of a reminder may start with."""


@dataclass
class When:
    """When an alarm or a reminder is: its first time (local), how it repeats
    (an RRULE, or None), and what was said besides (a reminder's text)."""

    start: datetime
    rrule: str | None = None
    rest: str = ""
    relative: bool = False
    """Said from now ("dentro de 20 minutos")."""
    said: str = ""
    """The words that said when."""


def _word(word: str) -> str:
    """A word as the reading compares it: folded, without punctuation."""
    return _fold(word).strip(",.!?¿¡;:").replace(".", "")


def _numeric(word: str) -> bool:
    return word in _NUMBER_WORDS or bool(re.fullmatch(r"\d{1,2}([:.h]\d{2})?", word))


def _is_when_word(word: str) -> bool:
    w = _word(word)
    return w in _WHEN_WORDS or bool(re.fullmatch(r"\d{1,2}([:h]\d{2})?h?(am|pm)?", w))


def _run(words: list[str], from_end: bool) -> tuple[int, int]:
    """The longest run of time words at the start or the end: (begin, end)."""
    n = len(words)

    def ok(i: int) -> bool:
        w = _word(words[i])
        before = _word(words[i - 1]) if i > 0 else ""
        after = _word(words[i + 1]) if i + 1 < n else ""
        days = {*_FOLDED_DAYS, *(d + "s" for d in _FOLDED_DAYS)}
        if w == "y":  # "las siete y media", "hora y media", "los lunes y los jueves": not "pan y leche"
            return (_numeric(before) or before in days or before in ("hora", "horas", "minuto", "minutos")) and (
                _numeric(after) or after in days or after in ("los", "el"))
        if w == "menos":  # "las ocho menos cuarto": not "menos azúcar"
            return _numeric(before) and _numeric(after)
        if w == "que":  # "el lunes que viene": not "que llame"
            return after == "viene"
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
    # Not "y" at its start, or a preposition or an article at its end: they
    # belong to what was said besides.
    while begin < end and _word(words[begin]) == "y":
        begin += 1
    while begin < end and _word(words[end - 1]) in _EDGE:
        end -= 1
    return begin, end


def _joined(text: str) -> str:
    """What speech-to-text writes apart or differently: "medio día",
    "media noche", "19h"; no opening marks."""
    text = re.sub(r"[¿¡]", "", text)
    text = re.sub(r"\bmedio\s+d[ií]a\b", "mediodía", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmedia\s+noche\b", "medianoche", text, flags=re.IGNORECASE)
    return re.sub(r"\b(\d{1,2}(?::\d{2})?)\s*h\b", r"\1", text, flags=re.IGNORECASE)


def when(text: str, now: datetime, alarm: bool = False) -> When | None:
    """When ``text`` says: a time (and a day, or how it repeats), or a time
    from now; None when it says none. ``now`` is aware local time; an
    ``alarm`` said for another day without "de la tarde" is in the morning."""
    words = _joined(text).split()
    best: tuple[When, int] | None = None
    for from_end in (False, True):
        begin, end = _run(words, from_end)
        found = None
        while begin < end:
            found = _read(" ".join(words[begin:end]), now, alarm)
            if found is not None:
                break
            # Not all of it is the time ("descansar diez minutos a las cinco"):
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


def _spaced(said: str) -> str:
    """Folded, lowercase, spaced at its ends, for the patterns below."""
    s = _fold(said).replace("a.m.", "am").replace("p.m.", "pm").replace(",", " ").replace(".", " ")
    s = re.sub(r"(\d)(am|pm)\b", r"\1 \2", s)
    s = re.sub(r"\ben punto\b", " ", s)
    return " " + " ".join(s.split()) + " "


def _read(said: str, now: datetime, alarm: bool) -> When | None:
    """A run of time words as a When; None when it isn't one (or names a day
    but no time: see ``wants_time``)."""
    s = _spaced(said)
    # "las siete y veinte minutos": the minutes of a clock time.
    s = re.sub(r"( (?:la|las) \S+(?: horas?)? y \S+(?: y \S+)?) minutos? ", r"\1 ", s)

    # From now: "en 20 minutos", "dentro de una hora", "en media hora",
    # "dentro de hora y media" -- or a length alone: speech-to-text, or the
    # free text's edge, can drop the "en".
    amount = minutes_in(re.sub(r"^ (?:para |por )?(?:en|dentro de|de aqui a) ", " ", s).strip())
    if amount:
        return When(now + timedelta(minutes=float(amount)), relative=True)
    if re.search(r" (?:minutos?|horas?) ", s) and not re.search(r" (?:la|las) \S+ horas? ", s):
        return None  # a length, and more: not all of it is the time

    rule, days = None, None
    if re.search(r" (?:dias? laborables?|laborables|entre semana|de lunes a viernes) ", s):
        rule, days = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", [0, 1, 2, 3, 4]
    elif re.search(r" (?:fines de semana|findes|cada fin de semana|cada finde) ", s):
        rule, days = "FREQ=WEEKLY;BYDAY=SA,SU", [5, 6]
    elif re.search(rf" (?:todos los|cada|los) {_DAY}s? | (?:sabados|domingos) ", s):
        # "Los lunes", "cada lunes", "los sábados" -- or "sábados" alone: free
        # text loses the article at its edge ("pon una alarma los sábados").
        repeated = [i for i, d in enumerate(_FOLDED_DAYS) if re.search(rf" {d}s? ", s)]
        rule, days = "FREQ=WEEKLY;BYDAY=" + ",".join(CODES[i] for i in repeated), repeated
    elif re.search(r" (?:todos los dias|cada dia|diariamente|a diario|todas las (?:mananas|tardes|noches)"
                   r"|cada (?:manana|tarde|noche)) ", s):
        rule = "FREQ=DAILY"

    date = _date(s, now) if rule is None else None

    # The day said by a count ("dentro de 3 días") has no time in it.
    t = re.sub(r" (?:en|dentro de) \S+ dias? ", " ", s)
    if not re.search(r"\d|mediodia|medianoche| (?:" + "|".join(sorted(_HOUR_WORDS)) + ") ", t):
        return None  # no time: a day alone is not enough
    time = reading.clock(t)
    if time is None:
        return None
    hour, minute, meridiem = time
    if " am " in s or re.search(r" (?:todas las|por las|cada) mananas? ", s):
        meridiem = "am"
    elif " pm " in s or re.search(r" (?:todas las|por las|cada) (?:tardes?|noches?) ", s):
        meridiem = "pm"
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
        # Today ("hoy a las 9", said in the afternoon): the one still to come.
        if date == now.date() and hour < 12 and at(date, hour) <= now and re.search(r" (?:hoy|esta noche|esta tarde) ", s):
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
    if start <= now and date == now.date() and not re.search(r" (?:hoy|esta noche|esta tarde|esta manana) ", s):
        start += timedelta(days=7)  # "el lunes" on a Monday, the time gone: next week's
    return When(start) if start > now else None


def _tomorrow(s: str) -> bool:
    """Whether ``s`` (folded) says tomorrow: "mañana", "de mañana" -- not
    the morning ("de la mañana", "esta mañana", "las mañanas") or "pasado
    mañana"."""
    words = s.split()
    return any(w == "manana" and (i == 0 or words[i - 1] not in ("la", "las", "esta", "pasado", "cada", "una"))
               for i, w in enumerate(words))


def _date(s: str, now: datetime) -> Any:
    """The day ``s`` (folded, spaced at its ends) names, if it names one."""
    if " pasado manana " in s:
        return (now + timedelta(days=2)).date()
    if _tomorrow(s):
        return (now + timedelta(days=1)).date()
    if re.search(r" (?:hoy|esta noche|esta tarde|esta manana|esta madrugada) ", s):
        return now.date()
    date = None
    found = re.search(rf" ({_DAY}) ", s)
    if found:
        day = found.group(1)
        ahead = (_FOLDED_DAYS.index(day) - now.weekday()) % 7
        later = re.search(rf" (?:proximo {day}|{day} que viene|{day} proximo) ", s)
        date = (now + timedelta(days=ahead or (7 if later else 0))).date()
    found = re.search(r" (?:en|dentro de) (\S+) dias? ", s)
    if found and parse_num(found.group(1)):
        date = (now + timedelta(days=int(parse_num(found.group(1))))).date()
    return date


def day(text: str, now: datetime) -> Any:
    """The day ``text`` names without a time ("de mañana", "del viernes"), or None."""
    return _date(_spaced(_joined(text)), now)


_NOT_ABOUT = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "mi", "mis", "tu", "tus", "su", "sus", "de", "del", "a",
    "al", "que", "para", "sobre", "y", "me", "te", "se", "lo", "con", "por", "recordatorio", "recordatorios",
}


def about(text: str) -> list[str]:
    """What a reminder is about, as words to compare (folded): "mi
    recordatorio de llamar a mamá mañana" -> ["llamar", "mama"]."""
    words = re.findall(r"\w+", _fold(_joined(text)))
    return [w for w in words if w not in _NOT_ABOUT and not _is_when_word(w)]


def wants_time(text: str) -> bool:
    """Whether ``text`` names a day or a repeat but no time ("mañana",
    "todos los lunes"): asked what time."""
    s = _spaced(text)
    return _tomorrow(s) or bool(re.search(
        rf" (?:hoy|pasado manana|esta noche|esta tarde|diario|diariamente|laborables|fines de semana|{_DAY}s?) "
        rf"| (?:todos los|todas las) (?:dias|mananas|tardes|noches|fines|{_DAY}s?) | cada (?:dia|manana|tarde|noche|{_DAY}) ",
        s,
    ))


_SWAPS = {"mi": "tu", "mis": "tus", "me": "te", "conmigo": "contigo", "mío": "tuyo", "mía": "tuya", "míos": "tuyos",
          "mías": "tuyas", "yo": "tú"}
"""The speaker's words for themselves, as said back to them."""
_YOURS = {"tengo": "tienes", "voy": "vas", "soy": "eres", "estoy": "estás", "he": "has", "debo": "debes",
          "puedo": "puedes", "quiero": "quieres", "hago": "haces", "salgo": "sales", "vengo": "vienes",
          "necesito": "necesitas", "llamo": "llamas", "llego": "llegas"}
"""A verb after "que" said by the speaker of themselves, as said back:
"que tengo médico" -> "que tienes médico"."""
_NOT_VERBS = {"el", "la", "los", "las", "un", "una", "unos", "unas", "mi", "tu", "su", "este", "esta", "ese", "esa",
              "nada", "nadie", "alguien", "ya", "mañana", "mama", "mamá", "papa", "papá",
              # Said of someone else ("que viene el fontanero"), not the speaker.
              "viene", "llega", "sale", "empieza", "termina", "abre", "cierra", "cumple", "pasa", "toca", "juega",
              "vence", "acaba", "hace"}


def what(text: str) -> str:
    """A reminder's text, as it is said back: "de llamar a mi madre" ->
    "llamar a tu madre"; "que me tome la pastilla" -> "que te tomes la
    pastilla" (a verb right after "que" in the second person)."""
    s = re.sub(r"^(?:de|sobre|para)\b\s*", "", text.strip(" ,.?!¿¡"), flags=re.IGNORECASE)
    if s.lower() == "que":
        return ""
    words = s.split()
    out = []
    verb = False  # the next word is the verb of a "que" said of the speaker
    for w in words:
        low = w.lower()
        if low in _SWAPS:
            out.append(_SWAPS[low])
            continue
        if verb and low not in ("me", "no", "se"):
            verb = False
            if low in _YOURS:
                out.append(_YOURS[low])
                continue
            if len(low) > 2 and low[-1] in "ae" and low not in _NOT_VERBS:
                out.append(w + "s")
                continue
        if low == "que":
            verb = True
        # An infinitive's "me": "tomarme" -> "tomarte".
        out.append(re.sub(r"([aeií]r)me$", r"\1te", w))
    return " ".join(out)


# ---------------------------------------------------------------- speaking

EXAMPLES = {
    "alarm_time": "mañana a las siete y media",
    "alarm": "siete",
    "alarm_other": "ocho",
    "reminder": "llamar a mamá",
    "reminder_timed": "llamar a mamá a las cinco de la tarde",
    "reminder_day": "llamar a mamá mañana",
    "reminder_other": "dar de comer al gato",
    "reminder_nothing": "de",
    "call": "Llamar a mamá",
    "bins": "Sacar la basura",
}
"""What the web UI's examples of what alarms and reminders say are made
from (alarms.outcome_examples), as speech-to-text writes them: see
English's."""

ALARM_WHEN = "¿Para qué hora pongo la alarma?"
REMINDER_WHEN = "¿Cuándo te lo recuerdo?"
REMINDER_WHAT = "¿Qué quieres que te recuerde?"
NO_ALARMS = "No hay ninguna alarma puesta."
NO_REMINDERS = "No tienes recordatorios."
CALENDAR_NEEDED = ("Las alarmas y los recordatorios necesitan el calendario local de Home Assistant, y no he podido "
                   "configurarlo.")
ALARM_TITLE = "Alarma"
"""An alarm's event, on the calendar."""


def _at(hour: int, minute: int) -> str:
    """"a las 7 y 30", "a la una", "a medianoche"."""
    return f"a {clock(hour, minute)}"


def _plural(day_name: str) -> str:
    """"los sábados", but "los lunes"."""
    return day_name if day_name.endswith("s") else day_name + "s"


def said_when(start: datetime, rrule: str | None, now: datetime) -> str:
    """"a las 7 y 30", "mañana a las 7 y 30", "el viernes a las 9", "los días
    laborables a las 7", "el 30 de octubre a las 9"."""
    time = _at(start.hour, start.minute)
    if rrule:
        days = re.search(r"BYDAY=([A-Z,]+)", rrule)
        if not days:
            return f"todos los días {time}"
        codes = days.group(1).split(",")
        if codes == CODES[:5]:
            return f"los días laborables {time}"
        if codes == CODES[5:]:
            return f"los fines de semana {time}"
        return f"los {join([_plural(DAYS[CODES.index(c)]) for c in codes])} {time}"
    ahead = (start.date() - now.date()).days
    if ahead == 0:
        return time
    if ahead == 1:
        return f"mañana {time}"
    if ahead < 7:
        return f"el {DAYS[start.weekday()]} {time}"
    return f"el {start.day} de {_MONTHS[start.month - 1]} {time}"


def _of(said: str) -> str:
    """When, after a noun: "de las 7", "de mañana a las 7", "del viernes a las 9"."""
    if said.startswith("a "):
        return "de " + said[2:]
    if said.startswith("el "):
        return "del " + said[3:]
    return "de " + said


def _from_now(start: datetime, now: datetime) -> str:
    return duration(max(60, round((start - now).total_seconds() / 60) * 60))


def alarm_set(start: datetime, rrule: str | None, now: datetime) -> dict[str, str]:
    specific = f"Alarma puesta {said_when(start, rrule, now)}."
    return {"brief": "Alarma puesta.", "specific": specific, "verbose": f"{specific[:-1]}, dentro de {_from_now(start, now)}."}


def reminder_set(what_said: str, start: datetime, rrule: str | None, now: datetime, relative: bool) -> dict[str, str]:
    at = f"dentro de {_from_now(start, now)}" if relative else said_when(start, rrule, now)
    specific = f"Te recordaré {what_said} {at}." if what_said else f"Te lo recordaré {at}."
    verbose = specific if relative else f"{specific[:-1]}, dentro de {_from_now(start, now)}."
    return {"brief": "Te lo recordaré.", "specific": specific, "verbose": verbose}


def reminder_listed(what_said: str) -> str:
    """A reminder without a time, put on the to-do list."""
    return f"He añadido {what_said} a tus recordatorios."


def alarm_due(title: str, start: datetime) -> str:
    """What an alarm says when it rings: "Son las 7 y 30."; a named one first
    says its name."""
    time = clock(start.hour, start.minute)
    said = f"{'Es' if time.startswith(('la ', 'medianoche')) else 'Son'} {time}."
    named = title.strip().lower()
    return said if named in ("", ALARM_TITLE.lower(), "alarm") else f"{_capital(title.strip())}. {said}"


def reminder_due(text: str) -> str:
    return f"Recordatorio: {text.strip().rstrip('.')}."


def _listed(events: list[dict[str, Any]], now: datetime) -> list[str]:
    return [said_when(e["start"], e.get("rrule"), now) for e in events]


def alarms_listed(alarms: list[dict[str, Any]], now: datetime) -> str:
    said = _listed(alarms, now)
    if len(said) == 1:
        return f"Tienes una alarma {said[0]}."
    return f"Tienes {len(said)} alarmas: {join(said)}."


def reminders_listed(reminders: list[dict[str, Any]], now: datetime) -> str:
    said = [f"{r['text']} {s}" for r, s in zip(reminders, _listed(reminders, now), strict=True)]
    if len(said) == 1:
        return f"Tienes un recordatorio: {said[0]}."
    return f"Tienes {len(said)} recordatorios: {join(said)}."


def alarm_cancelled(alarms: list[dict[str, Any]], now: datetime) -> dict[str, str]:
    said = _listed(alarms, now)
    if len(said) == 1:
        specific = f"He cancelado la alarma {_of(said[0])}."
    else:
        specific = f"He cancelado {len(said)} alarmas."
    return {"brief": "Alarma cancelada." if len(said) == 1 else "Alarmas canceladas.", "specific": specific,
            "verbose": f"He cancelado las alarmas: {join(said)}." if len(said) > 1 else specific}


def which_alarm(alarms: list[dict[str, Any]], now: datetime) -> str:
    return f"¿Qué alarma? Tienes alarmas {join(_listed(alarms, now))}."


def which_alarm_asked(alarms: list[dict[str, Any]], now: datetime) -> str:
    """Several alarms fit, asked of a satellite that hears the answer."""
    return f"¿{_capital(join_or(alarm_labels(alarms, now)))}?"


def alarm_labels(alarms: list[dict[str, Any]], now: datetime) -> list[str]:
    """How each is told apart (an answer to which_alarm_asked)."""
    return [f"la alarma {_of(when)}" for when in _listed(alarms, now)]


def alarm_not_found(asked: str, alarms: list[dict[str, Any]], now: datetime) -> str:
    return f"No hay ninguna alarma {asked}. {alarms_listed(alarms, now)}" if alarms else NO_ALARMS


def reminder_cancelled(reminders: list[dict[str, Any]], now: datetime) -> dict[str, str]:
    said = reminder_labels(reminders, now)
    if len(said) == 1:
        specific = f"He cancelado el recordatorio {_of(_listed(reminders, now)[0])}: {reminders[0]['text']}."
    else:
        specific = f"He cancelado {len(said)} recordatorios."
    return {"brief": "Recordatorio cancelado." if len(said) == 1 else "Recordatorios cancelados.", "specific": specific,
            "verbose": f"He cancelado los recordatorios: {join(said)}." if len(said) > 1 else specific}


def which_reminder(reminders: list[dict[str, Any]], now: datetime) -> str:
    return f"¿Qué recordatorio? Tienes {join(reminder_labels(reminders, now))}."


def which_reminder_asked(reminders: list[dict[str, Any]], now: datetime) -> str:
    """Several reminders fit, asked of a satellite that hears the answer."""
    return f"¿{_capital(join_or(reminder_labels(reminders, now)))}?"


def reminder_labels(reminders: list[dict[str, Any]], now: datetime) -> list[str]:
    """How each is told apart (an answer to which_reminder_asked)."""
    return [f"{r['text']} {when}" for r, when in zip(reminders, _listed(reminders, now), strict=True)]


def reminder_not_found(reminders: list[dict[str, Any]], now: datetime) -> str:
    return f"No hay ningún recordatorio así. {reminders_listed(reminders, now)}" if reminders else NO_REMINDERS
