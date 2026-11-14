"""Two commands said together, in Ukrainian (voice_incubator/compound.py): the
words that join them, and how what both say is said as one sentence
(voice_incubator/languages/en/compound.py for what each is).

"І", "й" and "та" join two commands as "and" does ("увімкни світло і вимкни
телевізор"), "потім" and "а потім" one after the other. "І" also joins the
parts of one amount ("година і десять хвилин", "сто і п'ять"): that joins
no commands. Ukrainian has no articles; a possessive stands where one would
("вимкни мою лампу і мій телевізор")."""

from __future__ import annotations

from .numerals import NUMBER_WORDS

JOINERS = ("а потім", "і потім", "та потім", "і", "й", "та", "потім")
"""Where one command ends and the next begins; the longest first."""

ARTICLES = {"мій", "моя", "моє", "мою", "мої", "твій", "твоя", "твоє", "твою", "твої", "наш", "наша", "наше", "нашу"}
"""No articles in Ukrainian: the possessives that stand where they would."""

UNITS = {
    "секунда", "секунди", "секунд", "секунду", "хвилина", "хвилини", "хвилин", "хвилину", "година", "години",
    "годин", "годину", "півгодини", "відсоток", "відсотки", "відсотків", "відсотка", "градус", "градуси", "градусів",
    "градуса",
}
NUMBERS = {*NUMBER_WORDS, "пів", "півтори", "півтора", "половина", "половиною", "чверть"}


def both(first: str, second: str) -> str:
    """Two sentences as one: "Увімкнено: Торшер." and "Увімкнено: Нічник."
    are "Увімкнено: Торшер і Нічник."; "Світло увімкнено." and "Вимкнено:
    Телевізор." are "Світло увімкнено і вимкнено: Телевізор."."""
    a, b = first.strip(), second.strip()
    if a == b:
        return a
    if _sentences(a) != 1 or _sentences(b) != 1:
        return f"{a} {b}"
    end = b[-1] if b[-1] in ".!?" else "."
    a, b = a.rstrip(".!?"), b.rstrip(".!?")
    aw, bw = a.split(), b.split()
    common = 0
    while common < min(len(aw), len(bw)) - 1 and aw[common].lower() == bw[common].lower():
        common += 1
    # What the verb acts on keeps its possessive: "... мою лампу і мій телевізор".
    while common and aw[common - 1].lower() in ARTICLES:
        common -= 1
    # Only the whole of what both start with said once, before what each
    # names: "Увімкнено: Торшер і Нічник" -- after a colon, or a possessive.
    if common and (aw[common - 1].endswith(":") or bw[common].lower() in ARTICLES):
        return f"{a} і {' '.join(bw[common:])}{end}"
    return f"{a} і {_lowered(bw)}{end}"


def within_an_amount(before: list[str], after: list[str]) -> bool:
    """Whether "і" joins the parts of one amount, not two commands: "година і
    десять хвилин", "дві години і тридцять секунд", "сто і п'ять", "година і
    пів"."""
    if not before or not after or not (before[-1] in UNITS or _number(before[-1])):
        return False
    return _number(after[0])


def devices(names: list[str]) -> str:
    """The devices a command named, said again after a command that named
    nothing, for it to act on them too: "Телевізор і Торшер" (a name is
    heard in any case)."""
    return " і ".join(names)


def _number(word: str) -> bool:
    return word.isdigit() or word in NUMBERS


def alone(description: str) -> str:
    """A command that asks first, said with another: neither is done."""
    return f"Попроси мене {description} окремо."


def _sentences(text: str) -> int:
    return sum(1 for i, c in enumerate(text) if c in ".!?" and (i == len(text) - 1 or text[i + 1] == " "))


def _lowered(words: list[str]) -> str:
    """A sentence carried on after "і": its first word lowercase, unless it
    is a name ("TV", "Настільна лампа") -- not the word before a colon that
    names one ("вимкнено: Телевізор")."""
    first = words[0]
    name = first[1:] != first[1:].lower() or (len(words) > 1 and words[1][:1].isupper() and not first.endswith(":"))
    return " ".join([first if name else first[0].lower() + first[1:], *words[1:]])
