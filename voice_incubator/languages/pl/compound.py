"""Two commands said together, in Polish (voice_incubator/compound.py): the
words that join them, and how what both say is said as one sentence, with
English's names (see voice_incubator/languages/en/compound.py).

Polish has no articles: what a verb acts on is said without one ("wyłącz
światło i telewizor"), and the app's replies start with a verb that is
neither a man's nor a woman's ("Wyłączono", "Otwieram"), said once for
both: "Wyłączono światło w kuchni i w sypialni". "I" also joins the parts
of an amount ("godzina i dziesięć minut", "dwa i pół"), which is no two
commands."""

from __future__ import annotations

import re

from .skills.numbers import fold, parse_num

JOINERS = ("a potem", "i potem", "i", "potem")
"""Where one command ends and the next begins; the longest first."""

ARTICLES = {"mój", "moja", "moje", "moją", "mojej", "mojego", "moim", "moich", "twój", "twoja", "twoje", "twoją", "twojej"}
"""What stands where an article would (Polish has none): a possessive,
kept with what it belongs to ("... i moją lampę")."""

PREPOSITIONS = {"w", "we", "na", "do", "z", "ze", "o", "u", "przy"}
"""What a place is said with: kept with it ("... w kuchni i w sypialni")."""

UNITS = {
    "sekunda", "sekundy", "sekund", "sekundę", "minuta", "minuty", "minut", "minutę", "godzina", "godziny", "godzin",
    "godzinę", "kwadrans", "kwadranse", "procent", "procenta", "stopień", "stopnie", "stopni", "stopnia",
}
NUMBERS = {
    "zero", "jeden", "jedna", "jedną", "jedno", "dwa", "dwie", "trzy", "cztery", "pięć", "sześć", "siedem", "osiem",
    "dziewięć", "dziesięć", "jedenaście", "dwanaście", "trzynaście", "czternaście", "piętnaście", "szesnaście",
    "siedemnaście", "osiemnaście", "dziewiętnaście", "dwadzieścia", "trzydzieści", "czterdzieści", "pięćdziesiąt",
    "sześćdziesiąt", "siedemdziesiąt", "osiemdziesiąt", "dziewięćdziesiąt", "sto", "tysiąc", "pół", "półtorej",
    "półtora", "ćwierć", "kwadrans",
}
_FOLDED_UNITS = {fold(word) for word in UNITS}
_FOLDED_NUMBERS = {fold(word) for word in NUMBERS}

_VERB = re.compile(r"(?:ono|ano|ęto|yto|uto|am|em|ę|uję)$")
"""How the app's own sentences start: a verb that is neither a man's nor a
woman's ("Wyłączono", "Ustawiono") or its own ("Otwieram", "Blokuję")."""
_WORDS = {"nie", "tak", "jest", "są", "gotowe", "teraz", "światło", "światła", "minutnik", "budzik", "termostat"}
"""Words the app's sentences start with that are no name."""


def both(first: str, second: str) -> str:
    """Two sentences as one: "Wyłączono światło." and "Wyłączono
    Telewizor." are "Wyłączono światło i Telewizor."; "Włączono światło."
    and "Wyłączono Telewizor." are "Włączono światło i wyłączono
    Telewizor."; "Wyłączono światło w kuchni." and "Wyłączono światło w
    sypialni." are "Wyłączono światło w kuchni i w sypialni."."""
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
    # A place keeps its preposition, and what is someone's its possessive:
    # "... w kuchni i w sypialni".
    while common and aw[common - 1].lower() in PREPOSITIONS | ARTICLES:
        common -= 1
    # Said once only when it is the app's verb: the same verb whatever it
    # acts on. A name the sentences start with ("Lampa stojąca włączona")
    # is said whole, each time.
    if common and _VERB.search(aw[0].lower()):
        return f"{a} i {' '.join(bw[common:])}{end}"
    return f"{a} i {_lowered(bw)}{end}"


def within_an_amount(before: list[str], after: list[str]) -> bool:
    """Whether "i" joins the parts of one amount, not two commands:
    "godzina i dziesięć minut", "jedna minuta i 30 sekund", "dwa i pół",
    "godzinę i kwadrans"."""
    if not before or not after or not (_unit(before[-1]) or _number(before[-1])):
        return False
    return _number(after[0])


def devices(names: list[str]) -> str:
    """The devices a command named, said again after a command that named
    nothing, for it to act on them too: "Telewizor i Lampa stojąca" (no
    article; a name is heard in any case)."""
    return " i ".join(names)


def _unit(word: str) -> bool:
    return fold(word.lower()) in _FOLDED_UNITS


def _number(word: str) -> bool:
    folded = fold(word.lower())
    return word.isdigit() or folded in _FOLDED_NUMBERS or parse_num(folded) is not None


def alone(description: str) -> str:
    """A command that asks first, said with another: neither is done."""
    return f"Żeby {description}, poproś mnie o to osobno."


def _sentences(text: str) -> int:
    return sum(1 for i, c in enumerate(text) if c in ".!?" and (i == len(text) - 1 or text[i + 1] == " "))


def _lowered(words: list[str]) -> str:
    """A sentence carried on after "i": its first word lowercase when it is
    the app's verb or word ("wyłączono", "nie"), not a name ("Lampa
    stojąca")."""
    first = words[0]
    lower = first.lower().rstrip(",")
    ours = (_VERB.search(lower) or lower in _WORDS) and first[1:] == first[1:].lower()
    return " ".join([first[0].lower() + first[1:] if ours else first, *words[1:]])
