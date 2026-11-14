"""Alarms and timed reminders in Dutch: when the Dutch calendar words
(voice_incubator/languages/nl/calendar.py) read them as being, what they say
back, and what each command does with them (voice_incubator/alarms.py).

Each table is a list of cases: add a row to check another way of saying it."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from voice_incubator import alarms, languages

TZ = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 10, 21, 14, 0, tzinfo=TZ)  # a Wednesday afternoon


@pytest.fixture(autouse=True)
def dutch():
    languages.use("nl")
    yield
    languages.use(languages.DEFAULT)


def calendar():
    return languages.current().calendar


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=TZ)


WEEKDAYS = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"


@pytest.mark.parametrize(
    ("said", "alarm", "start", "rrule", "rest"),
    [
        # Alarms: a clock time, the next one to come round without 's
        # ochtends or 's avonds; on another day, the morning.
        ("om zeven uur", True, "2026-10-21 19:00", None, ""),
        ("om half acht", True, "2026-10-21 19:30", None, ""),  # half: the hour to come
        ("morgen om half acht", True, "2026-10-22 07:30", None, ""),
        ("morgen om kwart over zes", True, "2026-10-22 06:15", None, ""),
        ("voor morgen om kwart voor zeven", True, "2026-10-22 06:45", None, ""),
        ("morgen om tien voor half acht", True, "2026-10-22 07:20", None, ""),
        ("morgen om tien over half acht", True, "2026-10-22 07:40", None, ""),
        ("morgen om zeven uur 's avonds", True, "2026-10-22 19:00", None, ""),
        ("morgen om acht uur 's ochtends", True, "2026-10-22 08:00", None, ""),
        ("om twaalf uur 's middags", True, "2026-10-22 12:00", None, ""),
        ("om tien uur vanavond", True, "2026-10-21 22:00", None, ""),
        ("om drie uur 's nachts", True, "2026-10-22 03:00", None, ""),
        ("middernacht", True, "2026-10-22 00:00", None, ""),
        ("om 19.30 uur", True, "2026-10-21 19:30", None, ""),
        ("om 6:45", True, "2026-10-21 18:45", None, ""),
        ("zaterdag om zeven uur", True, "2026-10-24 07:00", None, ""),
        ("woensdag om negen uur", True, "2026-10-28 09:00", None, ""),  # today's gone: next week's
        ("overmorgen om acht uur", True, "2026-10-23 08:00", None, ""),
        ("over drie dagen om acht uur", True, "2026-10-24 08:00", None, ""),
        ("morgen om zeven uur wakker", True, "2026-10-22 07:00", None, "wakker"),
        # Repeating.
        ("voor elke werkdag om kwart voor zeven", True, "2026-10-22 06:45", WEEKDAYS, ""),
        ("elke dag om zeven uur", True, "2026-10-22 07:00", "FREQ=DAILY", ""),
        ("elke maandag en woensdag om zeven uur", True, "2026-10-26 07:00", "FREQ=WEEKLY;BYDAY=MO,WE", ""),
        ("in het weekend om negen uur", True, "2026-10-24 09:00", "FREQ=WEEKLY;BYDAY=SA,SU", ""),
        # From now: "over", and "uur" as hours only then.
        ("over twintig minuten", True, "2026-10-21 14:20", None, ""),
        ("over acht uur", True, "2026-10-21 22:00", None, ""),
        ("over een kwartier", True, "2026-10-21 14:15", None, ""),
        ("over anderhalf uur", True, "2026-10-21 15:30", None, ""),
        ("over een uur en tien minuten", True, "2026-10-21 15:10", None, ""),
        # Reminders: the time first, last, or within a clause; what is left
        # is what to remind of. Another day without a part of it: 7 to 11 in
        # the morning, else the afternoon.
        ("om vijf uur 's middags eraan om mama te bellen", False, "2026-10-21 17:00", None, "eraan om mama te bellen"),
        ("eraan om mama te bellen om vijf uur", False, "2026-10-21 17:00", None, "eraan om mama te bellen"),
        ("morgen om negen uur eraan om de tandarts te bellen", False, "2026-10-22 09:00", None,
         "eraan om de tandarts te bellen"),
        ("vrijdag om drie uur aan de loodgieter", False, "2026-10-23 15:00", None, "aan de loodgieter"),
        ("elke dinsdag om zeven uur 's avonds aan de vuilnisbak", False, "2026-10-27 19:00", "FREQ=WEEKLY;BYDAY=TU",
         "aan de vuilnisbak"),
        ("over tien minuten aan de oven", False, "2026-10-21 14:10", None, "aan de oven"),
        ("eraan dat de loodgieter vrijdag om drie uur komt", False, "2026-10-23 15:00", None, "eraan dat de loodgieter komt"),
    ],
)
def test_when(said, alarm, start, rrule, rest):
    found = calendar().when(said, NOW, alarm=alarm)
    assert found is not None
    assert (found.start, found.rrule, found.rest) == (at(start), rrule, rest)


@pytest.mark.parametrize(
    ("said", "alarm", "start", "rest"),
    [
        # How speech-to-text may write it.
        ("om halfacht", True, "2026-10-21 19:30", ""),
        ("om kwartover zes", True, "2026-10-21 18:15", ""),
        ("morgenochtend om zeven uur", True, "2026-10-22 07:00", ""),
        ("maandagavond om zeven uur", False, "2026-10-26 19:00", ""),
        ("om zeven uur savonds", True, "2026-10-21 19:00", ""),
        ("om 19.30", True, "2026-10-21 19:30", ""),
        # "Half een" is 12:30 (or 0:30, whichever comes first).
        ("morgen om half een", True, "2026-10-22 12:30", ""),
        # A length alone is from now: the free text's edge may drop the "over".
        ("twintig minuten", True, "2026-10-21 14:20", ""),
        # A length that is the reminder's, before its time.
        ("om tien minuten te rusten om vijf uur", False, "2026-10-21 17:00", "om tien minuten te rusten"),
        # "Om" before what to do, after the time.
        ("om zeven om mama te bellen", False, "2026-10-21 19:00", "om mama te bellen"),
    ],
)
def test_what_speech_to_text_makes_of_it(said, alarm, start, rest):
    found = calendar().when(said, NOW, alarm=alarm)
    assert found is not None
    assert (found.start, found.rest) == (at(start), rest)


@pytest.mark.parametrize(
    "said",
    [
        "", "eraan om melk te kopen", "aan de tandarts", "morgen", "elke maandag",
        # How many, not when.
        "om drie pakken melk te kopen", "om een half brood te kopen",
    ],
)
def test_no_time_is_none(said):
    assert calendar().when(said, NOW) is None
    assert calendar().when(said, NOW, alarm=True) is None


@pytest.mark.parametrize(
    ("said", "wants"),
    [("morgen", True), ("op vrijdag", True), ("elke maandag", True), ("vanavond", True), ("om melk te kopen", False)],
)
def test_a_day_without_a_time_asks_for_one(said, wants):
    assert calendar().wants_time(said) is wants


@pytest.mark.parametrize(
    ("said", "day"),
    [("van morgen", "2026-10-22"), ("op vrijdag", "2026-10-23"), ("overmorgen", "2026-10-23"), ("om mama te bellen", None)],
)
def test_the_day_said(said, day):
    found = calendar().day(said, NOW)
    assert (found.isoformat() if found else None) == day


@pytest.mark.parametrize(
    ("said", "back"),
    [
        ("eraan om mama te bellen", "mama bellen"),
        ("om mijn moeder te bellen", "je moeder bellen"),
        ("aan de tandarts", "de tandarts"),
        ("om de kamer op te ruimen", "de kamer opruimen"),
        ("om de vuilnisbak buiten te zetten", "de vuilnisbak buitenzetten"),
        ("om naar buiten te gaan", "naar buiten gaan"),
        ("eraan dat ik naar de dokter ga", "je naar de dokter gaat"),
        ("dat de loodgieter komt", "de loodgieter komt"),
    ],
)
def test_what_is_said_back(said, back):
    assert calendar().what(said) == back


@pytest.mark.parametrize(
    ("said", "words"),
    [("mijn herinnering om mama te bellen morgen", ["mama", "bellen"]), ("Mama bellen", ["mama", "bellen"])],
)
def test_what_a_reminder_is_about(said, words):
    assert calendar().about(said) == words


@pytest.mark.parametrize(
    ("start", "rrule", "said"),
    [
        ("2026-10-21 19:30", None, "19 uur 30"),
        ("2026-10-22 07:00", None, "morgen om 7 uur"),
        ("2026-10-23 09:00", None, "vrijdag om 9 uur"),
        ("2026-11-02 09:00", None, "op 2 november om 9 uur"),
        ("2026-10-22 06:45", WEEKDAYS, "elke werkdag om 6 uur 45"),
        ("2026-10-24 09:00", "FREQ=WEEKLY;BYDAY=SA,SU", "elk weekend om 9 uur"),
        ("2026-10-26 07:00", "FREQ=WEEKLY;BYDAY=MO,WE", "elke maandag en woensdag om 7 uur"),
        ("2026-10-22 00:00", None, "morgen om middernacht"),
    ],
)
def test_said_when(start, rrule, said):
    assert calendar().said_when(at(start), rrule, NOW) == said


def _event(uid, hour, minute=0, days=1, kind="alarm", rrule=None, summary="Wekker"):
    start = NOW.replace(hour=hour, minute=minute) + timedelta(days=days)
    return alarms.Event(uid, start, summary, kind, rrule=rrule)


def test_alarm():
    plan = alarms.plan("alarm", {"time": "morgen om half acht"}, NOW, [], [])
    assert plan.outcome == "done" and plan.speech == "Wekker gezet voor morgen om 7 uur 30."
    assert plan.levels["verbose"] == "Wekker gezet voor morgen om 7 uur 30, over 17 uur en 30 minuten."
    assert plan.create == {"kind": "alarm", "summary": "Wekker", "start": at("2026-10-22 07:30"), "rrule": None}
    missing = alarms.plan("alarm", {}, NOW, [], [])
    assert missing.outcome == "missing_time" and missing.speech == "Voor hoe laat moet ik de wekker zetten?"


def test_reminder_with_or_without_a_time():
    plan = alarms.plan("reminder", {"reminder": "om vijf uur eraan om mijn moeder te bellen"}, NOW, [], [], todo=True)
    assert plan.outcome == "done" and plan.create["summary"] == "Je moeder bellen"
    assert plan.speech == "Ik herinner je om 17 uur: je moeder bellen."
    soon = alarms.plan("reminder", {"reminder": "over tien minuten aan de oven"}, NOW, [], [], todo=True)
    assert soon.speech == "Ik herinner je over 10 minuten: de oven." and soon.create["start"] == at("2026-10-21 14:10")
    # Without a time: on the to-do list, if there is one; else it asks when.
    listed = alarms.plan("reminder", {"reminder": "eraan om melk te kopen"}, NOW, [], [], todo=True)
    assert listed.outcome == "listed" and listed.todo == "melk kopen" and listed.create is None
    assert listed.speech == "Melk kopen toegevoegd aan je herinneringen."
    assert alarms.plan("reminder", {"reminder": "eraan om melk te kopen"}, NOW, [], []).outcome == "missing_time"
    # A day but no time asks for one rather than listing it.
    assert alarms.plan("reminder", {"reminder": "morgen aan de melk"}, NOW, [], [], todo=True).outcome == "missing_time"
    assert alarms.plan("reminder", {"reminder": "om vijf uur"}, NOW, [], [], todo=True).outcome == "missing_reminder"


def test_cancel_picks_the_alarm():
    seven, seven_pm = _event("1", 7), _event("2", 19)
    weekdays = _event("3", 6, 30, rrule=WEEKDAYS)
    # Without 's ochtends or 's avonds, either.
    plan = alarms.plan("cancel_alarm", {"time": "zeven uur"}, NOW, [seven, weekdays], [])
    assert plan.outcome == "done" and plan.delete == [seven] and plan.speech == "Wekker voor morgen om 7 uur geannuleerd."
    assert alarms.plan("cancel_alarm", {"time": "zeven uur"}, NOW, [seven, seven_pm], []).outcome == "ambiguous"
    assert alarms.plan("cancel_alarm", {"time": "zeven uur 's avonds"}, NOW, [seven, seven_pm], []).delete == [seven_pm]
    missing = alarms.plan("cancel_alarm", {"time": "acht uur"}, NOW, [seven], [])
    assert missing.outcome == "not_found" and missing.speech.startswith("Er is geen wekker voor 20 uur.")
    which = alarms.plan("cancel_alarm", {}, NOW, [seven, weekdays], [])
    assert which.outcome == "ambiguous" and [c["id"] for c in which.choices] == ["1", "3"]
    assert which.question == "De wekker voor morgen om 7 uur of elke werkdag om 6 uur 30?"
    assert alarms.plan("cancel_alarm", {}, NOW, [seven, weekdays], [], every=True).delete == [seven, weekdays]
    assert alarms.plan("cancel_alarm", {"time": "morgen"}, NOW, [seven, _event("4", 7, days=5)], []).delete == [seven]
    assert alarms.plan("cancel_alarm", {}, NOW, [], []).speech == "Er zijn geen wekkers gezet."


def test_cancel_picks_the_reminder():
    call = _event("1", 17, days=0, kind="reminder", summary="Je moeder bellen")
    dentist = _event("2", 9, days=1, kind="reminder", summary="De tandarts bellen")
    bins = _event("3", 8, days=6, kind="reminder", summary="De vuilnisbak buitenzetten")
    every = [call, dentist, bins]

    def cancel(text, reminders=every):
        return alarms.plan("cancel_reminder", {"reminder": text} if text is not None else {}, NOW, [], reminders)

    # By what it is about, as said ("mijn" for "je"), or close to it.
    assert cancel("om mijn moeder te bellen").delete == [call]
    assert cancel("over de tandarts").delete == [dentist]
    assert cancel("om de vuilnisbak buiten te zette").delete == [bins]
    # By when: a time, a day.
    assert cancel("vijf uur").delete == [call]
    assert cancel("morgen").delete == [dentist]
    # Both "bellen"s fit: it asks which.
    assert cancel("om te bellen").outcome == "ambiguous"
    assert cancel(None).outcome == "ambiguous"
    assert cancel(None, [call]).delete == [call]
    missing = cancel("om de kat te voeren")
    assert missing.outcome == "not_found" and missing.speech.startswith("Zo'n herinnering heb ik niet gevonden.")
    assert cancel("om mama te bellen", []).speech == "Je hebt geen herinneringen."
    assert cancel("om mijn moeder te bellen").speech == "Herinnering om 17 uur geannuleerd: Je moeder bellen."


def test_status():
    seven, weekdays = _event("1", 7), _event("2", 6, 30, rrule=WEEKDAYS)
    assert alarms.plan("alarm_status", {}, NOW, [seven], []).speech == "Je hebt een wekker voor morgen om 7 uur."
    assert alarms.plan("alarm_status", {}, NOW, [seven, weekdays], []).speech == (
        "Je hebt 2 wekkers: morgen om 7 uur en elke werkdag om 6 uur 30.")
    call = _event("3", 17, days=0, kind="reminder", summary="Mama bellen")
    assert alarms.plan("reminder_status", {}, NOW, [], [call]).speech == "Je hebt één herinnering: Mama bellen om 17 uur."
    assert alarms.plan("reminder_status", {}, NOW, [], []).outcome == "no_reminders"


@pytest.mark.parametrize(
    ("title", "said"),
    [("Wekker", "Het is 7 uur 30."), ("", "Het is 7 uur 30."), ("pillen innemen", "Pillen innemen. Het is 7 uur 30.")],
)
def test_what_rings(title, said):
    assert calendar().alarm_due(title, at("2026-10-22 07:30")) == said
    assert calendar().reminder_due("Mama bellen.") == "Herinnering: Mama bellen."


def test_the_uis_examples_are_dutch():
    """What the web UI shows each outcome saying, made from the pack's EXAMPLES."""
    said = alarms.outcome_examples()
    assert all(text for outcomes in said.values() for text in outcomes.values()), said
    assert said["reminder"]["done"] == "Ik herinner je om 17 uur: mama bellen."
    assert said["cancel_reminder"]["done"] == "Herinnering om 17 uur geannuleerd: Mama bellen."
