"""Alarms and timed reminders in German: when the calendar reads them from
what was said, what a reminder is said back as, and what each command says
(voice_incubator/languages/de/calendar.py, through voice_incubator/alarms.py).

Native speakers: add a row to a table to check another phrasing."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from voice_incubator import alarms, languages

TZ = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 10, 21, 14, 0, tzinfo=TZ)  # a Wednesday afternoon
WEEKDAYS = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"


@pytest.fixture(autouse=True)
def german():
    languages.use("de")
    yield
    languages.use(languages.DEFAULT)


def calendar():
    return languages.current().calendar


@pytest.mark.parametrize(
    ("said", "alarm", "start", "rrule", "rest"),
    [
        # Alarms: a clock time, the next one to come round unless a day says.
        ("für sieben Uhr morgen", True, "2026-10-22 07:00", None, ""),
        ("sieben Uhr dreißig", True, "2026-10-21 19:30", None, ""),
        ("halb sieben", True, "2026-10-21 18:30", None, ""),
        ("um Viertel nach sieben", True, "2026-10-21 19:15", None, ""),
        ("Viertel vor sieben", True, "2026-10-21 18:45", None, ""),
        ("dreiviertel sieben", True, "2026-10-21 18:45", None, ""),
        ("zehn vor acht", True, "2026-10-21 19:50", None, ""),
        ("fünf nach halb sieben", True, "2026-10-21 18:35", None, ""),
        ("fünf Minuten nach halb sieben", True, "2026-10-21 18:35", None, ""),
        ("um 7:30 Uhr", True, "2026-10-21 19:30", None, ""),
        ("um 7.30 Uhr", True, "2026-10-21 19:30", None, ""),
        ("19:30", True, "2026-10-21 19:30", None, ""),
        ("um 6 Uhr morgens", True, "2026-10-22 06:00", None, ""),
        ("um acht Uhr abends", True, "2026-10-21 20:00", None, ""),
        ("um zwölf Uhr mittags", True, "2026-10-22 12:00", None, ""),
        ("um ein Uhr mittags", True, "2026-10-22 13:00", None, ""),
        ("Mittag", True, "2026-10-22 12:00", None, ""),
        ("Mitternacht", True, "2026-10-22 00:00", None, ""),
        ("um zwei Uhr nachts", True, "2026-10-22 02:00", None, ""),
        # The day: heute, morgen, übermorgen, a weekday (another day: the morning).
        ("morgen früh um sechs Uhr fünfzehn", True, "2026-10-22 06:15", None, ""),
        ("morgen um acht Uhr", True, "2026-10-22 08:00", None, ""),
        ("übermorgen um 7", True, "2026-10-23 07:00", None, ""),
        ("heute Abend um zehn", True, "2026-10-21 22:00", None, ""),
        ("um zehn Uhr heute Abend", True, "2026-10-21 22:00", None, ""),
        ("heute Nacht um zwei", True, "2026-10-22 02:00", None, ""),
        ("für Samstag um sechs", True, "2026-10-24 06:00", None, ""),
        ("am Mittwoch um zehn", True, "2026-10-28 10:00", None, ""),  # today's 10:00 is gone: next week's
        ("am Mittwoch um 15 Uhr", True, "2026-10-21 15:00", None, ""),
        ("nächsten Montag um sieben", True, "2026-10-26 07:00", None, ""),
        ("Montagmorgen um sieben", True, "2026-10-26 07:00", None, ""),
        ("Freitagabend um acht", True, "2026-10-23 20:00", None, ""),
        ("in drei Tagen um acht", True, "2026-10-24 08:00", None, ""),
        # Repeating.
        ("jeden Tag um sieben", True, "2026-10-22 07:00", "FREQ=DAILY", ""),
        ("täglich um 22 Uhr", True, "2026-10-21 22:00", "FREQ=DAILY", ""),
        ("jeden Morgen um sechs", True, "2026-10-22 06:00", "FREQ=DAILY", ""),
        ("jeden Werktag um Viertel vor sieben", True, "2026-10-22 06:45", WEEKDAYS, ""),
        ("werktags um 6:45", True, "2026-10-22 06:45", WEEKDAYS, ""),
        ("an Werktagen um sechs", True, "2026-10-22 06:00", WEEKDAYS, ""),
        ("am Wochenende um neun", True, "2026-10-24 09:00", "FREQ=WEEKLY;BYDAY=SA,SU", ""),
        ("jeden Montag und Mittwoch um 7", True, "2026-10-26 07:00", "FREQ=WEEKLY;BYDAY=MO,WE", ""),
        ("montags und freitags um sechs", True, "2026-10-23 06:00", "FREQ=WEEKLY;BYDAY=MO,FR", ""),
        ("sonntags um zehn", True, "2026-10-25 10:00", "FREQ=WEEKLY;BYDAY=SU", ""),
        # From now.
        ("in 20 Minuten", True, "2026-10-21 14:20", None, ""),
        ("in zwanzig Minuten", True, "2026-10-21 14:20", None, ""),
        ("in einer Stunde", True, "2026-10-21 15:00", None, ""),
        ("in einer halben Stunde", True, "2026-10-21 14:30", None, ""),
        ("in einer Viertelstunde", True, "2026-10-21 14:15", None, ""),
        ("in anderthalb Stunden", True, "2026-10-21 15:30", None, ""),
        ("in acht Stunden", True, "2026-10-21 22:00", None, ""),
        # Reminders: the time anywhere -- first, last, or inside, the verb last.
        ("um 17 Uhr daran, Mama anzurufen", False, "2026-10-21 17:00", None, "daran Mama anzurufen"),
        ("daran, Mama anzurufen, um 17 Uhr", False, "2026-10-21 17:00", None, "daran Mama anzurufen"),
        ("um fünf, die Wäsche aufzuhängen", False, "2026-10-21 17:00", None, "die Wäsche aufzuhängen"),
        ("morgen um 9 daran, den Zahnarzt anzurufen", False, "2026-10-22 09:00", None, "daran den Zahnarzt anzurufen"),
        ("daran, morgen um 9 den Zahnarzt anzurufen", False, "2026-10-22 09:00", None, "daran den Zahnarzt anzurufen"),
        ("daran, dass der Klempner am Freitag um 3 kommt", False, "2026-10-23 15:00", None, "daran dass der Klempner kommt"),
        ("jeden Dienstag um 19 Uhr daran, den Müll rauszubringen", False, "2026-10-27 19:00", "FREQ=WEEKLY;BYDAY=TU",
         "daran den Müll rauszubringen"),
        ("daran, den Müll rauszubringen, jeden Dienstag um 19 Uhr", False, "2026-10-27 19:00", "FREQ=WEEKLY;BYDAY=TU",
         "daran den Müll rauszubringen"),
        ("in 10 Minuten daran, nach dem Ofen zu sehen", False, "2026-10-21 14:10", None, "daran nach dem Ofen zu sehen"),
        ("in einer Stunde, die Wäsche aufzuhängen", False, "2026-10-21 15:00", None, "die Wäsche aufzuhängen"),
        ("am Samstag um 10 daran, die Reifen zu wechseln", False, "2026-10-24 10:00", None, "daran die Reifen zu wechseln"),
    ],
)
def test_when(said, alarm, start, rrule, rest):
    found = calendar().when(said, NOW, alarm=alarm)
    assert found is not None
    assert found.start == datetime.fromisoformat(start).replace(tzinfo=TZ)
    assert found.rrule == rrule and found.rest == rest


@pytest.mark.parametrize(
    ("said", "alarm", "start", "rest"),
    [
        # A length alone, at the start, is from now: speech-to-text, or the free
        # text's edge, drops the "in".
        ("acht Stunden", True, "2026-10-21 22:00", ""),
        ("zehn Minuten daran, nach dem Ofen zu sehen", False, "2026-10-21 14:10", "daran nach dem Ofen zu sehen"),
        # A length that is the reminder's, before its time.
        ("daran, zehn Minuten Pause zu machen, um 17 Uhr", False, "2026-10-21 17:00", "daran zehn Minuten Pause zu machen"),
        # How the model writes numbers: "6 45".
        ("jeden Werktag um 6 45", True, "2026-10-22 06:45", ""),
        # A day today, its time gone: the time's next.
        ("heute um 9", False, "2026-10-21 21:00", "heute"),
    ],
)
def test_what_speech_to_text_makes_of_it(said, alarm, start, rest):
    found = calendar().when(said, NOW, alarm=alarm)
    assert found is not None
    assert found.start == datetime.fromisoformat(start).replace(tzinfo=TZ) and found.rest == rest


@pytest.mark.parametrize(
    ("said", "alarm"),
    [
        ("daran, Mama anzurufen", False),
        ("daran, zwei Eier zu kaufen", False),  # a number, but no time of day
        ("morgen daran, Milch zu kaufen", False),  # a day alone: asked what time
        ("an den Müll", False),
        ("", True),
        ("morgen", True),
    ],
)
def test_no_time_is_none(said, alarm):
    assert calendar().when(said, NOW, alarm=alarm) is None


@pytest.mark.parametrize(
    ("said", "back"),
    [
        ("daran, meine Mama anzurufen", "deine Mama anrufen"),
        ("daran Milch zu kaufen", "Milch kaufen"),
        ("den Müll rauszubringen", "den Müll rausbringen"),
        ("nach dem Ofen zu sehen", "nach dem Ofen sehen"),
        ("die Wäsche aufzuhängen", "die Wäsche aufhängen"),
        ("an den Müll", "den Müll"),
        ("dass der Klempner kommt", "der Klempner kommt"),
        ("dass ich Tabletten nehmen muss", "du Tabletten nehmen musst"),
        ("daran, dass ich und meine Schwester weg sind", "du und deine Schwester weg sind"),
    ],
)
def test_what_is_said_back(said, back):
    assert calendar().what(said) == back


@pytest.mark.parametrize(
    ("said", "words"),
    [
        ("meine Erinnerung, morgen Mama anzurufen", ["mama", "anrufen"]),
        ("Mama anrufen", ["mama", "anrufen"]),
        ("an den Zahnarzt", ["zahnarzt"]),
    ],
)
def test_what_a_reminder_is_about(said, words):
    assert calendar().about(said) == words


@pytest.mark.parametrize(
    ("said", "days"),
    [("morgen", 1), ("für morgen", 1), ("die morgige", 1), ("übermorgen", 2), ("heute", 0), ("am Freitag", 2), ("nichts", None)],
)
def test_a_day_without_a_time(said, days):
    found = calendar().day(said, NOW)
    assert found == (NOW.date() + timedelta(days=days) if days is not None else None)


@pytest.mark.parametrize(("said", "wants"), [("morgen", True), ("jeden Montag", True), ("werktags", True), ("Milch kaufen", False)])
def test_a_day_wants_a_time(said, wants):
    assert calendar().wants_time(said) is wants


@pytest.mark.parametrize(
    ("start", "rrule", "said"),
    [
        ("2026-10-21 19:30", None, "19 Uhr 30"),
        ("2026-10-22 07:00", None, "morgen um 7 Uhr"),
        ("2026-10-24 09:00", None, "Samstag um 9 Uhr"),
        ("2026-10-30 09:00", None, "den 30. Oktober um 9 Uhr"),
        ("2026-10-22 00:00", None, "morgen um Mitternacht"),
        ("2026-10-22 07:00", "FREQ=DAILY", "jeden Tag um 7 Uhr"),
        ("2026-10-22 06:45", WEEKDAYS, "jeden Werktag um 6 Uhr 45"),
        ("2026-10-24 09:00", "FREQ=WEEKLY;BYDAY=SA,SU", "jeden Samstag und Sonntag um 9 Uhr"),
        ("2026-10-26 07:00", "FREQ=WEEKLY;BYDAY=MO,WE", "jeden Montag und Mittwoch um 7 Uhr"),
    ],
)
def test_when_it_is_said(start, rrule, said):
    assert calendar().said_when(datetime.fromisoformat(start).replace(tzinfo=TZ), rrule, NOW) == said


def _event(uid, hour, minute=0, days=1, kind="alarm", rrule=None, summary="Wecker"):
    start = NOW.replace(hour=hour, minute=minute) + timedelta(days=days)
    return alarms.Event(uid, start, summary, kind, rrule=rrule)


@pytest.mark.parametrize(
    ("operation", "slots", "speech"),
    [
        ("alarm", {"time": "morgen um halb acht"}, "Wecker für morgen um 7 Uhr 30 gestellt."),
        ("alarm", {"time": "jeden Werktag um 6:45"}, "Wecker für jeden Werktag um 6 Uhr 45 gestellt."),
        ("alarm", {"time": "am Samstag um sieben"}, "Wecker für Samstag um 7 Uhr gestellt."),
        ("alarm", {}, "Für wann soll ich den Wecker stellen?"),
        ("reminder", {"reminder": "um 17 Uhr daran, meine Mama anzurufen"}, "Ich erinnere dich um 17 Uhr: Deine Mama anrufen."),
        ("reminder", {"reminder": "morgen um 9 daran, den Zahnarzt anzurufen"},
         "Ich erinnere dich morgen um 9 Uhr: Den Zahnarzt anrufen."),
        ("reminder", {"reminder": "am Samstag um 10 daran, die Reifen zu wechseln"},
         "Ich erinnere dich am Samstag um 10 Uhr: Die Reifen wechseln."),
        ("reminder", {"reminder": "in 10 Minuten daran, nach dem Ofen zu sehen"}, "Ich erinnere dich in 10 Minuten: Nach dem Ofen sehen."),
        ("reminder", {"reminder": "daran, Milch zu kaufen"}, "Zu deinen Erinnerungen hinzugefügt: Milch kaufen."),
        ("reminder", {"reminder": "morgen daran, Milch zu kaufen"}, "Wann soll ich dich erinnern?"),
        ("reminder", {"reminder": "um 5"}, "Woran soll ich dich erinnern?"),
        ("alarm_status", {}, "Es ist kein Wecker gestellt."),
        ("reminder_status", {}, "Du hast keine Erinnerungen."),
    ],
)
def test_what_is_said(operation, slots, speech):
    assert alarms.plan(operation, slots, NOW, [], [], todo=True).speech == speech


def test_alarm_on_the_calendar():
    plan = alarms.plan("alarm", {"time": "morgen um halb acht"}, NOW, [], [])
    assert plan.create == {"kind": "alarm", "summary": "Wecker", "start": NOW.replace(hour=7, minute=30) + timedelta(days=1),
                           "rrule": None}
    assert plan.levels["verbose"] == "Wecker für morgen um 7 Uhr 30 gestellt, in 17 Stunden und 30 Minuten."
    reminder = alarms.plan("reminder", {"reminder": "um 17 Uhr daran, meine Mama anzurufen"}, NOW, [], [], todo=True)
    assert reminder.create["summary"] == "Deine Mama anrufen"
    assert alarms.plan("reminder", {"reminder": "daran, Milch zu kaufen"}, NOW, [], []).outcome == "missing_time"


def test_cancel_picks_the_alarm():
    seven, seven_pm = _event("1", 7), _event("2", 19)
    weekdays = _event("3", 6, 30, rrule="FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR")
    plan = alarms.plan("cancel_alarm", {"time": "sieben"}, NOW, [seven, weekdays], [])
    assert plan.delete == [seven] and plan.speech == "Wecker für morgen um 7 Uhr gelöscht."
    which = alarms.plan("cancel_alarm", {"time": "sieben"}, NOW, [seven, seven_pm], [])
    assert which.outcome == "ambiguous"
    assert which.speech == "Welcher Wecker? Du hast Wecker für morgen um 7 Uhr und morgen um 19 Uhr."
    assert which.question == "Der Wecker für morgen um 7 Uhr oder der Wecker für morgen um 19 Uhr?"
    assert alarms.plan("cancel_alarm", {"time": "sieben Uhr abends"}, NOW, [seven, seven_pm], []).delete == [seven_pm]
    assert alarms.plan("cancel_alarm", {"time": "19 Uhr"}, NOW, [seven, seven_pm], []).delete == [seven_pm]
    missing = alarms.plan("cancel_alarm", {"time": "acht"}, NOW, [seven], [])
    assert missing.speech == "Es gibt keinen Wecker für 20 Uhr. Du hast einen Wecker für morgen um 7 Uhr."
    assert alarms.plan("cancel_alarm", {"time": "morgen"}, NOW, [seven, _event("4", 7, days=5)], []).delete == [seven]
    both = alarms.plan("cancel_alarm", {}, NOW, [seven, weekdays], [], every=True)
    assert both.levels["verbose"] == "Wecker für morgen um 7 Uhr und jeden Werktag um 6 Uhr 30 gelöscht."
    assert alarms.plan("cancel_alarm", {}, NOW, [], []).speech == "Es ist kein Wecker gestellt."


def test_cancel_picks_the_reminder():
    call = _event("1", 17, days=0, kind="reminder", summary="Mama anrufen")
    dentist = _event("2", 9, days=1, kind="reminder", summary="Den Zahnarzt anrufen")
    garbage = _event("3", 8, days=6, kind="reminder", summary="Den Müll rausbringen")
    every = [call, dentist, garbage]

    def cancel(text, reminders=every):
        return alarms.plan("cancel_reminder", {"reminder": text} if text is not None else {}, NOW, [], reminders)

    # By what it is about, as said ("meine" for "deine"), or close to it.
    assert cancel("Mama anzurufen").delete == [call]
    assert cancel("daran, meine Mama anzurufen").delete == [call]
    assert cancel("an den Zahnarzt").delete == [dentist]
    assert cancel("den Müll rauszubrigen").delete == [garbage]
    # By when: a time, a day.
    assert cancel("um 5").delete == [call]
    assert cancel("für morgen").delete == [dentist]
    # Both "anrufen"s fit: it asks which.
    which = cancel("anrufen")
    assert which.outcome == "ambiguous"
    assert which.question == "Um 17 Uhr Mama anrufen oder morgen um 9 Uhr den Zahnarzt anrufen?"
    assert cancel(None).outcome == "ambiguous"
    assert cancel("die Katze zu füttern").speech.startswith("So eine Erinnerung gibt es nicht.")
    assert cancel("Mama anzurufen").speech == "Erinnerung für 17 Uhr gelöscht: Mama anrufen."
    assert cancel("Mama anzurufen", []).speech == "Du hast keine Erinnerungen."


def test_status():
    assert alarms.plan("alarm_status", {}, NOW, [_event("1", 7)], []).speech == "Du hast einen Wecker für morgen um 7 Uhr."
    weekdays = _event("2", 6, 30, rrule=WEEKDAYS)
    assert alarms.plan("alarm_status", {}, NOW, [_event("1", 7), weekdays], []).speech == (
        "Du hast 2 Wecker: morgen um 7 Uhr und jeden Werktag um 6 Uhr 30.")
    reminders = [_event("3", 17, days=0, kind="reminder", summary="Mama anrufen"),
                 _event("4", 9, days=3, kind="reminder", summary="Reifen wechseln")]
    assert alarms.plan("reminder_status", {}, NOW, [], reminders).speech == (
        "Du hast 2 Erinnerungen: um 17 Uhr Mama anrufen und am Samstag um 9 Uhr Reifen wechseln.")


def test_what_rings():
    assert calendar().alarm_due("Wecker", NOW) == "Es ist 14 Uhr."
    assert calendar().alarm_due("Aufstehen", NOW) == "Aufstehen. Es ist 14 Uhr."
    assert calendar().reminder_due("Mama anrufen") == "Erinnerung: Mama anrufen."
