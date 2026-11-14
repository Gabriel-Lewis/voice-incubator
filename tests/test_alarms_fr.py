"""Alarms and timed reminders on the calendar, in French: what is read from
what was said, and what is said back (voice_incubator/languages/fr/calendar.py,
through voice_incubator/alarms.py). Each table is a native speaker's to add
rows to: what was said, and what it must come to."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from voice_incubator import alarms, languages
from voice_incubator.languages.fr import calendar, reading

TZ = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 10, 21, 14, 0, tzinfo=TZ)  # a Wednesday afternoon
WEEKDAYS = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"


@pytest.fixture(autouse=True)
def french():
    languages.use("fr")
    yield
    languages.use(languages.DEFAULT)


# ------------------------------------------------------------------ reading

WHEN = [
    # (said, alarm, start, rrule, rest)
    ("à sept heures demain", True, "2026-10-22 07:00", None, ""),
    ("sept heures et demie", True, "2026-10-21 19:30", None, ""),  # the next 7:30 to come round
    ("six heures et demie demain matin", True, "2026-10-22 06:30", None, ""),
    ("six heures et quart demain", True, "2026-10-22 06:15", None, ""),
    ("huit heures moins le quart demain", True, "2026-10-22 07:45", None, ""),
    ("huit heures moins dix demain", True, "2026-10-22 07:50", None, ""),
    ("six heures samedi", True, "2026-10-24 06:00", None, ""),  # another day: the morning
    ("sept heures du soir demain", True, "2026-10-22 19:00", None, ""),
    ("dix-neuf heures trente", True, "2026-10-21 19:30", None, ""),
    ("19h30", True, "2026-10-21 19:30", None, ""),
    ("à 7 h 15 demain", True, "2026-10-22 07:15", None, ""),
    ("vingt-deux heures", True, "2026-10-21 22:00", None, ""),
    ("dix heures ce soir", True, "2026-10-21 22:00", None, ""),
    ("onze heures du soir", True, "2026-10-21 23:00", None, ""),
    ("cette nuit à trois heures", True, "2026-10-22 03:00", None, ""),
    ("à midi", True, "2026-10-22 12:00", None, ""),  # noon gone: tomorrow's
    ("à minuit", True, "2026-10-22 00:00", None, ""),
    ("midi et quart demain", True, "2026-10-22 12:15", None, ""),
    ("après-demain à midi", False, "2026-10-23 12:00", None, ""),
    ("lundi prochain à neuf heures", False, "2026-10-26 09:00", None, ""),
    ("dans trois jours à neuf heures", False, "2026-10-24 09:00", None, ""),
    ("trois heures de l'après-midi", False, "2026-10-21 15:00", None, ""),
    ("tous les jours de la semaine à six heures quarante-cinq", True, "2026-10-22 06:45", WEEKDAYS, ""),
    ("en semaine à sept heures", True, "2026-10-22 07:00", WEEKDAYS, ""),
    ("tous les jours à sept heures", True, "2026-10-22 07:00", "FREQ=DAILY", ""),
    ("le week-end à neuf heures", True, "2026-10-24 09:00", "FREQ=WEEKLY;BYDAY=SA,SU", ""),
    ("tous les lundis et mercredis à sept heures", True, "2026-10-26 07:00", "FREQ=WEEKLY;BYDAY=MO,WE", ""),
    ("dans vingt minutes", True, "2026-10-21 14:20", None, ""),
    ("dans une demi-heure", True, "2026-10-21 14:30", None, ""),
    ("dans une heure et demie", True, "2026-10-21 15:30", None, ""),
    ("dans deux heures", True, "2026-10-21 16:00", None, ""),
    # Reminders: what they are about, before or after when.
    ("à dix-sept heures d'appeler ma mère", False, "2026-10-21 17:00", None, "d'appeler ma mère"),
    ("d'appeler ma mère à cinq heures", False, "2026-10-21 17:00", None, "d'appeler ma mère"),
    ("que le plombier vient à trois heures vendredi", False, "2026-10-23 15:00", None, "que le plombier vient"),
    ("de sortir les poubelles tous les mardis à dix-neuf heures", False, "2026-10-27 19:00", "FREQ=WEEKLY;BYDAY=TU",
     "de sortir les poubelles"),
    ("dans dix minutes de surveiller le four", False, "2026-10-21 14:10", None, "de surveiller le four"),
    ("dans un quart d'heure de sortir le gâteau", False, "2026-10-21 14:15", None, "de sortir le gâteau"),
    ("demain à neuf heures d'appeler le dentiste", False, "2026-10-22 09:00", None, "d'appeler le dentiste"),
    # A length that is the reminder's, before its time.
    ("de me reposer dix minutes à dix-sept heures", False, "2026-10-21 17:00", None, "de me reposer dix minutes"),
]


@pytest.mark.parametrize(("said", "alarm", "start", "rrule", "rest"), WHEN)
def test_when(said, alarm, start, rrule, rest):
    found = calendar.when(said, NOW, alarm=alarm)
    assert found is not None
    assert found.start == datetime.fromisoformat(start).replace(tzinfo=TZ)
    assert (found.rrule, found.rest) == (rrule, rest)


FREE_TEXT = [
    # (said, alarm, start, rest): what the free text keeps of it. "Dans" and
    # "à" are filler at its start, so trimmed: a length in minutes alone is
    # from now; in hours, a clock time.
    ("vingt minutes", True, "2026-10-21 14:20", ""),
    ("dix minutes de surveiller le four", False, "2026-10-21 14:10", "de surveiller le four"),
    ("huit heures", True, "2026-10-21 20:00", ""),
    ("dix-sept heures d'appeler maman", False, "2026-10-21 17:00", "d'appeler maman"),
    ("pour sept heures et demie", True, "2026-10-21 19:30", ""),
    # Speech-to-text's "aujourd hui".
    ("aujourd hui à dix-sept heures", False, "2026-10-21 17:00", ""),
]


@pytest.mark.parametrize(("said", "alarm", "start", "rest"), FREE_TEXT)
def test_what_free_text_makes_of_it(said, alarm, start, rest):
    found = calendar.when(said, NOW, alarm=alarm)
    assert found is not None
    assert found.start == datetime.fromisoformat(start).replace(tzinfo=TZ) and found.rest == rest


@pytest.mark.parametrize("said", ["dans vingt minutes", "vingt minutes", "dans deux heures", "dans une demi-heure"])
def test_from_now(said):
    assert calendar.when(said, NOW, alarm=True).relative


@pytest.mark.parametrize("said", ["d'appeler maman", "", "demain", "de demain", "tous les lundis", "d'acheter deux baguettes"])
def test_no_time_is_none(said):
    assert calendar.when(said, NOW) is None


CLOCK = [
    ("midi", (12, 0, "pm")),
    ("midi et quart", (12, 15, "pm")),
    ("midi moins le quart", (11, 45, "am")),
    ("minuit et demie", (0, 30, "am")),
    ("après-demain à midi", (12, 0, "pm")),
    ("trois heures cet après-midi", (3, 0, "pm")),
    ("sept heures et demie", (7, 30, None)),
]


@pytest.mark.parametrize(("said", "time"), CLOCK)
def test_the_clock(said, time):
    assert reading.clock(said) == time


WHAT = [
    ("d'appeler ma mère", "appeler votre mère"),
    ("de sortir les poubelles", "sortir les poubelles"),
    ("que moi et ma sœur sommes sortis", "vous et votre sœur sommes sortis"),
    ("de m'appeler", "vous appeler"),
]


@pytest.mark.parametrize(("said", "back"), WHAT)
def test_what_is_said_back(said, back):
    assert calendar.what(said) == back


def test_what_a_reminder_is_about():
    assert calendar.about("mon rappel d'appeler maman demain") == ["appeler", "maman"]
    assert calendar.day("de demain", NOW) == NOW.date() + timedelta(days=1)
    assert calendar.day("pour vendredi", NOW) == NOW.date() + timedelta(days=2)
    assert calendar.wants_time("tous les lundis") and calendar.wants_time("demain")
    assert not calendar.wants_time("d'appeler maman")


# ---------------------------------------------------------------- speaking

def _event(uid, hour, minute=0, days=1, kind="alarm", rrule=None, summary="Réveil"):
    start = NOW.replace(hour=hour, minute=minute) + timedelta(days=days)
    return alarms.Event(uid, start, summary, kind, rrule=rrule)


SEVEN = _event("1", 7)
SEVEN_PM = _event("2", 19)
EVERY_WEEKDAY = _event("3", 6, 30, rrule=WEEKDAYS)
CALL = _event("4", 17, days=0, kind="reminder", summary="Appeler votre mère")
DENTIST = _event("5", 9, days=1, kind="reminder", summary="Appeler le dentiste")
BINS = _event("6", 8, days=6, kind="reminder", summary="Sortir les poubelles")

SAID = [
    # (operation, slots, alarms, reminders, outcome, what is said)
    ("alarm", {"time": "sept heures et demie demain"}, [], [], "done", "Réveil réglé demain à 7 heures 30."),
    ("alarm", {"time": "tous les jours de la semaine à six heures quarante-cinq"}, [], [], "done",
     "Réveil réglé à 6 heures 45 tous les jours de la semaine."),
    ("alarm", {"time": "vendredi à midi"}, [], [], "done", "Réveil réglé après-demain à midi."),
    ("alarm", {"time": "samedi à sept heures"}, [], [], "done", "Réveil réglé samedi à 7 heures."),
    ("alarm", {}, [], [], "missing_time", "Pour quelle heure dois-je mettre le réveil ?"),
    ("reminder", {"reminder": "à dix-sept heures d'appeler ma mère"}, [], [], "done",
     "Je vous rappellerai d'appeler votre mère à 17 heures."),
    ("reminder", {"reminder": "dix minutes de surveiller le four"}, [], [], "done",
     "Je vous rappellerai de surveiller le four dans 10 minutes."),
    ("reminder", {"reminder": "vendredi à quinze heures que le plombier vient"}, [], [], "done",
     "Je vous le rappellerai après-demain à 15 heures : le plombier vient."),
    ("reminder", {"reminder": "d'acheter du lait"}, [], [], "listed", "J'ai ajouté acheter du lait à vos rappels."),
    ("reminder", {"reminder": "d'acheter du lait demain"}, [], [], "missing_time", "Quand dois-je vous le rappeler ?"),
    ("reminder", {"reminder": "à cinq heures"}, [], [], "missing_reminder", "Que dois-je vous rappeler ?"),
    ("cancel_alarm", {"time": "sept heures"}, [SEVEN, EVERY_WEEKDAY], [], "done", "J'ai annulé le réveil de demain à 7 heures."),
    ("cancel_alarm", {"time": "sept heures du soir"}, [SEVEN, SEVEN_PM], [], "done",
     "J'ai annulé le réveil de demain à 19 heures."),
    ("cancel_alarm", {"time": "huit heures"}, [SEVEN], [], "not_found",
     "Il n'y a pas de réveil à 20 heures. Vous avez un réveil demain à 7 heures."),
    ("cancel_alarm", {}, [SEVEN, EVERY_WEEKDAY], [], "ambiguous",
     "Quel réveil ? Vous avez le réveil de demain à 7 heures et le réveil de 6 heures 30 tous les jours de la semaine."),
    ("cancel_alarm", {}, [], [], "no_alarms", "Aucun réveil n'est réglé."),
    ("cancel_reminder", {"reminder": "d'appeler ma mère"}, [], [CALL, DENTIST, BINS], "done",
     "J'ai annulé le rappel de 17 heures : Appeler votre mère."),
    ("cancel_reminder", {"reminder": "concernant le dentiste"}, [], [CALL, DENTIST, BINS], "done",
     "J'ai annulé le rappel de demain à 9 heures : Appeler le dentiste."),
    ("cancel_reminder", {"reminder": "de nourrir le chat"}, [], [CALL], "not_found",
     "Je ne trouve pas ce rappel. Vous avez un rappel : Appeler votre mère à 17 heures."),
    ("cancel_reminder", {}, [], [], "no_reminders", "Vous n'avez aucun rappel."),
    ("alarm_status", {}, [SEVEN], [], "done", "Vous avez un réveil demain à 7 heures."),
    ("alarm_status", {}, [SEVEN, EVERY_WEEKDAY], [], "done",
     "Vous avez 2 réveils : demain à 7 heures et à 6 heures 30 tous les jours de la semaine."),
    ("reminder_status", {}, [], [CALL, BINS], "done",
     "Vous avez 2 rappels : Appeler votre mère à 17 heures et Sortir les poubelles mardi à 8 heures."),
]


@pytest.mark.parametrize(("operation", "slots", "alarms_set", "reminders", "outcome", "said"), SAID)
def test_what_each_says(operation, slots, alarms_set, reminders, outcome, said):
    plan = alarms.plan(operation, slots, NOW, alarms_set, reminders, todo=True)
    assert (plan.outcome, plan.speech) == (outcome, said)


def test_an_alarm_on_the_calendar():
    plan = alarms.plan("alarm", {"time": "sept heures et demie demain"}, NOW, [], [])
    assert plan.create == {"kind": "alarm", "summary": "Réveil", "start": NOW.replace(hour=7, minute=30) + timedelta(days=1),
                           "rrule": None}
    assert plan.levels["verbose"] == "Réveil réglé demain à 7 heures 30, dans 17 heures et 30 minutes."
    reminder = alarms.plan("reminder", {"reminder": "à dix-sept heures d'appeler ma mère"}, NOW, [], [], todo=True)
    assert reminder.create["summary"] == "Appeler votre mère"


def test_which_is_asked():
    which = alarms.plan("cancel_alarm", {"time": "sept heures"}, NOW, [SEVEN, SEVEN_PM], [])
    assert which.outcome == "ambiguous" and [c["id"] for c in which.choices] == ["1", "2"]
    assert which.question == "Le réveil de demain à 7 heures ou le réveil de demain à 19 heures ?"
    assert [c["label"] for c in which.choices] == ["le réveil de demain à 7 heures", "le réveil de demain à 19 heures"]
    reminders = alarms.plan("cancel_reminder", {"reminder": "d'appeler"}, NOW, [], [CALL, DENTIST])
    assert reminders.question == "Appeler votre mère à 17 heures ou Appeler le dentiste demain à 9 heures ?"
    # "Les deux": each of them.
    assert alarms.plan("cancel_alarm", {}, NOW, [SEVEN, EVERY_WEEKDAY], [], every=True).delete == [SEVEN, EVERY_WEEKDAY]


def test_when_it_rings():
    assert calendar.alarm_due("Réveil", SEVEN.start) == "Il est 7 heures."
    assert calendar.alarm_due("Médicaments", SEVEN.start) == "Médicaments. Il est 7 heures."
    assert calendar.alarm_due("", NOW.replace(hour=12, minute=30)) == "Il est midi 30."
    assert calendar.reminder_due("Appeler maman.") == "Rappel : Appeler maman."
    assert calendar.said_when(NOW.replace(hour=9) + timedelta(days=11), None, NOW) == "le 1er novembre à 9 heures"

