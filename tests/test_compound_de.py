"""Two commands said together in German (voice_incubator/compound.py, with
voice_incubator/languages/de/compound.py): where a sentence splits, "und"
within an amount, and what both say as one sentence.

Native speakers: add a row to a table to check another sentence."""

from __future__ import annotations

import pytest

from voice_incubator import compound, languages
from voice_incubator.languages.de import compound as german


@pytest.fixture(autouse=True)
def in_german():
    languages.use("de")
    yield
    languages.use(languages.DEFAULT)


@pytest.mark.parametrize(
    ("sentence", "splits"),
    [
        ("schalte das licht aus und dann spiel jazz", [(4, 6)]),
        ("schalte das licht aus und schließ die haustür ab", [(4, 5)]),
        ("schließ die haustür ab dann mach das licht aus", [(4, 5)]),
        ("schalte das licht aus danach spiel jazz", [(4, 5)]),
        ("und schalte das licht aus und", []),  # nothing on one side
        # "Und" within an amount joins no commands.
        ("stell einen timer für eine stunde und dreißig minuten", []),
        ("stell einen timer für eine stunde und eine halbe", []),
        ("stell einen timer für 1 stunde und 30 sekunden", []),
        ("fünf und zwanzig", []),
        ("stell einen timer für fünf minuten und einen timer für zehn minuten", [(6, 7)]),
    ],
)
def test_where_a_sentence_may_split(sentence, splits):
    assert compound.splits(sentence.split()) == splits


@pytest.mark.parametrize(
    ("before", "after", "within"),
    [
        (["eine", "stunde"], ["dreißig", "minuten"], True),
        (["zwei", "stunden"], ["eine", "minute"], True),
        (["eine", "stunde"], ["eine", "halbe"], True),
        (["fünf"], ["zwanzig"], True),
        (["licht", "aus"], ["spiel", "jazz"], False),
        (["fünf", "minuten"], ["einen", "timer"], False),
        ([], ["zwanzig"], False),
    ],
)
def test_within_an_amount(before, after, within):
    assert german.within_an_amount(before, after) is within


@pytest.mark.parametrize(
    ("first", "second", "said"),
    [
        # The same end -- what was done -- said once.
        ("Licht ausgeschaltet.", "Fernseher ausgeschaltet.", "Licht und Fernseher ausgeschaltet."),
        ("Licht in der Küche eingeschaltet.", "Licht im Wohnzimmer eingeschaltet.",
         "Licht in der Küche und Licht im Wohnzimmer eingeschaltet."),
        ("Thermostat auf 21 Grad gestellt.", "Licht auf 50 Prozent gestellt.", "Thermostat auf 21 Grad und Licht auf 50 Prozent gestellt."),
        # The same start said once.
        ("Ich spiele Jazz.", "Ich spiele Rock.", "Ich spiele Jazz und Rock."),
        # Neither: both whole, a noun keeping its capital.
        ("Licht eingeschaltet.", "Fernseher ausgeschaltet.", "Licht eingeschaltet und Fernseher ausgeschaltet."),
        ("Stehlampe eingeschaltet.", "Kleiner Ventilator ausgeschaltet.", "Stehlampe eingeschaltet und Kleiner Ventilator ausgeschaltet."),
        ("Pizza-Timer gestartet.", "Ich spiele Jazz.", "Pizza-Timer gestartet und ich spiele Jazz."),
        ("Licht eingeschaltet.", "Licht eingeschaltet.", "Licht eingeschaltet."),
        # More than one sentence: one after the other.
        ("Licht eingeschaltet.", "Ja. Die Haustür ist abgeschlossen.", "Licht eingeschaltet. Ja. Die Haustür ist abgeschlossen."),
    ],
)
def test_what_both_say_is_one_sentence(first, second, said):
    assert german.both(first, second) == said


def test_what_both_say():
    assert compound.joiners() == ("und dann", "und danach", "und", "dann", "danach")
    assert compound.both("Licht ausgeschaltet.", "") == "Licht ausgeschaltet."
    assert compound.alone("alle Timer abbrechen") == "Bitte sag mir einzeln, dass ich alle Timer abbrechen soll."


def test_what_a_command_named_said_again():
    """A second command that names nothing acts on what the first named, said
    again in German (compound.target): its devices, else its area or floor."""
    names = {"entities": {"light.stehlampe": {"name": "Stehlampe"}, "media_player.tv": "Fernseher"},
             "areas": {"kueche": "Küche"}, "floors": {"obergeschoss": "Obergeschoss"}}
    assert german.devices(["Fernseher", "Stehlampe"]) == "Fernseher und Stehlampe"
    assert compound.target({"entity": ["light.stehlampe", "media_player.tv"]}, names, {}) == "Stehlampe und Fernseher"
    assert compound.target({"area": ["kueche"]}, names, {}) == "in der Küche"
    assert compound.target({"floor": ["obergeschoss"]}, names, {}) == "im Obergeschoss"
    assert compound.target({}, names, {}) is None


@pytest.fixture(name="bench_engine", scope="module")
def fixture_bench_engine():
    """The German library in the bench's home (scripts/bench_language.py),
    typed; skipped without the German models."""
    import importlib.util  # pylint: disable=import-outside-toplevel
    from pathlib import Path  # pylint: disable=import-outside-toplevel

    root = Path(__file__).resolve().parent.parent
    pack = languages.use("de")
    try:
        if pack.missing(root):
            pytest.skip("no German models")
        spec = importlib.util.spec_from_file_location("bench_language", root / "scripts/bench_language.py")
        bench = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bench)
        data = bench.bench("de")
        yield bench.engine_for(data, threads=2), bench.satellite_for(data)
    finally:
        languages.use(languages.DEFAULT)


@pytest.mark.parametrize(
    ("text", "first", "then"),
    [
        ("Schalte die Stehlampe ein und stell die Helligkeit auf fünfzig Prozent.",
         ("turn_on_device", {"entity": ["light.stehlampe"]}),
         ("set_brightness_device", {"entity": ["light.stehlampe"], "percentage": 50})),
        ("Schalte das Licht in der Küche ein und stell die Helligkeit auf fünfzig Prozent.",
         ("turn_on_place", {"area": ["kueche"]}),
         ("set_brightness_place", {"area": ["kueche"], "percentage": 50})),
    ],
)
def test_the_second_acts_on_what_the_first_named(bench_engine, text, first, then):
    engine, satellite = bench_engine
    decision = engine.recognize_text(text, satellite)
    assert decision.command is not None and decision.then is not None and decision.then.command is not None
    assert (decision.command.id, decision.slots) == first
    assert (decision.then.command.id, decision.then.slots) == then
