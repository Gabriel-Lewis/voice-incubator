"""Alarms and timed reminders in Italian: when the Italian calendar words
(voice_incubator/languages/it/calendar.py) read one to be, and what is said
about them (voice_incubator/alarms.py). Each case is a row: a native speaker
reviewing adds one where Italian is said otherwise."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from voice_incubator import alarms, languages

TZ = ZoneInfo("Europe/Rome")
NOW = datetime(2026, 10, 21, 14, 0, tzinfo=TZ)  # a Wednesday afternoon
WEEKDAYS = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"


@pytest.fixture(autouse=True)
def italian():
    languages.use("it")
    yield
    languages.use(languages.DEFAULT)


def calendar():
    return languages.current().calendar


# (what was said after the keyword, an alarm, its first time, how it repeats, what was said besides)
WHEN = [
    # A clock time: the next to come round, morning or afternoon.
    ("alle sette e mezza", True, "2026-10-21 19:30", None, ""),
    ("sette e mezza", True, "2026-10-21 19:30", None, ""),
    ("alle sette in punto", True, "2026-10-21 19:00", None, ""),
    ("le otto meno un quarto", True, "2026-10-21 19:45", None, ""),
    ("alle sei e un quarto", True, "2026-10-21 18:15", None, ""),
    ("all'una", True, "2026-10-22 01:00", None, ""),
    # On a 24-hour clock, or with the part of the day.
    ("alle diciannove e trenta", True, "2026-10-21 19:30", None, ""),
    ("alle 19.30", True, "2026-10-21 19:30", None, ""),
    ("alle ore 17", True, "2026-10-21 17:00", None, ""),
    ("alle dieci di sera", True, "2026-10-21 22:00", None, ""),
    ("alle sei di mattina", True, "2026-10-22 06:00", None, ""),
    ("a mezzogiorno", True, "2026-10-22 12:00", None, ""),
    ("a mezzanotte", True, "2026-10-22 00:00", None, ""),
    # A day, before or after the time; another day without the part of the
    # day: an alarm in the morning.
    ("sette di domani", True, "2026-10-22 07:00", None, ""),
    ("domani alle sette", True, "2026-10-22 07:00", None, ""),
    ("per le sei e mezza di domani mattina", True, "2026-10-22 06:30", None, ""),
    ("dopodomani alle otto", True, "2026-10-23 08:00", None, ""),
    ("sabato alle sette", True, "2026-10-24 07:00", None, ""),
    ("lunedì prossimo alle sette", True, "2026-10-26 07:00", None, ""),
    ("mercoledì alle 10", True, "2026-10-28 10:00", None, ""),  # today's gone: next week's
    ("stasera alle dieci", True, "2026-10-21 22:00", None, ""),
    ("stanotte alle tre", True, "2026-10-22 03:00", None, ""),
    ("tra tre giorni alle otto", True, "2026-10-24 08:00", None, ""),
    # Repeating.
    ("ogni giorno feriale alle sei e quarantacinque", True, "2026-10-22 06:45", WEEKDAYS, ""),
    ("alle sette nei giorni feriali", True, "2026-10-22 07:00", WEEKDAYS, ""),
    ("tutti i giorni alle sette", True, "2026-10-22 07:00", "FREQ=DAILY", ""),
    ("ogni martedì e giovedì alle sette", True, "2026-10-22 07:00", "FREQ=WEEKLY;BYDAY=TU,TH", ""),
    ("ogni fine settimana alle nove", True, "2026-10-24 09:00", "FREQ=WEEKLY;BYDAY=SA,SU", ""),
    # A weekday with its article: every one of them; "per il" one: that one.
    ("il sabato alle otto", True, "2026-10-24 08:00", "FREQ=WEEKLY;BYDAY=SA", ""),
    ("il martedì e il giovedì alle sette", True, "2026-10-22 07:00", "FREQ=WEEKLY;BYDAY=TU,TH", ""),
    ("tutte le domeniche alle nove", True, "2026-10-25 09:00", "FREQ=WEEKLY;BYDAY=SU", ""),
    ("per il sabato alle otto", True, "2026-10-24 08:00", None, ""),
    # From now.
    ("tra venti minuti", True, "2026-10-21 14:20", None, ""),
    ("fra un'ora e mezza", True, "2026-10-21 15:30", None, ""),
    ("tra mezz'ora", True, "2026-10-21 14:30", None, ""),
    ("tra un quarto d'ora", True, "2026-10-21 14:15", None, ""),
    ("tra otto ore", True, "2026-10-21 22:00", None, ""),
    # A reminder: the time before or after what it is about; another day
    # from 7 to 11 in the morning, else the afternoon.
    ("alle 17 di chiamare la mamma", False, "2026-10-21 17:00", None, "chiamare la mamma"),
    ("di chiamare mia mamma alle cinque", False, "2026-10-21 17:00", None, "di chiamare mia mamma"),
    ("di chiamare la mamma alle cinque del pomeriggio", False, "2026-10-21 17:00", None, "di chiamare la mamma"),
    ("domani alle nove di chiamare il dentista", False, "2026-10-22 09:00", None, "chiamare il dentista"),
    ("che arriva l'idraulico venerdì alle tre", False, "2026-10-23 15:00", None, "che arriva l'idraulico"),
    ("che venerdì alle tre arriva l'idraulico", False, "2026-10-23 15:00", None, "che arriva l'idraulico"),
    ("di portare fuori la spazzatura ogni martedì alle sette di sera", False, "2026-10-27 19:00",
     "FREQ=WEEKLY;BYDAY=TU", "di portare fuori la spazzatura"),
    ("tra dieci minuti di controllare il forno", False, "2026-10-21 14:10", None, "di controllare il forno"),
    ("il martedì alle 19 di portare fuori la spazzatura", False, "2026-10-27 19:00", "FREQ=WEEKLY;BYDAY=TU",
     "portare fuori la spazzatura"),
    ("di portare fuori la spazzatura il martedì alle 19", False, "2026-10-27 19:00", "FREQ=WEEKLY;BYDAY=TU",
     "di portare fuori la spazzatura"),
    ("di chiamare il dentista martedì alle 9", False, "2026-10-27 09:00", None, "di chiamare il dentista"),
    # A length that is the reminder's, before its time.
    ("di riposare per dieci minuti alle cinque del pomeriggio", False, "2026-10-21 17:00", None,
     "di riposare per dieci minuti"),
]


@pytest.mark.parametrize(("said", "alarm", "start", "rrule", "rest"), WHEN)
def test_when(said, alarm, start, rrule, rest):
    found = calendar().when(said, NOW, alarm=alarm)
    assert found is not None
    assert found.start == datetime.fromisoformat(start).replace(tzinfo=TZ)
    assert (found.rrule, found.rest) == (rrule, rest)


# What speech-to-text may make of it: (said, alarm, start, relative)
HEARD = [
    ("otto ore", True, "2026-10-21 22:00", True),  # the "tra" dropped
    ("dieci minuti", True, "2026-10-21 14:10", True),
    ("dopo domani alle otto", True, "2026-10-23 08:00", False),
    ("tra un' ora", True, "2026-10-21 15:00", True),
    ("tra mezz' ora", True, "2026-10-21 14:30", True),
    ("alle sette, domani", True, "2026-10-22 07:00", False),
    ("lunedi alle sette", True, "2026-10-26 07:00", False),  # without its accent
]


@pytest.mark.parametrize(("said", "alarm", "start", "relative"), HEARD)
def test_what_speech_to_text_makes_of_it(said, alarm, start, relative):
    found = calendar().when(said, NOW, alarm=alarm)
    assert found is not None
    assert found.start == datetime.fromisoformat(start).replace(tzinfo=TZ) and found.relative == relative


@pytest.mark.parametrize("said", ["di chiamare la mamma", "", "di comprare il latte domani", "ogni lunedì",
                                  "per dieci minuti"])
def test_no_time_is_none(said):
    assert calendar().when(said, NOW) is None


@pytest.mark.parametrize(
    ("said", "wants"),
    [("di comprare il latte domani", True), ("ogni lunedì", True), ("venerdì", True), ("stasera", True),
     ("di comprare il latte", False)],
)
def test_a_day_without_a_time_asks_for_one(said, wants):
    assert calendar().wants_time(said) == wants


@pytest.mark.parametrize(
    ("said", "days"),
    [("di domani", 1), ("per domani", 1), ("di dopodomani", 2), ("di sabato", 3), ("di oggi", 0), ("di chiamare", None)],
)
def test_the_day_named(said, days):
    found = calendar().day(said, NOW)
    assert found == (None if days is None else (NOW + timedelta(days=days)).date())


@pytest.mark.parametrize(
    ("said", "back"),
    [
        ("di chiamare mia mamma", "chiamare tua mamma"),
        ("che io e mia sorella siamo fuori", "tu e tua sorella siamo fuori"),
        ("d'innaffiare le piante", "innaffiare le piante"),
        ("comprare il latte", "comprare il latte"),
    ],
)
def test_what_is_said_back(said, back):
    assert calendar().what(said) == back


@pytest.mark.parametrize(
    ("said", "words"),
    [("il mio promemoria di chiamare la mamma domani", ["chiamare", "mamma"]), ("dell'idraulico", ["idraulico"])],
)
def test_what_a_reminder_is_about(said, words):
    assert calendar().about(said) == words


def _event(uid, hour, minute=0, days=1, kind="alarm", rrule=None, summary="Sveglia"):
    start = NOW.replace(hour=hour, minute=minute) + timedelta(days=days)
    return alarms.Event(uid, start, summary, kind, rrule=rrule)


SEVEN = _event("1", 7)
SEVEN_PM = _event("2", 19)
EVERY_WEEKDAY = _event("3", 6, 30, rrule=WEEKDAYS)
CALL = _event("4", 17, days=0, kind="reminder", summary="Chiamare tua mamma")
DENTIST = _event("5", 9, days=1, kind="reminder", summary="Chiamare il dentista")
GARBAGE = _event("6", 8, days=6, kind="reminder", summary="Portare fuori la spazzatura")
REMINDERS = [CALL, DENTIST, GARBAGE]

# (operation, slots, alarms, reminders, outcome, what is said, what it deletes)
PLANS = [
    ("alarm", {"time": "sette e mezza domani"}, [], [], "done", "Sveglia impostata per le 7 e 30 di domani.", []),
    ("alarm", {"time": "ogni giorno feriale alle sei e quarantacinque"}, [], [], "done",
     "Sveglia impostata per le 6 e 45 nei giorni feriali.", []),
    ("alarm", {"time": "mezzogiorno"}, [], [], "done", "Sveglia impostata per mezzogiorno di domani.", []),
    ("alarm", {}, [], [], "missing_time", "Per che ora devo mettere la sveglia?", []),
    ("reminder", {"reminder": "alle 17 di chiamare mia mamma"}, [], [], "done",
     "Ti ricorderò di chiamare tua mamma alle 17.", []),
    ("reminder", {"reminder": "che arriva l'idraulico venerdì alle tre"}, [], [], "done",
     "Ti ricorderò che arriva l'idraulico alle 15 di venerdì.", []),
    ("reminder", {"reminder": "tra dieci minuti di controllare il forno"}, [], [], "done",
     "Ti ricorderò di controllare il forno tra 10 minuti.", []),
    ("reminder", {"reminder": "di comprare il latte domani"}, [], [], "missing_time", "Quando te lo devo ricordare?", []),
    ("reminder", {"reminder": "alle 5"}, [], [], "missing_reminder", "Cosa ti devo ricordare?", []),
    ("cancel_alarm", {"time": "delle sette"}, [SEVEN, EVERY_WEEKDAY], [], "done",
     "Ho annullato la sveglia delle 7 di domani.", [SEVEN]),
    ("cancel_alarm", {"time": "sette di sera"}, [SEVEN, SEVEN_PM], [], "done",
     "Ho annullato la sveglia delle 19 di domani.", [SEVEN_PM]),
    ("cancel_alarm", {"time": "delle sette"}, [SEVEN, SEVEN_PM], [], "ambiguous",
     "Quale sveglia? Hai quella delle 7 di domani e quella delle 19 di domani.", []),
    ("cancel_alarm", {"time": "delle otto"}, [SEVEN], [], "not_found",
     "Non c'è nessuna sveglia alle 20. Hai una sveglia alle 7 di domani.", []),
    ("cancel_alarm", {"time": "domani"}, [SEVEN, _event("7", 7, days=5)], [], "done",
     "Ho annullato la sveglia delle 7 di domani.", [SEVEN]),
    ("cancel_alarm", {}, [], [], "no_alarms", "Non ci sono sveglie.", []),
    ("cancel_reminder", {"reminder": "di chiamare mia mamma"}, [], REMINDERS, "done",
     "Ho annullato il promemoria delle 17: Chiamare tua mamma.", [CALL]),
    ("cancel_reminder", {"reminder": "del dentista"}, [], REMINDERS, "done",
     "Ho annullato il promemoria delle 9 di domani: Chiamare il dentista.", [DENTIST]),
    ("cancel_reminder", {"reminder": "di portare fuori la spazatura"}, [], REMINDERS, "done",
     "Ho annullato il promemoria delle 8 di martedì: Portare fuori la spazzatura.", [GARBAGE]),
    ("cancel_reminder", {"reminder": "delle cinque"}, [], REMINDERS, "done",
     "Ho annullato il promemoria delle 17: Chiamare tua mamma.", [CALL]),
    ("cancel_reminder", {"reminder": "di domani"}, [], REMINDERS, "done",
     "Ho annullato il promemoria delle 9 di domani: Chiamare il dentista.", [DENTIST]),
    ("cancel_reminder", {"reminder": "di chiamare"}, [], REMINDERS, "ambiguous",
     "Quale promemoria? Hai Chiamare tua mamma alle 17 e Chiamare il dentista alle 9 di domani.", []),
    ("cancel_reminder", {"reminder": "di dare da mangiare al gatto"}, [], [CALL], "not_found",
     "Non c'è nessun promemoria così. Hai un promemoria: Chiamare tua mamma alle 17.", []),
    ("cancel_reminder", {}, [], [], "no_reminders", "Non hai promemoria.", []),
    ("alarm_status", {}, [SEVEN], [], "done", "Hai una sveglia alle 7 di domani.", []),
    ("alarm_status", {}, [SEVEN, EVERY_WEEKDAY], [], "done",
     "Hai 2 sveglie: alle 7 di domani e alle 6 e 30 nei giorni feriali.", []),
    ("alarm_status", {}, [], [], "no_alarms", "Non ci sono sveglie.", []),
    ("reminder_status", {}, [], [CALL, DENTIST], "done",
     "Hai 2 promemoria: Chiamare tua mamma alle 17 e Chiamare il dentista alle 9 di domani.", []),
    ("reminder_status", {}, [], [], "no_reminders", "Non hai promemoria.", []),
]


@pytest.mark.parametrize(("operation", "slots", "alarms_set", "reminders", "outcome", "said", "deleted"), PLANS)
def test_what_each_command_does_and_says(operation, slots, alarms_set, reminders, outcome, said, deleted):
    plan = alarms.plan(operation, slots, NOW, alarms_set, reminders)
    assert (plan.outcome, plan.speech, plan.delete) == (outcome, said, deleted)


def test_a_reminder_without_a_time_goes_on_the_to_do_list():
    listed = alarms.plan("reminder", {"reminder": "di comprare il latte"}, NOW, [], [], todo=True)
    assert (listed.outcome, listed.todo, listed.speech) == ("listed", "comprare il latte",
                                                            "Ho aggiunto comprare il latte ai tuoi promemoria.")
    assert alarms.plan("reminder", {"reminder": "di comprare il latte"}, NOW, [], []).outcome == "missing_time"


def test_what_is_put_on_the_calendar():
    plan = alarms.plan("reminder", {"reminder": "alle 17 di chiamare mia mamma"}, NOW, [], [])
    assert plan.create == {"kind": "reminder", "summary": "Chiamare tua mamma", "start": NOW.replace(hour=17),
                           "rrule": None}
    plan = alarms.plan("alarm", {"time": "sette e mezza domani"}, NOW, [], [])
    assert plan.create["summary"] == "Sveglia"
    assert plan.levels == {
        "brief": "Sveglia impostata.", "specific": "Sveglia impostata per le 7 e 30 di domani.",
        "verbose": "Sveglia impostata per le 7 e 30 di domani, tra 17 ore e 30 minuti.",
    }


def test_which_is_asked():
    which = alarms.plan("cancel_alarm", {}, NOW, [SEVEN, EVERY_WEEKDAY], [])
    assert which.question == "Quella delle 7 di domani o quella delle 6 e 30 nei giorni feriali?"
    assert [c["label"] for c in which.choices] == ["la sveglia delle 7 di domani", "la sveglia delle 6 e 30 nei giorni feriali"]
    assert alarms.plan("cancel_alarm", {}, NOW, [SEVEN, EVERY_WEEKDAY], [], every=True).delete == [SEVEN, EVERY_WEEKDAY]


@pytest.mark.parametrize(
    ("start", "rrule", "said"),
    [
        (NOW.replace(hour=19, minute=30), None, "le 19 e 30"),
        (NOW.replace(hour=13, minute=5) + timedelta(days=1), None, "le 13 e 5 di domani"),
        (NOW.replace(hour=1, minute=5) + timedelta(days=1), None, "l'una e 5 di domani"),
        (NOW.replace(hour=12, minute=0) + timedelta(days=1), None, "mezzogiorno di domani"),
        (NOW.replace(hour=9) + timedelta(days=2), None, "le 9 di venerdì"),
        (NOW.replace(hour=9) + timedelta(days=9), None, "le 9 del 30 ottobre"),
        (NOW.replace(hour=9, day=8, month=11), None, "le 9 dell'8 novembre"),
        (NOW.replace(hour=9, day=1, month=12), None, "le 9 del primo dicembre"),
        (NOW.replace(hour=7) + timedelta(days=1), "FREQ=DAILY", "le 7 ogni giorno"),
        (NOW.replace(hour=7) + timedelta(days=3), "FREQ=WEEKLY;BYDAY=SA,SU", "le 7 nel fine settimana"),
        (NOW.replace(hour=7) + timedelta(days=6), "FREQ=WEEKLY;BYDAY=TU,TH", "le 7 ogni martedì e giovedì"),
    ],
)
def test_when_it_is_said(start, rrule, said):
    assert calendar().said_when(start, rrule, NOW) == said


@pytest.mark.parametrize(
    ("title", "hour", "minute", "said"),
    [("Sveglia", 7, 30, "Sono le 7 e 30."), ("", 1, 0, "È l'una."), ("medicine", 12, 0, "Medicine. È mezzogiorno.")],
)
def test_what_an_alarm_says_when_it_rings(title, hour, minute, said):
    assert calendar().alarm_due(title, NOW.replace(hour=hour, minute=minute)) == said


def test_what_a_reminder_says_when_it_is_due():
    assert calendar().reminder_due("Chiamare tua mamma.") == "Promemoria: Chiamare tua mamma."
