"""Two commands said together in Polish (voice_incubator/compound.py, with
voice_incubator/languages/pl/compound.py): where a sentence may split, what
both say as one sentence -- and, typed through the CTC model, the commands
heard. Rows are data: add one for each phrasing that should work."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from voice_incubator import compound, languages
from voice_incubator.languages.pl import compound as polish

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def in_polish():
    languages.use("pl")
    yield
    languages.use(languages.DEFAULT)


@pytest.mark.parametrize(
    ("said", "splits"),
    [
        ("zablokuj drzwi i potem wyłącz światło", [(2, 4)]),
        ("zablokuj drzwi a potem wyłącz światło", [(2, 4)]),
        ("wyłącz światło potem zablokuj drzwi", [(2, 3)]),
        ("i wyłącz światło i", []),  # nothing on one side
        # "I" within an amount joins no commands.
        ("ustaw minutnik na godzinę i dziesięć minut", []),
        ("ustaw minutnik na jedną minutę i 30 sekund", []),
        ("ustaw minutnik na dwa i pół minuty", []),
        ("ustaw minutnik na godzinę i kwadrans", []),
        ("minutnik na pięć minut i minutnik na dziesięć minut", [(4, 5)]),
    ],
)
def test_where_a_sentence_may_split(said, splits):
    assert compound.splits(said.split()) == splits


@pytest.mark.parametrize(
    ("first", "second", "said"),
    [
        ("Wyłączono światło.", "Wyłączono Telewizor.", "Wyłączono światło i Telewizor."),
        ("Włączono światło.", "Wyłączono Telewizor.", "Włączono światło i wyłączono Telewizor."),
        ("Wyłączono światło w kuchni.", "Wyłączono światło w sypialni.", "Wyłączono światło w kuchni i w sypialni."),
        ("Ustawiono jasność w salonie na 50 procent.", "Ustawiono głośność na 30 procent.",
         "Ustawiono jasność w salonie na 50 procent i głośność na 30 procent."),
        # A name the sentences start with is said whole each time.
        ("Lampa stojąca wyłączona.", "Lampka nocna wyłączona.", "Lampa stojąca wyłączona i Lampka nocna wyłączona."),
        ("Zablokowano.", "Nie, światła są wyłączone.", "Zablokowano i nie, światła są wyłączone."),
        ("Włączono światło.", "Włączono światło.", "Włączono światło."),
    ],
)
def test_what_both_say_is_one_sentence(first, second, said):
    assert polish.both(first, second) == said


@pytest.mark.parametrize(
    ("names", "said"),
    [(["Telewizor"], "Telewizor"), (["Telewizor", "Lampa stojąca"], "Telewizor i Lampa stojąca")],
)
def test_the_devices_said_again(names, said):
    assert polish.devices(names) == said


def test_said_again_after_a_command_that_named_nothing():
    names = {"entities": {"light.lampa": {"name": "Lampa stojąca"}}, "areas": {"kuchnia": {"name": "Kuchnia"}}}
    assert compound.target({"entity": ["light.lampa"]}, names, {}) == "Lampa stojąca"
    assert compound.target({"area": ["kuchnia"]}, names, {}) == "w kuchni"


def test_what_both_say():
    assert compound.joiners() == ("a potem", "i potem", "i", "potem")
    assert compound.both("Włączono światło.", "") == "Włączono światło."
    assert compound.alone("anulować wszystkie minutniki") == "Żeby anulować wszystkie minutniki, poproś mnie o to osobno."


ROUTES = [
    ("Włącz światło w kuchni i wyłącz lampę stojącą.", [("turn_on_place", ["kuchnia"]), ("turn_off_device", ["light.lampa_stojaca"])]),
    ("Zablokuj drzwi wejściowe a potem wyłącz światło.", [("lock", ["lock.drzwi_wejsciowe"]), ("turn_off_here", None)]),
    # One command, two targets: the second borrows the first's verb.
    ("Wyłącz lampę stojącą i lampkę nocną.", [("turn_off_device", ["light.lampa_stojaca"]),
                                              ("turn_off_device", ["light.lampka_nocna"])]),
    ("Włącz światło w salonie i w sypialni.", [("turn_on_place", ["salon"]), ("turn_on_place", ["sypialnia"])]),
    # The second acts on what the first named.
    ("Włącz lampę stojącą i ustaw jasność na pięćdziesiąt procent.", [("turn_on_device", ["light.lampa_stojaca"]),
                                                                     ("set_brightness_device", ["light.lampa_stojaca"])]),
    # One command: "i" between its items.
    ("Dodaj jabłka i banany do listy zakupów.", [("shopping_list_add", None)]),
]


@pytest.fixture(name="engine", scope="module")
def fixture_engine():
    """The Polish library in its bench's home (bench.yaml)."""
    languages.use("pl")
    if languages.current().missing(ROOT):
        pytest.skip("no Polish models")
    spec = importlib.util.spec_from_file_location("bench_language", ROOT / "scripts/bench_language.py")
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    data = bench.bench("pl")
    return bench.engine_for(data, threads=2), bench.satellite_for(data)


@pytest.mark.parametrize(("said", "commands"), ROUTES)
def test_two_commands_typed(engine, said, commands):
    engine, satellite = engine
    decision = engine.recognize_text(said, satellite)
    heard = []
    while decision is not None and decision.command is not None:
        heard.append((decision.command.id, decision.slots.get("entity") or decision.slots.get("area")))
        decision = decision.then
    assert heard == commands
