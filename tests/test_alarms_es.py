"""Alarms and timed reminders in Spanish: when the calendar reads them from
what was said, what is said back (voice_incubator/languages/es/calendar.py,
through voice_incubator/alarms.py), and two commands said together
(voice_incubator/languages/es/compound.py).

Each table is a list of cases: add a row for a phrasing that must read (or
be said) some way."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from voice_incubator import alarms, compound, languages
from voice_incubator.languages.es import calendar as spanish
from voice_incubator.languages.es import compound as joined

TZ = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 10, 21, 14, 0, tzinfo=TZ)  # a Wednesday afternoon


@pytest.fixture(autouse=True)
def in_spanish():
    languages.use("es")
    yield
    languages.use(languages.DEFAULT)


WEEKDAYS = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"

# (said, alarm, start, rrule, rest): what an alarm's time or a reminder says,
# read on a Wednesday at 14:00.
WHEN = [
    # A clock time: the next to come round, morning or afternoon.
    ("a las siete y media", True, "2026-10-21 19:30", None, ""),
    ("siete y media", True, "2026-10-21 19:30", None, ""),
    ("a las ocho menos cuarto", True, "2026-10-21 19:45", None, ""),
    ("a las ocho menos diez", True, "2026-10-21 19:50", None, ""),
    ("a las siete y cuarto", True, "2026-10-21 19:15", None, ""),
    ("a las 19:30", True, "2026-10-21 19:30", None, ""),
    ("a las diecinueve treinta", True, "2026-10-21 19:30", None, ""),
    ("a las siete en punto", True, "2026-10-21 19:00", None, ""),
    ("a las 7 pm", True, "2026-10-21 19:00", None, ""),
    ("a las diez de la noche", True, "2026-10-21 22:00", None, ""),
    ("a las doce de la noche", True, "2026-10-22 00:00", None, ""),
    ("a las dos de la madrugada", True, "2026-10-22 02:00", None, ""),
    ("a la una", True, "2026-10-22 01:00", None, ""),
    ("a mediodía", True, "2026-10-22 12:00", None, ""),
    ("a medianoche", True, "2026-10-22 00:00", None, ""),
    # A day: "mañana" is tomorrow, "de la mañana" the morning.
    ("para mañana a las siete", True, "2026-10-22 07:00", None, ""),
    ("mañana a las siete de la tarde", True, "2026-10-22 19:00", None, ""),
    ("mañana por la mañana a las seis y cuarto", True, "2026-10-22 06:15", None, ""),
    ("a las seis y cuarto mañana por la mañana", True, "2026-10-22 06:15", None, ""),
    ("a las 8 de la mañana", True, "2026-10-22 08:00", None, ""),
    ("pasado mañana a las siete", True, "2026-10-23 07:00", None, ""),
    ("hoy a las nueve", True, "2026-10-21 21:00", None, ""),  # today: the one still to come
    ("esta noche a las diez", True, "2026-10-21 22:00", None, ""),
    ("el sábado a las siete", True, "2026-10-24 07:00", None, ""),  # another day: an alarm in the morning
    ("a las 7 el sábado", True, "2026-10-24 07:00", None, ""),
    ("el miércoles a las diez", True, "2026-10-28 10:00", None, ""),  # today's gone: next week's
    ("el lunes que viene a las siete", True, "2026-10-26 07:00", None, ""),
    ("el próximo lunes a las siete", True, "2026-10-26 07:00", None, ""),
    ("dentro de 3 días a las nueve", True, "2026-10-24 09:00", None, ""),
    # Repeating.
    ("todos los días a las siete", True, "2026-10-22 07:00", "FREQ=DAILY", ""),
    ("todos los días laborables a las siete menos cuarto", True, "2026-10-22 06:45", WEEKDAYS, ""),
    ("los días laborables a las 6:45", True, "2026-10-22 06:45", WEEKDAYS, ""),
    ("de lunes a viernes a las siete", True, "2026-10-22 07:00", WEEKDAYS, ""),
    ("los fines de semana a las diez", True, "2026-10-24 10:00", "FREQ=WEEKLY;BYDAY=SA,SU", ""),
    ("los lunes y los miércoles a las siete", True, "2026-10-26 07:00", "FREQ=WEEKLY;BYDAY=MO,WE", ""),
    ("todos los martes y jueves a las seis", True, "2026-10-22 06:00", "FREQ=WEEKLY;BYDAY=TU,TH", ""),
    ("cada domingo a las nueve", True, "2026-10-25 09:00", "FREQ=WEEKLY;BYDAY=SU", ""),
    ("todas las mañanas a las siete", True, "2026-10-22 07:00", "FREQ=DAILY", ""),
    # From now.
    ("en 20 minutos", True, "2026-10-21 14:20", None, ""),
    ("dentro de veinte minutos", True, "2026-10-21 14:20", None, ""),
    ("dentro de una hora", True, "2026-10-21 15:00", None, ""),
    ("dentro de media hora", True, "2026-10-21 14:30", None, ""),
    ("dentro de hora y media", True, "2026-10-21 15:30", None, ""),
    ("dentro de dos horas y cuarto", True, "2026-10-21 16:15", None, ""),
    # A reminder: the time before or after what it is about; from 7 to 11 in
    # the morning on another day, else the afternoon.
    ("a las cinco de la tarde llamar a mamá", False, "2026-10-21 17:00", None, "llamar a mamá"),
    ("llamar a mamá a las cinco", False, "2026-10-21 17:00", None, "llamar a mamá"),
    ("mañana a las nueve llamar al dentista", False, "2026-10-22 09:00", None, "llamar al dentista"),
    ("que viene el fontanero el viernes a las tres", False, "2026-10-23 15:00", None, "que viene el fontanero"),
    ("sacar la basura todos los martes a las siete de la tarde", False, "2026-10-27 19:00", "FREQ=WEEKLY;BYDAY=TU",
     "sacar la basura"),
    ("regar las plantas cada lunes a las 8", False, "2026-10-26 08:00", "FREQ=WEEKLY;BYDAY=MO", "regar las plantas"),
    ("dentro de diez minutos que mire el horno", False, "2026-10-21 14:10", None, "que mire el horno"),
    ("en 10 minutos mirar el horno", False, "2026-10-21 14:10", None, "mirar el horno"),
    ("que me tome la pastilla a las nueve de la noche", False, "2026-10-21 21:00", None, "que me tome la pastilla"),
    ("llamar a la abuela y a mi tía a las 6", False, "2026-10-21 18:00", None, "llamar a la abuela y a mi tía"),
    # A length that is the reminder's, before its time.
    ("descansar diez minutos a las cinco de la tarde", False, "2026-10-21 17:00", None, "descansar diez minutos"),
]


@pytest.mark.parametrize(("said", "alarm", "start", "rrule", "rest"), WHEN)
def test_when(said, alarm, start, rrule, rest):
    found = spanish.when(said, NOW, alarm=alarm)
    assert found is not None
    assert found.start == datetime.fromisoformat(start).replace(tzinfo=TZ)
    assert found.rrule == rrule and found.rest.strip() == rest


# (said, alarm, start, rrule): what speech-to-text, or free text that loses
# a filler at its edge ("los", "a las", "que"), makes of it.
HEARD = [
    ("sábados a las nueve", True, "2026-10-24 09:00", "FREQ=WEEKLY;BYDAY=SA"),  # "los sábados"
    ("cinco de la tarde llamar a mamá", False, "2026-10-21 17:00", None),  # "a las cinco ..."
    ("veinte minutos", True, "2026-10-21 14:20", None),  # "en veinte minutos"
    ("ocho horas", True, "2026-10-21 22:00", None),
    ("a medio día", True, "2026-10-22 12:00", None),
    ("a las 7 y 20 minutos", True, "2026-10-21 19:20", None),
]


@pytest.mark.parametrize(("said", "alarm", "start", "rrule"), HEARD)
def test_what_speech_to_text_makes_of_it(said, alarm, start, rrule):
    found = spanish.when(said, NOW, alarm=alarm)
    assert found is not None
    assert (found.start, found.rrule) == (datetime.fromisoformat(start).replace(tzinfo=TZ), rrule)


# Said without a time: none read; whether to ask for one (a day, a repeat).
NO_TIME = [
    ("comprar pan", False),
    ("", False),
    ("de llamar a mi madre", False),
    ("comprar pan mañana", True),
    ("mañana", True),
    ("pasado mañana", True),
    ("el viernes", True),
    ("todos los lunes", True),
    ("por la mañana", False),  # the morning is no day
]


@pytest.mark.parametrize(("said", "asks"), NO_TIME)
def test_no_time_is_none(said, asks):
    assert spanish.when(said, NOW) is None and spanish.when(said, NOW, alarm=True) is None
    assert spanish.wants_time(said) is asks


DAY = [
    ("de mañana", "2026-10-22"),
    ("del viernes", "2026-10-23"),
    ("de pasado mañana", "2026-10-23"),
    ("para hoy", "2026-10-21"),
    ("de llamar a mamá", None),
]


@pytest.mark.parametrize(("said", "day"), DAY)
def test_a_day_without_a_time(said, day):
    found = spanish.day(said, NOW)
    assert (found.isoformat() if found else None) == day


# (said, said back): a reminder's text, in the second person.
WHAT = [
    ("llamar a mi madre", "llamar a tu madre"),
    ("de comprar pan", "comprar pan"),
    ("que llame a mamá", "que llames a mamá"),
    ("que me tome la pastilla", "que te tomes la pastilla"),
    ("que tengo médico", "que tienes médico"),
    ("que viene el fontanero", "que viene el fontanero"),
    ("tomarme la pastilla", "tomarte la pastilla"),
]


@pytest.mark.parametrize(("said", "back"), WHAT)
def test_what_is_said_back(said, back):
    assert spanish.what(said) == back


def test_about_compares_without_accents_or_filler():
    assert spanish.about("mi recordatorio de llamar a mamá mañana") == ["llamar", "mama"]


def _event(uid, hour, minute=0, days=1, kind="alarm", rrule=None, summary="Alarma"):
    start = NOW.replace(hour=hour, minute=minute) + timedelta(days=days)
    return alarms.Event(uid, start, summary, kind, rrule=rrule)


SEVEN, SEVEN_PM = _event("1", 7), _event("2", 19)
WEEKDAY = _event("3", 6, 30, rrule=WEEKDAYS)
MONDAY = _event("4", 7, days=5)
FAR = _event("5", 9, days=9)
CALL = _event("r1", 17, days=0, kind="reminder", summary="Llamar a mamá")
DENTIST = _event("r2", 9, days=1, kind="reminder", summary="Llamar al dentista")
BINS = _event("r3", 8, days=6, kind="reminder", summary="Sacar la basura")
REMINDERS = [CALL, DENTIST, BINS]

# (operation, slots, alarms, reminders, outcome, said): what each command
# says, as alarms.plan has it (the specific level).
SAID = [
    ("alarm", {"time": "mañana a las siete y media"}, [], [], "done", "Alarma puesta mañana a las 7 y 30."),
    ("alarm", {"time": "todos los días laborables a las 6:45"}, [], [], "done",
     "Alarma puesta los días laborables a las 6 y 45."),
    ("alarm", {"time": "los sábados y domingos a las 9"}, [], [], "done", "Alarma puesta los fines de semana a las 9."),
    ("alarm", {"time": "el viernes a las 8"}, [], [], "done", "Alarma puesta el viernes a las 8."),
    ("alarm", {"time": "a la una"}, [], [], "done", "Alarma puesta mañana a la una."),
    ("alarm", {"time": "dentro de 20 minutos"}, [], [], "done", "Alarma puesta a las 14 y 20."),
    ("alarm", {}, [], [], "missing_time", "¿Para qué hora pongo la alarma?"),
    ("reminder", {"reminder": "a las cinco de la tarde llamar a mi madre"}, [], [], "done",
     "Te recordaré llamar a tu madre a las 17."),
    ("reminder", {"reminder": "que llame a mamá mañana a las 9"}, [], [], "done",
     "Te recordaré que llames a mamá mañana a las 9."),
    ("reminder", {"reminder": "dentro de diez minutos mirar el horno"}, [], [], "done",
     "Te recordaré mirar el horno dentro de 10 minutos."),
    ("reminder", {"reminder": "comprar pan"}, [], [], "listed", "He añadido comprar pan a tus recordatorios."),
    ("reminder", {"reminder": "comprar pan mañana"}, [], [], "missing_time", "¿Cuándo te lo recuerdo?"),
    ("reminder", {"reminder": "a las cinco"}, [], [], "missing_reminder", "¿Qué quieres que te recuerde?"),
    ("alarm_status", {}, [SEVEN], [], "done", "Tienes una alarma mañana a las 7."),
    ("alarm_status", {}, [SEVEN, WEEKDAY, FAR], [], "done",
     "Tienes 3 alarmas: mañana a las 7, los días laborables a las 6 y 30 y el 30 de octubre a las 9."),
    ("alarm_status", {}, [], [], "no_alarms", "No hay ninguna alarma puesta."),
    ("reminder_status", {}, [], [CALL], "done", "Tienes un recordatorio: Llamar a mamá a las 17."),
    ("reminder_status", {}, [], [], "no_reminders", "No tienes recordatorios."),
    ("cancel_alarm", {"time": "siete"}, [SEVEN, WEEKDAY], [], "done", "He cancelado la alarma de mañana a las 7."),
    ("cancel_alarm", {"time": "las siete de la tarde"}, [SEVEN, SEVEN_PM], [], "done",
     "He cancelado la alarma de mañana a las 19."),
    ("cancel_alarm", {"time": "mañana"}, [SEVEN, MONDAY], [], "done", "He cancelado la alarma de mañana a las 7."),
    ("cancel_alarm", {"time": "las ocho"}, [SEVEN], [], "not_found",
     "No hay ninguna alarma a las 20. Tienes una alarma mañana a las 7."),
    ("cancel_alarm", {}, [SEVEN, WEEKDAY], [], "ambiguous",
     "¿Qué alarma? Tienes alarmas mañana a las 7 y los días laborables a las 6 y 30."),
    ("cancel_reminder", {"reminder": "de llamar a mamá"}, [], REMINDERS, "done",
     "He cancelado el recordatorio de las 17: Llamar a mamá."),
    ("cancel_reminder", {"reminder": "de sacar la basura el martes"}, [], REMINDERS, "done",
     "He cancelado el recordatorio del martes a las 8: Sacar la basura."),
    ("cancel_reminder", {"reminder": "de mañana"}, [], REMINDERS, "done",
     "He cancelado el recordatorio de mañana a las 9: Llamar al dentista."),
    ("cancel_reminder", {"reminder": "de las cinco"}, [], REMINDERS, "done",
     "He cancelado el recordatorio de las 17: Llamar a mamá."),
    ("cancel_reminder", {"reminder": "de llamar"}, [], REMINDERS, "ambiguous",
     "¿Qué recordatorio? Tienes Llamar a mamá a las 17 y Llamar al dentista mañana a las 9."),
    ("cancel_reminder", {"reminder": "de dar de comer al gato"}, [], [CALL], "not_found",
     "No hay ningún recordatorio así. Tienes un recordatorio: Llamar a mamá a las 17."),
]


@pytest.mark.parametrize(("operation", "slots", "alarms_set", "reminders", "outcome", "said"), SAID)
def test_what_is_said(operation, slots, alarms_set, reminders, outcome, said):
    plan = alarms.plan(operation, slots, NOW, alarms_set, reminders, todo=True)
    assert (plan.outcome, plan.speech) == (outcome, said)


def test_an_alarm_on_the_calendar():
    plan = alarms.plan("alarm", {"time": "mañana a las siete y media"}, NOW, [], [])
    assert plan.levels == {"brief": "Alarma puesta.", "specific": "Alarma puesta mañana a las 7 y 30.",
                           "verbose": "Alarma puesta mañana a las 7 y 30, dentro de 17 horas y 30 minutos."}
    assert plan.create == {"kind": "alarm", "summary": "Alarma", "start": NOW.replace(hour=7, minute=30) + timedelta(days=1),
                           "rrule": None}
    reminder = alarms.plan("reminder", {"reminder": "que llame a mamá mañana a las 9"}, NOW, [], [], todo=True)
    assert reminder.create["summary"] == "Que llames a mamá"


def test_which_is_asked():
    which = alarms.plan("cancel_alarm", {"time": "siete"}, NOW, [SEVEN, SEVEN_PM], [])
    assert which.question == "¿La alarma de mañana a las 7 o la alarma de mañana a las 19?"
    assert [c["label"] for c in which.choices] == ["la alarma de mañana a las 7", "la alarma de mañana a las 19"]
    assert alarms.plan("cancel_alarm", {}, NOW, [SEVEN, WEEKDAY], [], every=True).delete == [SEVEN, WEEKDAY]
    reminder = alarms.plan("cancel_reminder", {"reminder": "de llamar"}, NOW, [], REMINDERS)
    assert reminder.question == "¿Llamar a mamá a las 17 o Llamar al dentista mañana a las 9?"


def test_what_rings():
    assert spanish.alarm_due("Alarma", SEVEN.start) == "Son las 7."
    assert spanish.alarm_due("", NOW.replace(hour=1)) == "Es la una."
    assert spanish.alarm_due("Pastilla", NOW.replace(hour=13, minute=30)) == "Pastilla. Son las 13 y 30."
    assert spanish.reminder_due("Llamar a mamá.") == "Recordatorio: Llamar a mamá."


# ------------------------------------------------------- two commands at once

# (sentence, where it may split): "y" between commands, not within an amount.
SPLITS = [
    ("apaga la luz y enciende la tele", [(3, 4)]),
    ("bloquea la puerta y luego apaga las luces", [(3, 5)]),
    ("apaga la luz después bloquea la puerta", [(3, 4)]),
    ("y apaga la luz y", []),  # nothing on one side
    ("pon un temporizador de una hora y media", []),
    ("pon un temporizador de treinta y cinco minutos", []),
    ("pon un temporizador de cinco minutos y treinta segundos", []),
    ("pon una alarma a las siete y cuarto", []),
    ("pon una alarma a la una y media", []),
    ("pon un temporizador de una hora y una alarma a las siete", [(6, 7)]),
]


@pytest.mark.parametrize(("sentence", "splits"), SPLITS)
def test_where_a_sentence_may_split(sentence, splits):
    assert compound.splits(sentence.split()) == splits


@pytest.mark.parametrize(
    ("before", "after", "amount"),
    [
        ("una hora", "media", True),
        ("treinta", "cinco", True),
        ("1 hora", "30 segundos", True),
        ("las siete", "cuarto", True),
        ("una hora", "un cuarto", True),
        ("una hora", "una alarma", False),
        ("la luz", "la tele", False),
    ],
)
def test_within_an_amount(before, after, amount):
    assert joined.within_an_amount(before.split(), after.split()) is amount


@pytest.mark.parametrize(
    ("first", "second", "said"),
    [
        ("He apagado las luces.", "He apagado la tele.", "He apagado las luces y la tele."),
        ("He encendido las luces.", "He apagado la tele.", "He encendido las luces y he apagado la tele."),
        ("Luces apagadas en la cocina.", "Luces apagadas en el dormitorio.",
         "Luces apagadas en la cocina y en el dormitorio."),
        ("He encendido Lámpara de pie.", "He encendido Lámpara pequeña.", "He encendido Lámpara de pie y Lámpara pequeña."),
        ("Bloqueando Puerta principal.", "Luces apagadas.", "Bloqueando Puerta principal y luces apagadas."),
        ("He apagado la tele.", "He apagado Iluminación del jardín.", "He apagado la tele e Iluminación del jardín."),
        ("Luces encendidas.", "Luces encendidas.", "Luces encendidas."),
    ],
)
def test_what_both_say_is_one_sentence(first, second, said):
    assert joined.both(first, second) == said


def test_what_a_second_command_acts_on_too():
    assert joined.devices(["Lámpara de pie"]) == "la Lámpara de pie"
    assert joined.devices(["Lámpara de pie", "Ventilador de techo"]) == "la Lámpara de pie y el Ventilador de techo"


def test_what_both_say():
    assert compound.both("Luces encendidas.", "") == "Luces encendidas."
    assert compound.alone("cancelar todos los temporizadores") == "Para cancelar todos los temporizadores, pídemelo por separado."
    assert compound.joiners() == ("y luego", "y después", "y", "e", "luego", "después")
