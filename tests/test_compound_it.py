"""Two commands said together, in Italian (voice_incubator/compound.py with
voice_incubator/languages/it/compound.py): where a sentence may split, "e"
within an amount or a time, and what both say as one sentence. Each case is a
row: a native speaker reviewing adds one where Italian is said otherwise."""

from __future__ import annotations

from pathlib import Path

import pytest

from voice_incubator import compound, languages
from voice_incubator.languages.it import compound as italian

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def in_italian():
    languages.use("it")
    yield
    languages.use(languages.DEFAULT)


@pytest.mark.parametrize(
    ("said", "splits"),
    [
        ("chiudi la porta a chiave e poi spegni la luce", [(5, 7)]),
        ("spegni la luce e chiudi le tapparelle", [(3, 4)]),
        ("spegni la luce poi chiudi la porta", [(3, 4)]),
        ("accendi la luce ed apri le tapparelle", [(3, 4)]),
        ("e spegni la luce e", []),  # nothing on one side
        # "E" within an amount or a time joins no commands.
        ("imposta un timer di un'ora e mezza", []),
        ("imposta un timer di 1 ora e 30 secondi", []),
        ("imposta un timer di due minuti e mezzo", []),
        ("imposta un timer di un'ora e un quarto", []),
        ("svegliami alle sette e mezza", []),
        ("svegliami alle sette e quaranta", []),
        ("imposta un timer di 5 minuti e un timer di 10 minuti", [(6, 7)]),
    ],
)
def test_where_a_sentence_may_split(said, splits):
    assert compound.splits(said.split()) == splits


@pytest.mark.parametrize(
    ("before", "after", "amount"),
    [
        ("un'ora", "mezza", True),
        ("due ore", "trenta minuti", True),
        ("sette", "un quarto", True),
        ("ventuno", "tre quarti", True),
        ("minuti", "spegni la luce", False),
        ("la luce", "chiudi la porta", False),
        ("", "mezza", False),
    ],
)
def test_e_within_an_amount(before, after, amount):
    assert italian.within_an_amount(before.split(), after.split()) == amount


@pytest.mark.parametrize(
    ("first", "second", "said"),
    [
        ("Ho spento la luce.", "Ho spento la TV.", "Ho spento la luce e la TV."),
        ("Ho acceso la luce.", "Ho spento la TV.", "Ho acceso la luce e ho spento la TV."),
        ("Ho spento Piantana.", "Ho spento Lampada piccola.", "Ho spento Piantana e Lampada piccola."),
        ("Ho spento la luce.", "Ho spento l'ingresso.", "Ho spento la luce e l'ingresso."),
        ("Luce accesa.", "Chiudo la porta.", "Luce accesa e chiudo la porta."),
        ("Ho acceso la TV.", "TV: spento.", "Ho acceso la TV e TV: spento."),
        ("Luce spenta.", "Luce spenta.", "Luce spenta."),
    ],
)
def test_what_both_say_is_one_sentence(first, second, said):
    assert italian.both(first, second) == said


def test_what_both_say():
    assert compound.both("", "") == ""  # the acknowledgement sound, once
    assert compound.both("Luce accesa.", "") == "Luce accesa."
    assert compound.joiners() == ("e poi", "e dopo", "e", "ed", "poi")
    assert compound.alone("annullare tutti i timer") == "Chiedimi di annullare tutti i timer in una richiesta a parte."


@pytest.mark.parametrize(
    ("slots", "said"),
    [
        ({"entity": ["light.piantana"]}, "la Piantana"),
        ({"entity": ["media_player.tv", "light.lampadario"]}, "la TV e il Lampadario"),
        ({"area": ["cucina"]}, "in Cucina"),
        ({"area": ["camera"]}, "in Camera da letto"),
        ({"floor": ["primo_piano"]}, "al Primo piano"),
    ],
)
def test_what_the_first_named_said_again(slots, said):
    names = {"entities": {"light.piantana": {"name": "Piantana"}, "media_player.tv": {"name": "TV"},
                          "light.lampadario": "Lampadario"},
             "areas": {"cucina": {"name": "Cucina"}, "camera": "Camera da letto"},
             "floors": {"primo_piano": {"name": "Primo piano"}}}
    assert compound.target(slots, names, {}) == said


@pytest.fixture(name="engine", scope="module")
def fixture_engine():
    """Italian's library (but the timers) in a home with a TV and a floor
    lamp, and a satellite in the Studio."""
    from voice_incubator.engine import Engine, Satellite  # pylint: disable=import-outside-toplevel
    from voice_incubator.library import load_library  # pylint: disable=import-outside-toplevel
    from voice_incubator.store import compile_store  # pylint: disable=import-outside-toplevel

    pack = languages.use("it")
    if pack.missing(ROOT):
        pytest.skip("no Italian models")
    entries = [e for e in load_library() if e["file"] != "timers"]
    store = {
        "language": "it",
        "names": {
            "entities": {"media_player.tv": {"name": "TV"}, "light.piantana": {"name": "Piantana"}},
            "areas": {"cucina": {"name": "Cucina"}, "camera": {"name": "Camera da letto"}, "studio": {"name": "Studio"}},
        },
        "lists": {name: values for e in entries for name, values in e["lists"].items()},
        "commands": {e["id"]: e["spec"] for e in entries},
    }
    engine = Engine(pack.ctc_dir(ROOT), pack.transducer_dir(ROOT), None, threads=2)
    engine.build(compile_store(store))
    yield engine, Satellite("s", "Studio", "studio", "Studio")
    languages.use(languages.DEFAULT)


def heard(decision):
    """Each command a decision runs, with what it acts on."""
    out = []
    while decision is not None and decision.command is not None:
        out.append((decision.command.id, decision.slots.get("entity") or decision.slots.get("area")))
        decision = decision.then
    return out


@pytest.mark.parametrize(
    ("text", "commands"),
    [
        ("spegni la luce e chiudi le tapparelle", [("turn_off_here", None), ("close_covers_here", None)]),
        # A second that names nothing acts on what the first named: its device, its area.
        # (With "e" alone the matcher takes the "e" in, and the whole is one
        # command with "accendi" unexplained.)
        ("accendi la piantana e poi imposta la luminosità al cinquanta per cento",
         [("turn_on_device", ["light.piantana"]), ("set_brightness_device", ["light.piantana"])]),
        ("accendi la luce in cucina e poi imposta la luminosità al cinquanta per cento",
         [("turn_on_place", ["cucina"]), ("set_brightness_place", ["cucina"])]),
        ("accendi la luce in cucina poi imposta la luminosità al cinquanta per cento",
         [("turn_on_place", ["cucina"]), ("set_brightness_place", ["cucina"])]),
        # One command, whole: "e" is part of it.
        ("aggiungi mele e banane alla lista della spesa", [("shopping_list_add", None)]),
    ],
)
def test_typed(engine, text, commands):
    engine, studio = engine
    assert heard(engine.recognize_text(text, studio)) == commands
