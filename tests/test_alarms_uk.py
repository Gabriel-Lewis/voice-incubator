"""Alarms and timed reminders in Ukrainian: when the Ukrainian calendar words
(voice_incubator/languages/uk/calendar.py) read one to be from what was said,
and what each command says (voice_incubator/alarms.py) -- as tests/test_alarms.py
does for English.

The cases are tables: a native speaker adds a row for a phrasing ("на
сьому", "о пів на восьму", "щопонеділка") with when it should be, and what is
left for the reminder's text."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from voice_incubator import alarms, languages

TZ = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 10, 21, 14, 0, tzinfo=TZ)  # a Wednesday afternoon
WEEKDAYS = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"


@pytest.fixture(autouse=True)
def ukrainian():
    languages.use("uk")
    yield
    languages.use(languages.DEFAULT)


def calendar():
    return languages.current().calendar


@pytest.mark.parametrize(
    ("said", "alarm", "start", "rrule", "rest"),
    [
        # Alarms: all their words are the time.
        ("на сьому ранку завтра", True, "2026-10-22 07:00", None, ""),
        ("сьому тридцять", True, "2026-10-21 19:30", None, ""),  # the next 7:30 to come round
        ("сім тридцять", True, "2026-10-21 19:30", None, ""),  # a cardinal hour
        ("о 7:30 завтра", True, "2026-10-22 07:30", None, ""),
        ("на 19:00", True, "2026-10-21 19:00", None, ""),
        ("на пів на сьому завтра вранці", True, "2026-10-22 06:30", None, ""),  # half to the hour
        ("за чверть сьома завтра", True, "2026-10-22 06:45", None, ""),
        ("чверть на восьму завтра", True, "2026-10-22 07:15", None, ""),
        ("на шосту в суботу", True, "2026-10-24 06:00", None, ""),  # another day: the morning
        ("у середу о восьмій", True, "2026-10-28 08:00", None, ""),  # today's weekday: next week's
        ("наступного понеділка о восьмій", True, "2026-10-26 08:00", None, ""),
        ("післязавтра о восьмій", True, "2026-10-23 08:00", None, ""),
        ("через три дні о дев'ятій", True, "2026-10-24 09:00", None, ""),
        ("сьогодні о десятій вечора", True, "2026-10-21 22:00", None, ""),
        ("о десятій ночі", True, "2026-10-21 22:00", None, ""),  # late at night is the evening's
        ("о другій ночі", True, "2026-10-22 02:00", None, ""),
        ("о дванадцятій ночі", True, "2026-10-22 00:00", None, ""),
        ("опівночі", True, "2026-10-22 00:00", None, ""),
        ("опівдні", True, "2026-10-22 12:00", None, ""),
        ("по буднях о шостій сорок п'ять", True, "2026-10-22 06:45", WEEKDAYS, ""),
        ("щобудня о шостій", True, "2026-10-22 06:00", WEEKDAYS, ""),
        ("по вихідних о дев'ятій", True, "2026-10-24 09:00", "FREQ=WEEKLY;BYDAY=SA,SU", ""),
        ("щодня о сьомій", True, "2026-10-22 07:00", "FREQ=DAILY", ""),
        ("кожного ранку о сьомій", True, "2026-10-22 07:00", "FREQ=DAILY", ""),
        ("щопонеділка і щосереди о сьомій", True, "2026-10-26 07:00", "FREQ=WEEKLY;BYDAY=MO,WE", ""),
        ("по понеділках і середах о сьомій", True, "2026-10-26 07:00", "FREQ=WEEKLY;BYDAY=MO,WE", ""),
        ("кожного понеділка о восьмій", True, "2026-10-26 08:00", "FREQ=WEEKLY;BYDAY=MO", ""),
        ("через двадцять хвилин", True, "2026-10-21 14:20", None, ""),
        ("через годину", True, "2026-10-21 15:00", None, ""),
        ("через півгодини", True, "2026-10-21 14:30", None, ""),
        ("через півтори години", True, "2026-10-21 15:30", None, ""),
        ("через годину і десять хвилин", True, "2026-10-21 15:10", None, ""),
        # Reminders: the time at the start or the end, the rest their text.
        ("о п'ятій вечора подзвонити мамі", False, "2026-10-21 17:00", None, "подзвонити мамі"),
        ("подзвонити мамі о п'ятій", False, "2026-10-21 17:00", None, "подзвонити мамі"),
        ("що сантехнік прийде в п'ятницю о третій", False, "2026-10-23 15:00", None, "що сантехнік прийде"),
        ("винести сміття щовівторка о сьомій вечора", False, "2026-10-27 19:00", "FREQ=WEEKLY;BYDAY=TU",
         "винести сміття"),
        ("через десять хвилин перевірити духовку", False, "2026-10-21 14:10", None, "перевірити духовку"),
        ("завтра о дев'ятій подзвонити стоматологу", False, "2026-10-22 09:00", None, "подзвонити стоматологу"),
        ("подзвонити другу о п'ятій", False, "2026-10-21 17:00", None, "подзвонити другу"),
        ("на сьому вечора полити квіти", False, "2026-10-21 19:00", None, "полити квіти"),
        ("у п'ятницю о дев'ятій забрати посилку", False, "2026-10-23 09:00", None, "забрати посилку"),
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
        # A length alone is from now for an alarm: speech-to-text can drop "через".
        ("вісім годин", True, "2026-10-21 22:00", ""),
        # A length that is the reminder's, before its time.
        ("відпочити десять хвилин о п'ятій вечора", False, "2026-10-21 17:00", "відпочити десять хвилин"),
        ("поставити тісто на дві години о п'ятій", False, "2026-10-21 17:00", "поставити тісто на дві години"),
        # The hour joined to its "о", or without its last "й".
        ("осьомій", True, "2026-10-21 19:00", ""),
        ("о сьомі ранку", True, "2026-10-22 07:00", ""),
        # Split words joined: "після завтра", "що понеділка".
        ("після завтра о восьмій", True, "2026-10-23 08:00", ""),
        # The "на" before a reminder's time, taken for filler by the matcher.
        ("п'яту вечора", False, "2026-10-21 17:00", ""),
    ],
)
def test_what_speech_to_text_makes_of_it(said, alarm, start, rest):
    found = calendar().when(said, NOW, alarm=alarm)
    assert found is not None
    assert found.start == datetime.fromisoformat(start).replace(tzinfo=TZ) and found.rest == rest


def test_what_speech_to_text_makes_of_a_repeat():
    assert calendar().when("що понеділка о сьомій", NOW, alarm=True).rrule == "FREQ=WEEKLY;BYDAY=MO"


@pytest.mark.parametrize(
    ("said", "alarm"),
    [
        ("подзвонити мамі", False),
        ("купити молоко", False),
        ("подзвонити другу", False),  # a friend, not two o'clock
        ("купити молоко завтра", False),  # a day, but no time
        ("відпочити десять хвилин", False),  # the reminder's own length
        ("на завтра", True),
        ("", True),
    ],
)
def test_no_time_is_none(said, alarm):
    assert calendar().when(said, NOW, alarm=alarm) is None


@pytest.mark.parametrize(
    ("said", "wants"),
    [("купити молоко завтра", True), ("щопонеділка", True), ("у п'ятницю", True), ("сьогодні ввечері", True),
     ("купити молоко", False), ("подзвонити другу", False)],
)
def test_a_day_without_a_time_asks_for_one(said, wants):
    assert calendar().wants_time(said) is wants


@pytest.mark.parametrize(
    ("said", "ahead"),
    [("на завтра", 1), ("завтрашній", 1), ("сьогоднішнє", 0), ("післязавтра", 2), ("у п'ятницю", 2),
     ("через три дні", 3), ("подзвонити мамі", None)],
)
def test_the_day_said(said, ahead):
    found = calendar().day(said, NOW)
    assert found == (None if ahead is None else (NOW + timedelta(days=ahead)).date())


@pytest.mark.parametrize(
    ("said", "back"),
    [
        ("подзвонити моїй мамі", "подзвонити твоїй мамі"),
        ("що мені треба до лікаря", "тобі треба до лікаря"),
        ("про зустріч з моїм братом", "зустріч з твоїм братом"),
        ("мені купити хліб", "купити хліб"),
        ("щоб я не забув парасольку", "ти не забув парасольку"),
    ],
)
def test_what_is_said_back(said, back):
    assert calendar().what(said) == back


def test_what_a_reminder_is_about_is_compared_by_stems():
    # "Про стоматолога" and "Подзвонити стоматологу": the same dentist.
    assert set(calendar().about("про стоматолога")) <= set(calendar().about("Подзвонити стоматологу"))
    assert calendar().about("моє нагадування подзвонити мамі завтра") == ["подзвонит", "мам"]


@pytest.mark.parametrize(
    ("hour", "minute", "days", "rrule", "said"),
    [
        (7, 30, 0, None, "о сьомій тридцять"),
        (7, 30, 1, None, "завтра о сьомій тридцять"),
        (9, 0, 2, None, "у п'ятницю о дев'ятій"),
        (11, 0, 3, None, "у суботу об одинадцятій"),
        (9, 0, 9, None, "тридцятого жовтня о дев'ятій"),
        (0, 0, 1, None, "завтра опівночі"),
        (6, 45, 1, WEEKDAYS, "по буднях о шостій сорок п'ять"),
        (9, 0, 3, "FREQ=WEEKLY;BYDAY=SA,SU", "по вихідних о дев'ятій"),
        (7, 0, 1, "FREQ=DAILY", "щодня о сьомій"),
        (7, 0, 5, "FREQ=WEEKLY;BYDAY=MO,WE", "щопонеділка і щосереди о сьомій"),
    ],
)
def test_when_is_said(hour, minute, days, rrule, said):
    start = NOW.replace(hour=hour, minute=minute) + timedelta(days=days)
    assert calendar().said_when(start, rrule, NOW) == said


def _event(uid, hour, minute=0, days=1, kind="alarm", rrule=None, summary="Будильник"):
    start = NOW.replace(hour=hour, minute=minute) + timedelta(days=days)
    return alarms.Event(uid, start, summary, kind, rrule=rrule)


def test_alarm():
    plan = alarms.plan("alarm", {"time": "сьому тридцять завтра"}, NOW, [], [])
    assert plan.outcome == "done" and plan.speech == "Будильник задзвонить завтра о сьомій тридцять."
    assert plan.create == {"kind": "alarm", "summary": "Будильник", "start": NOW.replace(hour=7, minute=30) + timedelta(days=1),
                           "rrule": None}
    assert plan.levels["verbose"] == "Будильник задзвонить завтра о сьомій тридцять, це через сімнадцять годин і тридцять хвилин."
    repeating = alarms.plan("alarm", {"time": "по буднях о шостій сорок п'ять"}, NOW, [], [])
    assert repeating.speech == "Будильник дзвонитиме по буднях о шостій сорок п'ять."
    missing = alarms.plan("alarm", {}, NOW, [], [])
    assert missing.outcome == "missing_time" and missing.speech == "На котру годину поставити будильник?"


def test_reminder_with_or_without_a_time():
    plan = alarms.plan("reminder", {"reminder": "о п'ятій вечора подзвонити моїй мамі"}, NOW, [], [], todo=True)
    assert plan.outcome == "done" and plan.create["summary"] == "Подзвонити твоїй мамі"
    assert plan.speech == "Нагадаю о сімнадцятій: подзвонити твоїй мамі."
    soon = alarms.plan("reminder", {"reminder": "через десять хвилин перевірити духовку"}, NOW, [], [], todo=True)
    assert soon.speech == "Нагадаю через десять хвилин: перевірити духовку."
    # Without a time: on the to-do list, if there is one; else it asks when.
    listed = alarms.plan("reminder", {"reminder": "купити молоко"}, NOW, [], [], todo=True)
    assert listed.outcome == "listed" and listed.todo == "купити молоко" and listed.create is None
    assert listed.speech == "Додано до нагадувань: купити молоко."
    assert alarms.plan("reminder", {"reminder": "купити молоко"}, NOW, [], []).outcome == "missing_time"
    # A day but no time asks for one rather than listing it.
    asked = alarms.plan("reminder", {"reminder": "купити молоко завтра"}, NOW, [], [], todo=True)
    assert asked.outcome == "missing_time" and asked.speech == "Коли нагадати?"
    nothing = alarms.plan("reminder", {"reminder": "о п'ятій"}, NOW, [], [], todo=True)
    assert nothing.outcome == "missing_reminder" and nothing.speech == "Про що нагадати?"


def test_cancel_picks_the_alarm():
    seven, seven_pm = _event("1", 7), _event("2", 19)
    weekdays = _event("3", 6, 30, rrule=WEEKDAYS)
    # Without "ранку" or "вечора", either.
    plan = alarms.plan("cancel_alarm", {"time": "сьому"}, NOW, [seven, weekdays], [])
    assert plan.outcome == "done" and plan.delete == [seven]
    assert plan.speech == "Скасовано будильник завтра о сьомій."
    assert alarms.plan("cancel_alarm", {"time": "сьому"}, NOW, [seven, seven_pm], []).outcome == "ambiguous"
    assert alarms.plan("cancel_alarm", {"time": "сьому вечора"}, NOW, [seven, seven_pm], []).delete == [seven_pm]
    missing = alarms.plan("cancel_alarm", {"time": "восьму"}, NOW, [seven], [])
    assert missing.outcome == "not_found"
    assert missing.speech == "Немає будильника о двадцятій. Є будильник завтра о сьомій."
    which = alarms.plan("cancel_alarm", {}, NOW, [seven, weekdays], [])
    assert which.outcome == "ambiguous" and [c["id"] for c in which.choices] == ["1", "3"]
    assert which.speech == "Який будильник? Їх кілька: завтра о сьомій і по буднях о шостій тридцять."
    assert which.question == "Будильник завтра о сьомій чи по буднях о шостій тридцять?"
    assert [c["label"] for c in which.choices] == ["будильник завтра о сьомій", "будильник по буднях о шостій тридцять"]
    # "Обидва": each of them.
    assert alarms.plan("cancel_alarm", {}, NOW, [seven, weekdays], [], every=True).delete == [seven, weekdays]
    assert alarms.plan("cancel_alarm", {}, NOW, [], []).speech == "Будильників немає."


def test_cancel_alarm_by_its_day():
    seven, monday = _event("1", 7), _event("2", 7, days=5)
    assert alarms.plan("cancel_alarm", {"time": "завтра"}, NOW, [seven, monday], []).delete == [seven]
    assert alarms.plan("cancel_alarm", {"time": "завтрашній"}, NOW, [seven, monday], []).delete == [seven]
    assert alarms.plan("cancel_alarm", {"time": "сьому"}, NOW, [seven, monday], []).outcome == "ambiguous"


@pytest.mark.parametrize(
    ("said", "deleted"),
    [
        # By what it is about, as said ("моїй" for "твоїй"), in another case, or close to it.
        ("подзвонити моїй мамі", ["1"]),
        ("про стоматолога", ["2"]),
        ("винести сміття у вівторок", ["3"]),
        ("винести смітя", ["3"]),
        # By when: a time ("ранку" or "вечора" when it doesn't say), a day.
        ("о п'ятій", ["1"]),
        ("п'яту вечора", ["1"]),
        ("завтра", ["2"]),
    ],
)
def test_cancel_picks_the_reminder(said, deleted):
    plan = alarms.plan("cancel_reminder", {"reminder": said}, NOW, [], _reminders())
    assert plan.outcome == "done" and [e.uid for e in plan.delete] == deleted


def _reminders():
    return [_event("1", 17, days=0, kind="reminder", summary="Подзвонити твоїй мамі"),
            _event("2", 9, days=1, kind="reminder", summary="Подзвонити стоматологу"),
            _event("3", 8, days=6, kind="reminder", summary="Винести сміття")]


def test_cancel_a_reminder_said_back():
    every = _reminders()
    done = alarms.plan("cancel_reminder", {"reminder": "подзвонити мамі"}, NOW, [], every)
    assert done.speech == "Скасовано нагадування о сімнадцятій: Подзвонити твоїй мамі."
    # Both "подзвонити"s fit: it asks which.
    which = alarms.plan("cancel_reminder", {"reminder": "подзвонити"}, NOW, [], every)
    assert which.outcome == "ambiguous"
    assert which.question == "Подзвонити твоїй мамі о сімнадцятій чи Подзвонити стоматологу завтра о дев'ятій?"
    assert alarms.plan("cancel_reminder", {}, NOW, [], every).outcome == "ambiguous"
    assert alarms.plan("cancel_reminder", {}, NOW, [], every[:1]).delete == every[:1]
    missing = alarms.plan("cancel_reminder", {"reminder": "погодувати кота"}, NOW, [], every)
    assert missing.outcome == "not_found" and missing.speech.startswith("Такого нагадування немає.")
    assert alarms.plan("cancel_reminder", {"reminder": "о сьомій вечора"}, NOW, [], every).outcome == "not_found"
    assert alarms.plan("cancel_reminder", {"reminder": "подзвонити мамі"}, NOW, [], []).speech == "Нагадувань немає."


def test_status():
    seven, weekdays = _event("1", 7), _event("2", 6, 30, rrule=WEEKDAYS)
    assert alarms.plan("alarm_status", {}, NOW, [seven], []).speech == "Є будильник завтра о сьомій."
    assert alarms.plan("alarm_status", {}, NOW, [seven, weekdays], []).speech == (
        "Є два будильники: завтра о сьомій і по буднях о шостій тридцять.")
    assert alarms.plan("alarm_status", {}, NOW, [], []).speech == "Будильників немає."
    call = _event("3", 17, days=0, kind="reminder", summary="Подзвонити мамі")
    assert alarms.plan("reminder_status", {}, NOW, [], [call]).speech == "Є одне нагадування: Подзвонити мамі о сімнадцятій."
    assert alarms.plan("reminder_status", {}, NOW, [], _reminders()).speech.startswith("Є три нагадування: ")
    assert alarms.plan("reminder_status", {}, NOW, [], []).speech == "Нагадувань немає."


def test_what_rings():
    assert calendar().alarm_due("Будильник", NOW.replace(hour=7, minute=30)) == "Зараз сьома тридцять."
    assert calendar().alarm_due("Alarm", NOW.replace(hour=0, minute=0)) == "Зараз північ."
    assert calendar().alarm_due("підйом", NOW.replace(hour=7, minute=0)) == "Підйом. Зараз сьома."
    assert calendar().reminder_due("Подзвонити мамі.") == "Нагадування: Подзвонити мамі."


def test_the_uis_examples_are_said_in_ukrainian():
    said = alarms.outcome_examples()
    assert all(text for outcomes in said.values() for text in outcomes.values()), said
    assert said["reminder"]["done"] == "Нагадаю о сімнадцятій: подзвонити мамі."
    assert alarms.level_examples()["alarm"]["brief"] == "Будильник поставлено."
