"""Two commands said together in Dutch (voice_incubator/compound.py, with the
Dutch words, voice_incubator/languages/nl/compound.py): where a sentence
splits, "en" within an amount, and what both say as one sentence.

Each table is a list of cases: add a row to check another sentence."""

from __future__ import annotations

import pytest

from voice_incubator import compound, languages
from voice_incubator.languages.nl import compound as dutch


@pytest.fixture(autouse=True)
def in_dutch():
    languages.use("nl")
    yield
    languages.use(languages.DEFAULT)


@pytest.mark.parametrize(
    ("sentence", "splits"),
    [
        ("doe het licht uit en zet de tv aan", [(4, 5)]),
        ("doe het licht uit en dan de tv", [(4, 6)]),
        ("doe het licht uit en daarna de tv", [(4, 6)]),
        ("doe het licht uit dan de tv aan", [(4, 5)]),
        ("en doe het licht uit en", []),  # nothing on one side
        # "En" within an amount joins no commands.
        ("zet een timer van een uur en tien minuten", []),
        ("zet een timer van twee en een half uur", []),
        ("zet een timer van een uur en een kwartier", []),
        ("zet het volume op honderd en vijftig", []),
        ("zet een timer van vijf minuten en een timer van tien minuten", [(6, 7)]),
    ],
)
def test_where_a_sentence_may_split(sentence, splits):
    assert compound.splits(sentence.split()) == splits


@pytest.mark.parametrize(
    ("before", "after", "within"),
    [
        ("een uur", "tien minuten", True),
        ("twee", "een half uur", True),
        ("een uur", "een kwartier", True),
        ("honderd", "vijftig", True),
        ("vijf minuten", "een timer van tien minuten", False),
        ("doe het licht uit", "zet de tv aan", False),
    ],
)
def test_en_within_an_amount(before, after, within):
    assert dutch.within_an_amount(before.split(), after.split()) is within


@pytest.mark.parametrize(
    ("first", "second", "said"),
    [
        # What both end with -- the verb -- said once.
        ("Staande lamp uitgezet.", "Kleine lamp uitgezet.", "Staande en kleine lamp uitgezet."),
        ("Licht in de keuken aan.", "Licht in de woonkamer aan.", "Licht in de keuken en de woonkamer aan."),
        ("Thermostaat op 21 graden gezet.", "Licht op 50 procent gezet.", "Thermostaat op 21 graden en licht op 50 procent gezet."),
        # What both start with, said once.
        ("Ik open de rolluiken.", "Ik open de gordijnen.", "Ik open de rolluiken en de gordijnen."),
        ("Ik open de rolluiken.", "Ik sluit de gordijnen.", "Ik open de rolluiken en ik sluit de gordijnen."),
        # Neither.
        ("Tv aangezet.", "Volume op 50 procent gezet.", "Tv aangezet en volume op 50 procent gezet."),
        ("Licht in de keuken uit.", "Licht in de keuken uit.", "Licht in de keuken uit."),
    ],
)
def test_what_both_say_is_one_sentence(first, second, said):
    assert dutch.both(first, second) == said


@pytest.mark.parametrize(
    ("names", "said"),
    [(["Tv"], "de Tv"), (["Staande lamp", "Dakraam"], "de Staande lamp en het Dakraam")],
)
def test_the_devices_said_again(names, said):
    assert dutch.devices(names) == said


def test_a_second_command_acts_on_what_the_first_named():
    """What the first named, said after a second that names nothing: its
    devices, else its areas or floors (the language's place)."""
    names = {"entities": {"media_player.tv": "Tv"}, "areas": {"keuken": "Keuken"}, "floors": {"boven": "Eerste verdieping"}}
    assert compound.target({"entity": ["media_player.tv"]}, names, {}) == "de Tv"
    assert compound.target({"area": ["keuken"]}, names, {}) == "in de Keuken"
    assert compound.target({"floor": ["boven"]}, names, {}) == "op de eerste verdieping"


def test_what_both_say():
    assert compound.joiners() == ("en daarna", "en dan", "en", "daarna", "dan")
    assert compound.both("", "Licht uit.") == "Licht uit."
    assert compound.alone("alle timers annuleren") == "Vraag me dat apart: alle timers annuleren."
