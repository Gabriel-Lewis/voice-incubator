"""Two commands said together, in French (voice_incubator/compound.py, with
voice_incubator/languages/fr/compound.py): where a sentence splits -- not at
"et" within an amount -- what both say as one sentence, and, typed, what each
clause runs. Each table is a native speaker's to add rows to."""

from __future__ import annotations

from pathlib import Path

import pytest

from voice_incubator import compound as shared
from voice_incubator import languages
from voice_incubator.languages.fr import compound

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def french():
    languages.use("fr")
    yield
    languages.use(languages.DEFAULT)


def test_the_joining_words():
    assert shared.joiners() == ("et ensuite", "et puis", "ensuite", "puis", "et")


SPLITS = [
    # (sentence, where it splits)
    ("verrouille la porte et puis éteins la lumière", [(3, 5)]),
    ("éteins la lumière puis verrouille la porte", [(3, 4)]),
    ("éteins la lumière ensuite ferme les volets", [(3, 4)]),
    ("et éteins la lumière et", []),  # nothing on one side
    # "Et" within an amount joins no commands.
    ("mets un minuteur d'une heure et demie", []),
    ("mets un minuteur de vingt et une minutes", []),
    ("mets un minuteur d'une heure et trente secondes", []),
    ("soixante et onze", []),
    ("mets un minuteur d'une heure et une minute", []),
    ("mets un minuteur de cinq minutes et un minuteur de dix minutes", [(6, 7)]),
    ("règle le volume à 20 et éteins la lumière", [(5, 6)]),
]


@pytest.mark.parametrize(("sentence", "splits"), SPLITS)
def test_where_a_sentence_may_split(sentence, splits):
    assert shared.splits(sentence.split()) == splits


BOTH = [
    ("J'ai éteint la lumière.", "J'ai éteint la télé.", "J'ai éteint la lumière et la télé."),
    ("J'ai allumé la lumière.", "J'ai éteint la télé.", "J'ai allumé la lumière et j'ai éteint la télé."),
    ("J'ai éteint Lampe de bureau.", "J'ai éteint Lampadaire.", "J'ai éteint Lampe de bureau et Lampadaire."),
    ("Lumière allumée dans le salon.", "Lumière éteinte dans la cuisine.",
     "Lumière allumée dans le salon et lumière éteinte dans la cuisine."),
    ("Thermostat réglé à 21 degrés.", "TV : éteint.", "Thermostat réglé à 21 degrés et TV : éteint."),
    ("Couleur changée.", "Couleur changée.", "Couleur changée."),
]


@pytest.mark.parametrize(("first", "second", "said"), BOTH)
def test_what_both_say_is_one_sentence(first, second, said):
    assert compound.both(first, second) == said


def test_said_on_its_own():
    assert compound.alone("annuler tous les minuteurs") == "Demandez-moi d'annuler tous les minuteurs séparément."
    assert compound.alone("verrouiller toutes les portes") == "Demandez-moi de verrouiller toutes les portes séparément."


def test_what_the_first_named_said_again():
    assert compound.devices(["Télé", "Lampadaire"]) == "Télé et Lampadaire"
    assert shared.target({"area": ["cuisine"]}, {"areas": {"cuisine": "Cuisine"}}, {}) == "dans la Cuisine"


@pytest.fixture(name="engine", scope="module")
def fixture_engine():
    """French's library (but the timers) in a home with a TV, two lamps, a
    front door and a scene, and a satellite in its Bureau."""
    from voice_incubator.engine import Engine, Satellite  # pylint: disable=import-outside-toplevel
    from voice_incubator.library import load_library  # pylint: disable=import-outside-toplevel
    from voice_incubator.store import compile_store  # pylint: disable=import-outside-toplevel

    pack = languages.use("fr")
    try:
        if pack.missing(ROOT):
            pytest.skip("no French models")
        entries = [e for e in load_library() if e["file"] != "timers"]
        store = {
            "language": "fr",
            "names": {
                "entities": {
                    "media_player.tele": {"name": "Télé"}, "light.lampe_chevet": {"name": "Lampe de chevet"},
                    "light.lampadaire": {"name": "Lampadaire"}, "lock.porte_entree": {"name": "Porte d'entrée"},
                    "scene.cinema": {"name": "Soirée cinéma"},
                },
                "areas": {"cuisine": {"name": "Cuisine"}, "chambre": {"name": "Chambre"}, "bureau": {"name": "Bureau"}},
            },
            "lists": {name: values for e in entries for name, values in e["lists"].items()},
            "commands": {e["id"]: e["spec"] for e in entries},
        }
        engine = Engine(pack.ctc_dir(ROOT), pack.transducer_dir(ROOT), None, threads=2)
        engine.build(compile_store(store))
        yield engine, Satellite("s", "Bureau", "bureau", "Bureau")
    finally:
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
    ("allume la lumière et éteins la télé", [("turn_on_here", None), ("turn_off_device", ["media_player.tele"])]),
    ("verrouille la porte d'entrée et puis éteins la lumière", [("lock", ["lock.porte_entree"]), ("turn_off_here", None)]),
    # One command, two targets: the second borrows the first's verb.
    ("éteins la lampe de chevet et le lampadaire", [("turn_off_device", ["light.lampe_chevet"]),
                                                   ("turn_off_device", ["light.lampadaire"])]),
    ("allume la lumière dans la cuisine et dans la chambre", [("turn_on_place", ["cuisine"]), ("turn_on_place", ["chambre"])]),
    # A second that names nothing acts on what the first named.
    ("allume la lumière dans la cuisine puis ferme les volets", [("turn_on_place", ["cuisine"]), ("close_covers_place", ["cuisine"])]),
    ("allume la lumière dans la cuisine et règle la luminosité à cinquante pour cent",
     [("turn_on_place", ["cuisine"]), ("set_brightness_place", ["cuisine"])]),
    ("allume le lampadaire et règle la luminosité à trente pour cent",
     [("turn_on_device", ["light.lampadaire"]), ("set_brightness_device", ["light.lampadaire"])]),
    # One target, two commands: "le" is what the first named.
    ("allume le lampadaire et mets-le en bleu", [("turn_on_device", ["light.lampadaire"]), ("light_color_device", ["light.lampadaire"])]),
    # One command, whole: "et" is part of it -- a list's items, an amount.
    ("ajoute des pommes et des bananes à la liste de courses", [("shopping_list_add", None)]),
]


@pytest.mark.parametrize(("text", "commands"), ROUTES)
def test_typed(engine, text, commands):
    engine, office = engine
    languages.use("fr")
    assert heard(engine.recognize_text(text, office)) == commands
