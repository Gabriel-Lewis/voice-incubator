"""Two commands said together in Ukrainian (voice_incubator/compound.py with
voice_incubator/languages/uk/compound.py): where a sentence may split, "і"
within an amount, what both say as one sentence, the devices or place a
second command borrows -- and, typed through the engine, which commands a
sentence runs (as tests/test_compound.py does for English).

The cases are tables: a native speaker adds a row for a sentence."""

from __future__ import annotations

from pathlib import Path

import pytest

from voice_incubator import compound, languages
from voice_incubator.languages.uk import compound as ukrainian

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def in_ukrainian():
    languages.use("uk")
    yield
    languages.use(languages.DEFAULT)


def test_the_joining_words():
    assert compound.joiners() == ("а потім", "і потім", "та потім", "і", "й", "та", "потім")


@pytest.mark.parametrize(
    ("said", "splits"),
    [
        ("увімкни світло і вимкни телевізор", [(2, 3)]),
        ("замкни двері а потім вимкни світло", [(2, 4)]),
        ("вимкни світло потім замкни двері", [(2, 3)]),
        ("вимкни нічник й торшер", [(2, 3)]),
        ("і вимкни світло і", []),  # nothing on one side
        # "І" within an amount joins no commands.
        ("постав таймер на годину і десять хвилин", []),
        ("постав таймер на дві години і тридцять секунд", []),
        ("постав таймер на годину і пів", []),
        ("сто і п'ять", []),
        ("постав таймер на п'ять хвилин і таймер на десять хвилин", [(5, 6)]),
    ],
)
def test_where_a_sentence_may_split(said, splits):
    assert compound.splits(said.split()) == splits


@pytest.mark.parametrize(
    ("before", "after", "within"),
    [
        ("на годину", "десять хвилин", True),
        ("дві години", "тридцять секунд", True),
        ("на годину", "пів", True),
        ("сто", "п'ять", True),
        ("на п'ять хвилин", "таймер на десять хвилин", False),
        ("увімкни світло", "вимкни телевізор", False),
    ],
)
def test_and_within_an_amount(before, after, within):
    assert ukrainian.within_an_amount(before.split(), after.split()) is within


@pytest.mark.parametrize(
    ("first", "second", "said"),
    [
        ("Увімкнено: Торшер.", "Увімкнено: Нічник.", "Увімкнено: Торшер і Нічник."),
        ("Вимкнено: Телевізор.", "Вимкнено: Вентилятор.", "Вимкнено: Телевізор і Вентилятор."),
        ("Світло увімкнено.", "Вимкнено: Телевізор.", "Світло увімкнено і вимкнено: Телевізор."),
        ("Світло на кухні увімкнено.", "Світло у вітальні увімкнено.",
         "Світло на кухні увімкнено і світло у вітальні увімкнено."),
        ("Замикаю: Вхідні двері.", "Світло вимкнено.", "Замикаю: Вхідні двері і світло вимкнено."),
        ("Світло увімкнено.", "Світло увімкнено.", "Світло увімкнено."),
    ],
)
def test_what_both_say_is_one_sentence(first, second, said):
    assert ukrainian.both(first, second) == said


def test_what_both_say():
    assert compound.both(None, None) is None  # both silent
    assert compound.both("", "") == ""  # the acknowledgement sound, once
    assert compound.both("Світло увімкнено.", "") == "Світло увімкнено."
    assert compound.both("Увімкнено: Торшер.", "Увімкнено: Нічник.") == "Увімкнено: Торшер і Нічник."
    assert compound.alone("скасувати всі таймери") == "Попроси мене скасувати всі таймери окремо."


@pytest.mark.parametrize(
    ("slots", "said"),
    [
        ({"entity": ["media_player.tv"]}, "Телевізор"),
        ({"entity": ["media_player.tv", "light.lamp"]}, "Телевізор і Торшер"),
        ({"area": ["kitchen"]}, "на кухні"),
        ({"area": ["living_room"]}, "у вітальні"),
        ({"floor": ["first"]}, "на першому поверсі"),
        ({}, None),
    ],
)
def test_what_a_second_command_borrows(slots, said):
    """What the first command named, said again after a second that names
    nothing ("увімкни телевізор і встанови гучність на п'ятдесят"): its
    devices by name, else its place in its case."""
    names = {"entities": {"media_player.tv": {"name": "Телевізор"}, "light.lamp": {"name": "Торшер"}},
             "areas": {"kitchen": {"name": "Кухня"}, "living_room": {"name": "Вітальня"}},
             "floors": {"first": {"name": "Перший поверх"}}}
    assert compound.target(slots, names, {}) == said


def test_devices_are_named_as_they_are():
    assert ukrainian.devices(["Телевізор"]) == "Телевізор"
    assert ukrainian.devices(["Телевізор", "Торшер", "Нічник"]) == "Телевізор і Торшер і Нічник"


@pytest.fixture(name="engine", scope="module")
def fixture_engine():
    """The Ukrainian library (but the timers) in a home with a TV, two lamps,
    a fan and a front door, and a satellite in its Кабінет."""
    from voice_incubator.engine import Engine, Satellite  # pylint: disable=import-outside-toplevel
    from voice_incubator.library import load_library  # pylint: disable=import-outside-toplevel
    from voice_incubator.store import compile_store  # pylint: disable=import-outside-toplevel

    pack = languages.use("uk")
    if pack.missing(ROOT):
        pytest.skip("no Ukrainian models")
    entries = [e for e in load_library() if e["file"] != "timers"]
    store = {
        "language": "uk",
        "names": {
            "entities": {
                "media_player.tv": {"name": "Телевізор"}, "light.nichnyk": {"name": "Нічник"},
                "light.nastilna_lampa": {"name": "Настільна лампа"}, "fan.ventyliator": {"name": "Вентилятор"},
                "lock.vkhidni_dveri": {"name": "Вхідні двері"},
            },
            "areas": {"kukhnia": {"name": "Кухня"}, "spalnia": {"name": "Спальня"}, "vitalnia": {"name": "Вітальня"},
                      "kabinet": {"name": "Кабінет"}},
        },
        "lists": {name: values for e in entries for name, values in e["lists"].items()},
        "commands": {e["id"]: e["spec"] for e in entries},
    }
    engine = Engine(pack.ctc_dir(ROOT), pack.transducer_dir(ROOT), None, threads=2)
    engine.build(compile_store(store))
    yield engine, Satellite("s", "Кабінет", "kabinet", "Кабінет")
    languages.use(languages.DEFAULT)


def heard(decision):
    """Each command a decision runs, with what it acts on."""
    out = []
    while decision is not None and decision.command is not None:
        out.append((decision.command.id, decision.slots.get("entity") or decision.slots.get("area")))
        decision = decision.then
    return out


ROUTES = [
    # Two commands.
    ("увімкни світло і вимкни вентилятор", [("turn_on_here", None), ("turn_off_device", ["fan.ventyliator"])]),
    ("замкни вхідні двері а потім вимкни світло", [("lock", ["lock.vkhidni_dveri"]), ("turn_off_here", None)]),
    ("вимкни світло потім замкни вхідні двері", [("turn_off_here", None), ("lock", ["lock.vkhidni_dveri"])]),
    # One command, two targets: the second borrows the first's verb.
    ("вимкни нічник і настільну лампу", [("turn_off_device", ["light.nichnyk"]),
                                         ("turn_off_device", ["light.nastilna_lampa"])]),
    ("увімкни світло на кухні і у вітальні", [("turn_on_place", ["kukhnia"]), ("turn_on_place", ["vitalnia"])]),
    # A second that names nothing acts on what the first named.
    ("увімкни світло на кухні і встанови яскравість на п'ятдесят відсотків",
     [("turn_on_place", ["kukhnia"]), ("set_brightness_place", ["kukhnia"])]),
    ("увімкни настільну лампу і встанови яскравість на тридцять відсотків",
     [("turn_on_device", ["light.nastilna_lampa"]), ("set_brightness_device", ["light.nastilna_lampa"])]),
    # One command, whole: "і" is part of it -- a list's items.
    ("додай яблука і банани до списку покупок", [("shopping_list_add", None)]),
    # Not two commands: neither runs, not half.
    ("вимкни світло і добраніч", []),
]


@pytest.mark.parametrize(("text", "commands"), ROUTES)
def test_typed(engine, text, commands):
    engine, office = engine
    assert heard(engine.recognize_text(text, office)) == commands
