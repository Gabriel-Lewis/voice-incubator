"""Two commands said together in Russian (voice_incubator/compound.py, with
voice_incubator/languages/ru/compound.py): where a sentence may split, "и"
within an amount, what both say as one sentence -- and, typed, sentences
heard as two commands with the Russian library in the bench's home. Each
case is a row: a native speaker adds one by adding a row."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from voice_incubator import compound, languages
from voice_incubator.languages.ru import compound as russian

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def in_russian():
    languages.use("ru")
    yield
    languages.use(languages.DEFAULT)


def test_the_joining_words():
    assert compound.joiners()[0] in ("а потом", "и потом") and compound.joiners()[-1] == "и"
    assert {"и", "потом"} <= compound.joining_words()


@pytest.mark.parametrize(
    ("said", "splits"),
    [
        ("выключи свет и включи телевизор", [(2, 3)]),
        ("выключи свет а потом включи телевизор", [(2, 4)]),
        ("выключи свет потом запри дверь", [(2, 3)]),
        ("выключи свет и потом запри дверь", [(2, 4)]),
        ("и выключи свет и", []),  # nothing on one side
        # "И" within an amount joins no commands.
        ("поставь таймер на час и десять минут", []),
        ("поставь таймер на 5 минут и 30 секунд", []),
        ("поставь таймер на пять минут и таймер на десять минут", [(5, 6)]),
    ],
)
def test_where_a_sentence_may_split(said, splits):
    assert compound.splits(said.split()) == splits


@pytest.mark.parametrize(
    ("before", "after", "within"),
    [
        ("поставь таймер на час", "десять минут", True),
        ("на 5 минут", "30 секунд", True),
        ("полтора часа", "пять минут", True),
        ("на пять минут", "таймер на десять минут", False),
        ("выключи свет", "включи телевизор", False),
    ],
)
def test_and_within_an_amount(before, after, within):
    assert russian.within_an_amount(before.split(), after.split()) == within


@pytest.mark.parametrize(
    ("first", "second", "said"),
    [
        ("Свет выключен на кухне.", "Свет выключен в спальне.", "Свет выключен на кухне и в спальне."),
        ("Свет выключен на кухне.", "Свет выключен на втором этаже.", "Свет выключен на кухне и на втором этаже."),
        ("Включено: Торшер.", "Включено: Телевизор.", "Включено: Торшер и Телевизор."),
        ("Свет включён.", "Громкость изменена.", "Свет включён и громкость изменена."),
        ("Запираю: Входная дверь.", "Свет выключен.", "Запираю: Входная дверь. Свет выключен."),
        ("Свет включён.", "Свет включён.", "Свет включён."),
    ],
)
def test_what_both_say_is_one_sentence(first, second, said):
    assert russian.both(first, second) == said


@pytest.mark.parametrize(
    ("slots", "said"),
    [
        # Devices by their names, joined; an area or floor as the language's place says it.
        ({"entity": ["light.torsher"]}, "Торшер"),
        ({"entity": ["light.torsher", "light.nochnik"]}, "Торшер и Ночник"),
        ({"area": ["kuhnya"]}, "на кухне"),
        ({"area": ["kuhnya", "gostinaya"]}, "на кухне и в гостиной"),
        ({"floor": ["vtoroy_etazh"]}, "на втором этаже"),
        ({}, None),
    ],
)
def test_what_a_command_named_said_again(slots, said):
    names = {"entities": {"light.torsher": {"name": "Торшер"}, "light.nochnik": "Ночник"},
             "areas": {"kuhnya": "Кухня", "gostinaya": "Гостиная"}, "floors": {"vtoroy_etazh": "Второй этаж"}}
    assert compound.target(slots, names, {}) == said
    assert russian.devices(["Торшер", "Ночник"]) == "Торшер и Ночник"


def test_what_both_say():
    assert compound.both(None, None) is None  # both silent
    assert compound.both("", "") == ""  # the acknowledgement sound, once
    assert compound.both("Свет включён.", "") == "Свет включён."
    assert compound.alone("отменить все таймеры") == "Попросите меня отменить все таймеры отдельно."


def _bench():
    spec = importlib.util.spec_from_file_location("bench_language", ROOT / "scripts/bench_language.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(name="heard", scope="module")
def fixture_heard():
    """The Russian library in the bench's home (voice_incubator/languages/ru/
    bench.yaml), typed: each sentence's command and slots, and its second's."""
    pack = languages.use("ru")
    try:
        if pack.missing(ROOT):
            pytest.skip("no Russian models")
        bench = _bench()
        data = bench.bench("ru")
        engine = bench.engine_for(data, threads=2)
        satellite = bench.satellite_for(data)
    finally:
        languages.use(languages.DEFAULT)

    def heard(text):
        languages.use("ru")
        decision = engine.recognize_text(text, satellite)
        if decision.command is None:
            return None
        then = decision.then
        return (decision.command.id, decision.slots,
                (then.command.id, then.slots) if then is not None and then.command is not None else None)

    return heard


@pytest.mark.parametrize(
    ("said", "first", "second"),
    [
        ("Выключи свет на кухне и включи свет в гостиной.",
         ("turn_off_place", {"area": ["kuhnya"]}), ("turn_on_place", {"area": ["gostinaya"]})),
        # The second borrows the first's verb.
        ("Выключи свет на кухне и в спальне.",
         ("turn_off_place", {"area": ["kuhnya"]}), ("turn_off_place", {"area": ["spalnya"]})),
        ("Включи ночник, а потом выключи маленькую лампу.",
         ("turn_on_device", {"entity": ["light.nochnik"]}), ("turn_off_device", {"entity": ["light.malenkaya_lampa"]})),
        ("Запри входную дверь и выключи свет на кухне.",
         ("lock", {"entity": ["lock.vhodnaya_dver"]}), ("turn_off_place", {"area": ["kuhnya"]})),
        # The second, naming nothing, acts on what the first named.
        ("Включи свет в гостиной и поставь яркость на пятьдесят процентов.",
         ("turn_on_place", {"area": ["gostinaya"]}), ("set_brightness_place", {"area": ["gostinaya"], "percentage": 50})),
        ("Включи маленькую лампу и поставь яркость на пятьдесят процентов.",
         ("turn_on_device", {"entity": ["light.malenkaya_lampa"]}),
         ("set_brightness_device", {"entity": ["light.malenkaya_lampa"], "percentage": 50})),
        ("Включи маленькую лампу и сделай ярче.",
         ("turn_on_device", {"entity": ["light.malenkaya_lampa"]}),
         ("brighter_device", {"entity": ["light.malenkaya_lampa"], "step": 30})),
    ],
)
def test_two_commands_said_together(heard, said, first, second):
    command, slots, then = heard(said)
    assert (command, slots) == first and then == second


@pytest.mark.parametrize(
    ("said", "command"),
    [
        # One command, whole: "и" inside what is added, and within an amount.
        ("Добавь яблоки и бананы в список покупок.", "shopping_list_add"),
        ("Поставь таймер на пять минут.", "start_timer"),
    ],
)
def test_one_command_is_one(heard, said, command):
    found = heard(said)
    assert found is not None and found[0] == command and found[2] is None
