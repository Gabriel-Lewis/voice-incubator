"""Alarms and timed reminders in Russian: when one is for, read from what was
said, and what is said back (voice_incubator/languages/ru/calendar.py, through
voice_incubator/alarms.py). Each case is a row: a native speaker adds one by
adding a row."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from voice_incubator import alarms, languages

TZ = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 10, 21, 14, 0, tzinfo=TZ)  # a Wednesday afternoon
WEEKDAYS = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"


@pytest.fixture(autouse=True)
def russian():
    languages.use("ru")
    yield
    languages.use(languages.DEFAULT)


def calendar():
    return languages.current().calendar


@pytest.mark.parametrize(
    ("said", "alarm", "start", "rrule", "rest"),
    [
        # Alarms: a clock time, the next one to come round without утра or вечера.
        ("на семь тридцать", True, "2026-10-21 19:30", None, ""),
        ("на 7 утра завтра", True, "2026-10-22 07:00", None, ""),
        ("на завтра на восемь утра", True, "2026-10-22 08:00", None, ""),
        ("в шесть пятнадцать завтра утром", True, "2026-10-22 06:15", None, ""),
        # By the hour it leads to.
        ("на половину седьмого завтра", True, "2026-10-22 06:30", None, ""),
        ("на без четверти семь завтра", True, "2026-10-22 06:45", None, ""),
        ("на без пятнадцати восемь", True, "2026-10-21 19:45", None, ""),
        ("на четверть восьмого", True, "2026-10-21 19:15", None, ""),
        ("в десять минут восьмого", True, "2026-10-21 19:10", None, ""),
        ("полвосьмого", True, "2026-10-21 19:30", None, ""),
        # The 24-hour clock, noon and midnight, a time with its words.
        ("в 19:30", True, "2026-10-21 19:30", None, ""),
        ("в девятнадцать тридцать", True, "2026-10-21 19:30", None, ""),
        ("на полдень", True, "2026-10-22 12:00", None, ""),
        ("в полночь", True, "2026-10-22 00:00", None, ""),
        ("в 7 часов 30 минут", True, "2026-10-21 19:30", None, ""),
        # утра, дня, вечера, ночи: "одиннадцать ночи" is 23:00, "час ночи" 1:00.
        ("на 10 вечера", True, "2026-10-21 22:00", None, ""),
        ("сегодня в 10 вечера", True, "2026-10-21 22:00", None, ""),
        ("в одиннадцать ночи", True, "2026-10-21 23:00", None, ""),
        ("в час ночи", True, "2026-10-22 01:00", None, ""),
        ("в час дня", True, "2026-10-22 13:00", None, ""),
        # Another day: an alarm without утра or вечера is in the morning.
        ("в семь в субботу", True, "2026-10-24 07:00", None, ""),
        ("в субботу в 7", True, "2026-10-24 07:00", None, ""),
        ("в среду в 7", True, "2026-10-28 07:00", None, ""),  # today's 7:00 has gone: next week's
        ("послезавтра в 9", True, "2026-10-23 09:00", None, ""),
        ("через 2 дня в 9", True, "2026-10-23 09:00", None, ""),
        ("в следующую пятницу в 8", True, "2026-10-23 08:00", None, ""),
        # Repeating.
        ("на 6:45 по будням", True, "2026-10-22 06:45", WEEKDAYS, ""),
        ("на каждый будний день на 6:45", True, "2026-10-22 06:45", WEEKDAYS, ""),
        ("каждый день в 7", True, "2026-10-22 07:00", "FREQ=DAILY", ""),
        ("каждое утро в 7", True, "2026-10-22 07:00", "FREQ=DAILY", ""),
        ("каждый вечер в 9", True, "2026-10-21 21:00", "FREQ=DAILY", ""),
        ("по выходным в 9", True, "2026-10-24 09:00", "FREQ=WEEKLY;BYDAY=SA,SU", ""),
        ("каждый понедельник в 7", True, "2026-10-26 07:00", "FREQ=WEEKLY;BYDAY=MO", ""),
        ("по понедельникам и средам в 7", True, "2026-10-26 07:00", "FREQ=WEEKLY;BYDAY=MO,WE", ""),
        ("на семь каждую субботу", True, "2026-10-24 07:00", "FREQ=WEEKLY;BYDAY=SA", ""),
        # From now.
        ("через 20 минут", True, "2026-10-21 14:20", None, ""),
        ("через восемь часов", True, "2026-10-21 22:00", None, ""),
        ("через полчаса", True, "2026-10-21 14:30", None, ""),
        ("через полтора часа", True, "2026-10-21 15:30", None, ""),
        ("через час и десять минут", True, "2026-10-21 15:10", None, ""),
        ("на 20 минут", True, "2026-10-21 14:20", None, ""),
        # Reminders: the time before or after what to be reminded of.
        ("в 5 вечера позвонить маме", False, "2026-10-21 17:00", None, "позвонить маме"),
        ("позвонить маме в пять", False, "2026-10-21 17:00", None, "позвонить маме"),
        ("что сантехник придёт в 3 в пятницу", False, "2026-10-23 15:00", None, "что сантехник придёт"),
        ("выносить мусор каждый вторник в 7 вечера", False, "2026-10-27 19:00", "FREQ=WEEKLY;BYDAY=TU", "выносить мусор"),
        ("через 10 минут проверить духовку", False, "2026-10-21 14:10", None, "проверить духовку"),
        ("завтра в 9 позвонить стоматологу", False, "2026-10-22 09:00", None, "позвонить стоматологу"),
        ("поздравить маму с днем рождения завтра в 9", False, "2026-10-22 09:00", None, "поздравить маму с днем рождения"),
        # A length that is the reminder's, before its time.
        ("отдохнуть 10 минут в 5 вечера", False, "2026-10-21 17:00", None, "отдохнуть 10 минут"),
        ("отдохнуть десять минут в пять вечера", False, "2026-10-21 17:00", None, "отдохнуть десять минут"),
        ("отдохнуть 2 часа в 5 вечера", False, "2026-10-21 17:00", None, "отдохнуть 2 часа"),
        # A reminder on another day without вечера: from 7 to 11 in the morning, else after noon.
        ("в пятницу в три", False, "2026-10-23 15:00", None, ""),
        ("в понедельник в 10", False, "2026-10-26 10:00", None, ""),
    ],
)
def test_when(said, alarm, start, rrule, rest):
    found = calendar().when(said, NOW, alarm=alarm)
    assert found is not None
    assert found.start == datetime.fromisoformat(start).replace(tzinfo=TZ)
    assert found.rrule == rrule and found.rest == rest


@pytest.mark.parametrize(
    ("said", "alarm", "start", "relative"),
    [
        # "Послезавтра" written as two words.
        ("после завтра в 9", True, "2026-10-23 09:00", False),
        ("через двадцать минут", True, "2026-10-21 14:20", True),
        ("на семь", True, "2026-10-21 19:00", False),
    ],
)
def test_what_speech_to_text_makes_of_it(said, alarm, start, relative):
    found = calendar().when(said, NOW, alarm=alarm)
    assert found is not None
    assert found.start == datetime.fromisoformat(start).replace(tzinfo=TZ) and found.relative == relative


@pytest.mark.parametrize("said", ["позвонить маме", "купить молоко завтра", "на завтра", "завтра", "", "час", "помыть пол"])
def test_no_time_is_none(said):
    assert calendar().when(said, NOW) is None
    assert calendar().when(said, NOW, alarm=True) is None


@pytest.mark.parametrize(
    ("said", "wants"),
    [("купить молоко завтра", True), ("каждый понедельник", True), ("в пятницу", True), ("по будням", True),
     ("купить молоко", False)],
)
def test_a_day_without_a_time_asks_when(said, wants):
    assert calendar().wants_time(said) == wants


@pytest.mark.parametrize(
    ("said", "day"),
    [("на завтра", "2026-10-22"), ("завтрашний", "2026-10-22"), ("послезавтра", "2026-10-23"),
     ("в пятницу", "2026-10-23"), ("сегодняшнее", "2026-10-21"), ("позвонить маме", None)],
)
def test_the_day_said(said, day):
    found = calendar().day(said, NOW)
    assert (found.isoformat() if found else None) == day


@pytest.mark.parametrize(
    ("said", "back"),
    [
        ("позвонить моей маме", "позвонить вашей маме"),
        ("что мне нужно к врачу", "вам нужно к врачу"),
        ("мне забрать мои ключи", "забрать ваши ключи"),
        ("чтобы полить цветы", "полить цветы"),
        ("про стоматолога", "про стоматолога"),
    ],
)
def test_what_is_said_back(said, back):
    assert calendar().what(said) == back


@pytest.mark.parametrize(
    ("start", "rrule", "said"),
    [
        ("2026-10-21 17:00", None, "17:00"),
        ("2026-10-22 07:30", None, "7:30 завтра"),
        ("2026-10-23 09:00", None, "9:00 в пятницу"),
        ("2026-10-27 09:00", None, "9:00 во вторник"),
        ("2026-10-31 09:00", None, "9:00 тридцать первого октября"),
        ("2026-10-22 00:00", None, "полночь завтра"),
        ("2026-10-22 06:45", WEEKDAYS, "6:45 по будням"),
        ("2026-10-24 09:00", "FREQ=WEEKLY;BYDAY=SA,SU", "9:00 по выходным"),
        ("2026-10-22 07:00", "FREQ=DAILY", "7:00 каждый день"),
        ("2026-10-26 07:00", "FREQ=WEEKLY;BYDAY=MO,WE", "7:00 по понедельникам и средам"),
    ],
)
def test_when_said(start, rrule, said):
    assert calendar().said_when(datetime.fromisoformat(start).replace(tzinfo=TZ), rrule, NOW) == said


def _event(uid, hour, minute=0, days=1, kind="alarm", rrule=None, summary="Будильник"):
    start = NOW.replace(hour=hour, minute=minute) + timedelta(days=days)
    return alarms.Event(uid, start, summary, kind, rrule=rrule)


@pytest.mark.parametrize(
    ("time", "levels"),
    [
        ("семь тридцать завтра", {"brief": "Будильник поставлен.", "specific": "Будильник поставлен на 7:30 завтра.",
                                  "verbose": "Будильник поставлен на 7:30 завтра, через 17 часов и 30 минут."}),
        ("через двадцать минут", {"brief": "Будильник поставлен.", "specific": "Будильник поставлен на 14:20.",
                                  "verbose": "Будильник поставлен на 14:20, через 20 минут."}),
        ("шесть сорок пять по будням", {"brief": "Будильник поставлен.", "specific": "Будильник поставлен на 6:45 по будням.",
                                        "verbose": "Будильник поставлен на 6:45 по будням, через 16 часов и 45 минут."}),
    ],
)
def test_alarm(time, levels):
    plan = alarms.plan("alarm", {"time": time}, NOW, [], [])
    assert plan.outcome == "done" and plan.levels == levels
    assert plan.create["kind"] == "alarm" and plan.create["summary"] == "Будильник"


def test_an_alarm_without_a_time_asks():
    plan = alarms.plan("alarm", {}, NOW, [], [])
    assert plan.outcome == "missing_time" and plan.speech == "На какое время поставить будильник?"


@pytest.mark.parametrize(
    ("said", "outcome", "speech", "summary"),
    [
        ("в пять вечера позвонить моей маме", "done", "Напомню позвонить вашей маме в 17:00.", "Позвонить вашей маме"),
        ("через 10 минут проверить духовку", "done", "Напомню проверить духовку через 10 минут.", "Проверить духовку"),
        ("что сантехник придёт в 3 в пятницу", "done", "Напомню в 15:00 в пятницу: сантехник придёт.", "Сантехник придёт"),
        ("выносить мусор каждый вторник в 7 вечера", "done", "Напомню выносить мусор в 19:00 по вторникам.", "Выносить мусор"),
        ("про стоматолога завтра в 9", "done", "Напомню про стоматолога в 9:00 завтра.", "Про стоматолога"),
        # Without a time: on the to-do list; a day but no time asks for one.
        ("купить молоко", "listed", "Добавлено в напоминания: купить молоко.", None),
        ("купить молоко завтра", "missing_time", "Когда напомнить?", None),
        ("в пять", "missing_reminder", "О чём напомнить?", None),
    ],
)
def test_reminder(said, outcome, speech, summary):
    plan = alarms.plan("reminder", {"reminder": said}, NOW, [], [], todo=True)
    assert (plan.outcome, plan.speech) == (outcome, speech)
    assert (plan.create["summary"] if plan.create else None) == summary


def test_a_reminder_without_a_time_or_a_list_asks_when():
    assert alarms.plan("reminder", {"reminder": "купить молоко"}, NOW, [], []).outcome == "missing_time"


SEVEN, SEVEN_PM = _event("1", 7), _event("2", 19)
WEEKDAY = _event("3", 6, 30, rrule=WEEKDAYS)


@pytest.mark.parametrize(
    ("time", "alarms_set", "outcome", "deleted", "speech"),
    [
        ("семь", [SEVEN, WEEKDAY], "done", ["1"], "Будильник на 7:00 завтра отменён."),
        ("на семь", [SEVEN, WEEKDAY], "done", ["1"], "Будильник на 7:00 завтра отменён."),
        ("семь", [SEVEN, SEVEN_PM], "ambiguous", [], "Какой будильник? Есть будильники на 7:00 завтра и на 19:00 завтра."),
        ("семь вечера", [SEVEN, SEVEN_PM], "done", ["2"], "Будильник на 19:00 завтра отменён."),
        ("восемь", [SEVEN], "not_found", [], "Будильника на 20:00 нет. У вас будильник на 7:00 завтра."),
        (None, [WEEKDAY], "done", ["3"], "Будильник на 6:30 по будням отменён."),
        (None, [], "no_alarms", [], "Будильников нет."),
        ("завтрашний", [SEVEN, _event("4", 7, days=5)], "done", ["1"], "Будильник на 7:00 завтра отменён."),
    ],
)
def test_cancel_picks_the_alarm(time, alarms_set, outcome, deleted, speech):
    plan = alarms.plan("cancel_alarm", {"time": time} if time else {}, NOW, alarms_set, [])
    assert (plan.outcome, [e.uid for e in plan.delete], plan.speech) == (outcome, deleted, speech)


def test_which_alarm_is_asked():
    which = alarms.plan("cancel_alarm", {}, NOW, [SEVEN, WEEKDAY], [])
    assert which.outcome == "ambiguous" and [c["id"] for c in which.choices] == ["1", "3"]
    assert which.question == "Будильник на 7:00 завтра или на 6:30 по будням?"
    assert [c["label"] for c in which.choices] == ["будильник на 7:00 завтра", "будильник на 6:30 по будням"]
    # "Оба": each of them.
    both = alarms.plan("cancel_alarm", {}, NOW, [SEVEN, WEEKDAY], [], every=True)
    assert both.delete == [SEVEN, WEEKDAY] and both.speech == "Отменены 2 будильника."
    assert both.levels["verbose"] == "Отменены будильники на 7:00 завтра и на 6:30 по будням."


CALL = _event("1", 17, days=0, kind="reminder", summary="Позвонить вашей маме")
DENTIST = _event("2", 9, days=1, kind="reminder", summary="Позвонить стоматологу")
GARBAGE = _event("3", 8, days=6, kind="reminder", summary="Вынести мусор")


@pytest.mark.parametrize(
    ("said", "outcome", "deleted"),
    [
        # By what it is about, as said ("мой" for "ваш"), in another case, or close to it.
        ("позвонить моей маме", "done", ["1"]),
        ("про стоматолога", "done", ["2"]),
        ("вынести мусор во вторник", "done", ["3"]),
        ("вынести мусар", "done", ["3"]),
        # By when: a time (before or after noon when it doesn't say), a day.
        ("в пять", "done", ["1"]),
        ("на завтра", "done", ["2"]),
        ("завтрашнее", "done", ["2"]),
        # Both "позвонить" fit: it asks which.
        ("позвонить", "ambiguous", []),
        (None, "ambiguous", []),
        ("покормить кошку", "not_found", []),
        ("в семь вечера", "not_found", []),
    ],
)
def test_cancel_picks_the_reminder(said, outcome, deleted):
    plan = alarms.plan("cancel_reminder", {"reminder": said} if said else {}, NOW, [], [CALL, DENTIST, GARBAGE])
    assert (plan.outcome, [e.uid for e in plan.delete]) == (outcome, deleted)


def test_what_cancelling_a_reminder_says():
    every = [CALL, DENTIST, GARBAGE]
    done = alarms.plan("cancel_reminder", {"reminder": "позвонить маме"}, NOW, [], every)
    assert done.speech == "Отменено напоминание в 17:00: Позвонить вашей маме."
    missing = alarms.plan("cancel_reminder", {"reminder": "покормить кошку"}, NOW, [], every)
    assert missing.speech == ("Такого напоминания нет. У вас 3 напоминания: Позвонить вашей маме в 17:00, "
                              "Позвонить стоматологу в 9:00 завтра и Вынести мусор в 8:00 во вторник.")
    which = alarms.plan("cancel_reminder", {"reminder": "позвонить"}, NOW, [], every)
    assert which.question == "Позвонить вашей маме в 17:00 или Позвонить стоматологу в 9:00 завтра?"
    assert alarms.plan("cancel_reminder", {}, NOW, [], [CALL]).delete == [CALL]
    assert alarms.plan("cancel_reminder", {"reminder": "позвонить маме"}, NOW, [], []).speech == "Напоминаний нет."


@pytest.mark.parametrize(
    ("operation", "alarms_set", "reminders", "speech"),
    [
        ("alarm_status", [SEVEN], [], "У вас будильник на 7:00 завтра."),
        ("alarm_status", [SEVEN, WEEKDAY], [], "У вас 2 будильника: на 7:00 завтра и на 6:30 по будням."),
        ("alarm_status", [], [], "Будильников нет."),
        ("reminder_status", [], [CALL], "У вас одно напоминание: Позвонить вашей маме в 17:00."),
        ("reminder_status", [], [CALL, DENTIST], "У вас два напоминания: Позвонить вашей маме в 17:00 и Позвонить стоматологу в 9:00 завтра."),
        ("reminder_status", [], [], "Напоминаний нет."),
    ],
)
def test_status(operation, alarms_set, reminders, speech):
    assert alarms.plan(operation, {}, NOW, alarms_set, reminders).speech == speech


@pytest.mark.parametrize(
    ("title", "said"),
    [("Будильник", "Сейчас 7:30."), ("Alarm", "Сейчас 7:30."), ("подъём", "Подъём. Сейчас 7:30.")],
)
def test_an_alarm_says_the_time_when_it_rings(title, said):
    assert calendar().alarm_due(title, NOW.replace(hour=7, minute=30)) == said


def test_a_reminder_says_what_it_is_when_it_is_due():
    assert calendar().reminder_due("Позвонить маме.") == "Напоминание: Позвонить маме."
