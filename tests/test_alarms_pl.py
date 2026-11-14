"""Alarms and timed reminders in Polish: when the calendar reads one for --
from what was said, as a speech-to-text writes it -- and what the app says
about them (voice_incubator/languages/pl/calendar.py, through
voice_incubator/alarms.py). Rows are (what was said, ..., what it must be):
add one for each phrasing a speaker uses that should work."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from voice_incubator import alarms, languages

TZ = ZoneInfo("Europe/Warsaw")
NOW = datetime(2026, 10, 21, 14, 0, tzinfo=TZ)  # a Wednesday afternoon

WEEKDAYS = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"


@pytest.fixture(autouse=True)
def polish():
    languages.use("pl")
    yield
    languages.use(languages.DEFAULT)


def calendar():
    return languages.current().calendar


@pytest.mark.parametrize(
    ("said", "alarm", "start", "rrule", "rest"),
    [
        # A clock time: its hour's ordinal, in its case.
        ("na jutro na siódmą rano", True, "2026-10-22 07:00", None, ""),
        ("na siódmą trzydzieści", True, "2026-10-21 19:30", None, ""),  # the next 7:30 to come round
        ("o dziewiętnastej", True, "2026-10-21 19:00", None, ""),
        ("o 7:30", True, "2026-10-21 19:30", None, ""),
        ("na godzinę siódmą", True, "2026-10-21 19:00", None, ""),
        ("o siódmej trzydzieści wieczorem", True, "2026-10-21 19:30", None, ""),
        ("jedenasta w nocy", True, "2026-10-21 23:00", None, ""),
        ("o północy", True, "2026-10-22 00:00", None, ""),
        ("w południe", True, "2026-10-22 12:00", None, ""),
        # Halves and quarters, before the next hour or after this one.
        ("na wpół do siódmej jutro rano", True, "2026-10-22 06:30", None, ""),
        ("wpół do 8 rano", True, "2026-10-22 07:30", None, ""),
        ("kwadrans po siódmej jutro", True, "2026-10-22 07:15", None, ""),
        ("za kwadrans ósma jutro", True, "2026-10-22 07:45", None, ""),
        # A day: another day's alarm is in the morning, a reminder from 7 to
        # 11 in the morning, else after noon.
        ("na szóstą w sobotę", True, "2026-10-24 06:00", None, ""),
        ("pojutrze o siódmej", True, "2026-10-23 07:00", None, ""),
        ("za trzy dni o ósmej", True, "2026-10-24 08:00", None, ""),
        ("w przyszły poniedziałek o dziewiątej", False, "2026-10-26 09:00", None, ""),
        ("w środę o dziesiątej", False, "2026-10-28 10:00", None, ""),  # today's gone: next week's
        ("dziś wieczorem o dziewiątej", False, "2026-10-21 21:00", None, ""),
        # Repeating.
        ("w każdy dzień roboczy na szóstą czterdzieści pięć", True, "2026-10-22 06:45", WEEKDAYS, ""),
        ("na 6:45 w dni robocze", True, "2026-10-22 06:45", WEEKDAYS, ""),
        ("od poniedziałku do piątku o szóstej", True, "2026-10-22 06:00", WEEKDAYS, ""),
        ("codziennie o siódmej", True, "2026-10-22 07:00", "FREQ=DAILY", ""),
        ("w weekendy o ósmej", True, "2026-10-24 08:00", "FREQ=WEEKLY;BYDAY=SA,SU", ""),
        ("w soboty i niedziele o dziewiątej", True, "2026-10-24 09:00", "FREQ=WEEKLY;BYDAY=SA,SU", ""),
        ("co poniedziałek o ósmej", True, "2026-10-26 08:00", "FREQ=WEEKLY;BYDAY=MO", ""),
        ("w poniedziałki i środy o siódmej", True, "2026-10-26 07:00", "FREQ=WEEKLY;BYDAY=MO,WE", ""),
        ("w każdą środę i piątek o siódmej", True, "2026-10-23 07:00", "FREQ=WEEKLY;BYDAY=WE,FR", ""),
        # From now.
        ("za 20 minut", True, "2026-10-21 14:20", None, ""),
        ("za godzinę", True, "2026-10-21 15:00", None, ""),
        ("za pół godziny", True, "2026-10-21 14:30", None, ""),
        ("za półtorej godziny", True, "2026-10-21 15:30", None, ""),
        ("za kwadrans", True, "2026-10-21 14:15", None, ""),
        ("za godzinę i kwadrans", True, "2026-10-21 15:15", None, ""),
        ("za dwie i pół godziny", True, "2026-10-21 16:30", None, ""),
        # A reminder: what it is about, before or after when.
        ("o siedemnastej, żebym zadzwonił do mojej mamy", False, "2026-10-21 17:00", None, "żebym zadzwonił do mojej mamy"),
        ("żebym zadzwonił do mamy o piątej", False, "2026-10-21 17:00", None, "żebym zadzwonił do mamy"),
        ("że hydraulik przychodzi o trzeciej w piątek", False, "2026-10-23 15:00", None, "że hydraulik przychodzi"),
        ("żebym wyniósł śmieci w każdy wtorek o dziewiętnastej", False, "2026-10-27 19:00", "FREQ=WEEKLY;BYDAY=TU",
         "żebym wyniósł śmieci"),
        ("za dziesięć minut sprawdzić piekarnik", False, "2026-10-21 14:10", None, "sprawdzić piekarnik"),
        ("jutro o dziewiątej, żebym zadzwonił do dentysty", False, "2026-10-22 09:00", None, "żebym zadzwonił do dentysty"),
        ("o zakupach jutro o ósmej", False, "2026-10-22 08:00", None, "o zakupach"),
        ("o ósmej o zakupach", False, "2026-10-21 20:00", None, "o zakupach"),
        ("w piątek o 9 zadzwonić do mamy", False, "2026-10-23 09:00", None, "zadzwonić do mamy"),
    ],
)
def test_when(said, alarm, start, rrule, rest):
    found = calendar().when(said, NOW, alarm=alarm)
    assert found is not None
    assert found.start == datetime.fromisoformat(start).replace(tzinfo=TZ)
    assert found.rrule == rrule and found.rest.strip() == rest


@pytest.mark.parametrize(
    ("said", "alarm", "start", "rest"),
    [
        # A length alone is from now: the free text's edge can drop the "za".
        ("osiem godzin", True, "2026-10-21 22:00", ""),
        ("dwadzieścia pięć minut", True, "2026-10-21 14:25", ""),
        # "Mi", left before the reminder.
        ("mi o siedemnastej żebym kupił chleb", False, "2026-10-21 17:00", "żebym kupił chleb"),
        # A length that is the reminder's, before its time.
        ("żebym odpoczął dziesięć minut o siedemnastej", False, "2026-10-21 17:00", "żebym odpoczął dziesięć minut"),
    ],
)
def test_what_speech_to_text_makes_of_it(said, alarm, start, rest):
    found = calendar().when(said, NOW, alarm=alarm)
    assert found is not None
    assert found.start == datetime.fromisoformat(start).replace(tzinfo=TZ) and found.rest == rest


@pytest.mark.parametrize("said", ["żebym zadzwonił do mamy", "o zakupach", "", "jutro", "na jutro", "zadzwonić do mamy w piątek"])
def test_no_time_is_none(said):
    assert calendar().when(said, NOW) is None
    assert calendar().when(said, NOW, alarm=True) is None


@pytest.mark.parametrize(
    ("said", "wants"),
    [("jutro", True), ("w każdy poniedziałek", True), ("co rano", True), ("w piątek", True),
     ("kupić mleko", False), ("co mam kupić", False)],
)
def test_a_day_without_a_time_asks_for_one(said, wants):
    assert calendar().wants_time(said) is wants


@pytest.mark.parametrize(
    ("said", "back"),
    [
        ("żebym zadzwonił do mojej mamy", "zadzwonić do twojej mamy"),
        ("żebym wyniósł śmieci", "wynieść śmieci"),
        ("mi żebym wzięła leki", "wziąć leki"),
        ("żebyśmy podlali kwiaty", "podlać kwiaty"),
        ("że mam wizytę u lekarza", "masz wizytę u lekarza"),
        ("o zakupach", "o zakupach"),
        ("kupić mleko", "kupić mleko"),
        # Not one to make an infinitive of: said back as a clause.
        ("żebym się nie spóźnił", "żebyś się nie spóźnił"),
        ("żebym leżał", "żebyś leżał"),
        # Only the word that would join it: nothing to remind of.
        ("żebym", ""),
    ],
)
def test_what_is_said_back(said, back):
    assert calendar().what(said) == back


@pytest.mark.parametrize(
    ("said", "words"),
    [("o mamie jutro", ["mam"]), ("Zadzwonić do mamy", ["zadzwon", "mam"]), ("o dentyście", ["dentyst"]),
     ("Zadzwonić do dentysty", ["zadzwon", "dentyst"])],
)
def test_what_a_reminder_is_about(said, words):
    assert calendar().about(said) == words


@pytest.mark.parametrize(
    ("said", "days"),
    [("jutrzejszy", 1), ("na jutro", 1), ("pojutrzejsze", 2), ("dzisiejsze", 0), ("piątkowy", 2), ("w piątek", 2)],
)
def test_a_day_alone(said, days):
    assert calendar().day(said, NOW) == (NOW + timedelta(days=days)).date()


def _event(uid, hour, minute=0, days=1, kind="alarm", rrule=None, summary="Budzik"):
    start = NOW.replace(hour=hour, minute=minute) + timedelta(days=days)
    return alarms.Event(uid, start, summary, kind, rrule=rrule)


@pytest.mark.parametrize(
    ("time", "said"),
    [
        ("jutro na siódmą trzydzieści", "Ustawiono budzik na jutro na siódmą trzydzieści."),
        ("w dni robocze na szóstą czterdzieści pięć", "Ustawiono budzik na szóstą czterdzieści pięć w dni robocze."),
        ("w każdą środę o siódmej", "Ustawiono budzik na siódmą w każdą środę."),
        ("w sobotę o siódmej", "Ustawiono budzik na sobotę na siódmą."),
        ("za 20 minut", "Ustawiono budzik na czternastą dwadzieścia."),
    ],
)
def test_alarm_set_said(time, said):
    plan = alarms.plan("alarm", {"time": time}, NOW, [], [])
    assert plan.outcome == "done" and plan.speech == said


def test_alarm():
    plan = alarms.plan("alarm", {"time": "jutro na siódmą trzydzieści"}, NOW, [], [])
    assert plan.create == {"kind": "alarm", "summary": "Budzik", "start": NOW.replace(hour=7, minute=30) + timedelta(days=1),
                           "rrule": None}
    assert plan.levels["verbose"] == "Ustawiono budzik na jutro na siódmą trzydzieści. Zadzwoni za 17 godzin i 30 minut."
    missing = alarms.plan("alarm", {}, NOW, [], [])
    assert missing.outcome == "missing_time" and missing.speech == "Na którą godzinę ustawić budzik?"


@pytest.mark.parametrize(
    ("reminder", "said", "summary"),
    [
        ("o siedemnastej żebym zadzwonił do mojej mamy", "Przypomnę ci o siedemnastej: zadzwonić do twojej mamy.",
         "Zadzwonić do twojej mamy"),
        ("za dziesięć minut sprawdzić piekarnik", "Przypomnę ci za 10 minut: sprawdzić piekarnik.", "Sprawdzić piekarnik"),
        ("jutro o dziewiątej o wizycie u dentysty", "Przypomnę ci jutro o dziewiątej o wizycie u dentysty.",
         "O wizycie u dentysty"),
        ("jutro o ósmej żebym się nie spóźnił", "Przypomnę ci jutro o ósmej, żebyś się nie spóźnił.", "Żebyś się nie spóźnił"),
    ],
)
def test_reminder_set_said(reminder, said, summary):
    plan = alarms.plan("reminder", {"reminder": reminder}, NOW, [], [], todo=True)
    assert plan.outcome == "done" and plan.speech == said and plan.create["summary"] == summary


def test_reminder_with_or_without_a_time():
    # Without a time: on the to-do list, if there is one; else it asks when.
    listed = alarms.plan("reminder", {"reminder": "kupić mleko"}, NOW, [], [], todo=True)
    assert listed.outcome == "listed" and listed.todo == "kupić mleko" and listed.create is None
    assert listed.speech == "Zapisano przypomnienie: kupić mleko."
    assert alarms.plan("reminder", {"reminder": "kupić mleko"}, NOW, [], []).outcome == "missing_time"
    # A day but no time asks for one rather than listing it.
    assert alarms.plan("reminder", {"reminder": "kupić mleko jutro"}, NOW, [], [], todo=True).outcome == "missing_time"
    assert alarms.plan("reminder", {"reminder": "o piątej"}, NOW, [], [], todo=True).outcome == "missing_reminder"


def test_cancel_picks_the_alarm():
    seven, seven_pm = _event("1", 7), _event("2", 19)
    weekdays = _event("3", 6, 30, rrule=WEEKDAYS)
    plan = alarms.plan("cancel_alarm", {"time": "siódmą"}, NOW, [seven, weekdays], [])
    assert plan.outcome == "done" and plan.delete == [seven] and plan.speech == "Anulowano budzik na jutro na siódmą."
    assert alarms.plan("cancel_alarm", {"time": "siódmą"}, NOW, [seven, seven_pm], []).outcome == "ambiguous"
    assert alarms.plan("cancel_alarm", {"time": "dziewiętnastą"}, NOW, [seven, seven_pm], []).delete == [seven_pm]
    missing = alarms.plan("cancel_alarm", {"time": "ósmą"}, NOW, [seven], [])
    assert missing.outcome == "not_found" and missing.speech == "Nie ma budzika o dwudziestej. Masz budzik na jutro na siódmą."
    which = alarms.plan("cancel_alarm", {}, NOW, [seven, weekdays], [])
    assert which.outcome == "ambiguous" and [c["id"] for c in which.choices] == ["1", "3"]
    assert which.speech == "Który budzik: na jutro na siódmą czy na szóstą trzydzieści w dni robocze?"
    assert which.question == "Budzik na jutro na siódmą czy budzik na szóstą trzydzieści w dni robocze?"
    both = alarms.plan("cancel_alarm", {}, NOW, [seven, weekdays], [], every=True)
    assert both.delete == [seven, weekdays] and both.speech == "Anulowano 2 budziki."
    assert alarms.plan("cancel_alarm", {"time": "jutro"}, NOW, [seven, _event("4", 7, days=5)], []).delete == [seven]
    assert alarms.plan("cancel_alarm", {}, NOW, [], []).speech == "Nie ma żadnych budzików."


def test_cancel_picks_the_reminder():
    call = _event("1", 17, days=0, kind="reminder", summary="Zadzwonić do twojej mamy")
    dentist = _event("2", 9, days=1, kind="reminder", summary="Zadzwonić do dentysty")
    trash = _event("3", 8, days=6, kind="reminder", summary="Wynieść śmieci")
    every = [call, dentist, trash]

    def cancel(text, reminders=every):
        return alarms.plan("cancel_reminder", {"reminder": text} if text is not None else {}, NOW, [], reminders)

    # By what it is about, whatever its case ("o mamie", "do mamy").
    assert cancel("żebym zadzwonił do mojej mamy").delete == [call]
    assert cancel("o mamie").delete == [call]
    assert cancel("o dentyście").delete == [dentist]
    assert cancel("wynieść śmieci we wtorek").delete == [trash]
    assert cancel("o wynoszeniu śmieci").delete == [trash]
    # By when: a time, a day.
    assert cancel("o siedemnastej").delete == [call]
    assert cancel("na jutro").delete == [dentist]
    # Both "zadzwonić"s fit: it asks which.
    assert cancel("zadzwonić").outcome == "ambiguous"
    assert cancel(None).outcome == "ambiguous"
    assert cancel(None, [call]).delete == [call]
    missing = cancel("nakarmić kota")
    assert missing.outcome == "not_found" and missing.speech.startswith("Nie ma takiego przypomnienia.")
    assert cancel("o dziewiętnastej").outcome == "not_found"
    assert cancel("o mamie", []).outcome == "no_reminders"
    assert cancel("o mamie").speech == "Anulowano przypomnienie o siedemnastej: zadzwonić do twojej mamy."


def test_status():
    seven, weekdays = _event("1", 7), _event("2", 6, 30, rrule=WEEKDAYS)
    far = _event("3", 9, days=9)
    assert alarms.plan("alarm_status", {}, NOW, [seven], []).speech == "Masz budzik na jutro na siódmą."
    assert alarms.plan("alarm_status", {}, NOW, [seven, weekdays, far], []).speech == (
        "Masz 3 budziki: na jutro na siódmą, na szóstą trzydzieści w dni robocze i na trzydziestego października na dziewiątą.")
    assert alarms.plan("alarm_status", {}, NOW, [], []).speech == "Nie ma żadnych budzików."
    call = _event("4", 17, days=0, kind="reminder", summary="Zadzwonić do mamy")
    assert alarms.plan("reminder_status", {}, NOW, [], [call]).speech == "Masz jedno przypomnienie: zadzwonić do mamy o siedemnastej."
    assert alarms.plan("reminder_status", {}, NOW, [], []).outcome == "no_reminders"


@pytest.mark.parametrize(
    ("title", "said"),
    [("Budzik", "Jest siódma trzydzieści."), ("Alarm", "Jest siódma trzydzieści."), ("leki", "Leki. Jest siódma trzydzieści.")],
)
def test_an_alarm_ringing(title, said):
    assert calendar().alarm_due(title, NOW.replace(hour=7, minute=30)) == said


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("Zadzwonić do mamy", "Przypomnienie: zadzwonić do mamy."),
        ("O zakupach", "Przypominam o zakupach."),
        ("Żebyś się nie spóźnił", "Przypominam, żebyś się nie spóźnił."),
        ("Wizyta u dentysty", "Przypomnienie: Wizyta u dentysty."),  # one added in Home Assistant
    ],
)
def test_a_reminder_due(text, said):
    assert calendar().reminder_due(text) == said


def test_the_ui_examples_say_something():
    examples = alarms.outcome_examples()
    assert examples and all(said for outcomes in examples.values() for said in outcomes.values()), examples
