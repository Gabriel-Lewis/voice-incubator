"""Two commands said together (voice_incubator/compound.py), in Dutch, with
English's names (see voice_incubator/languages/en/compound.py): the words that
join them, and how what both say is said as one sentence.

Dutch confirmations often end in their verb ("Staande lamp uitgezet.", "Licht
in de keuken aan."), so what both end with is said once at the end: "Staande
lamp en kleine lamp uitgezet."; what both start with ("Ik open de ...") once
at the start, as English does."""

from __future__ import annotations

import re

JOINERS = ("en daarna", "en dan", "en", "daarna", "dan")
"""Where one command ends and the next begins; the longest first."""

ARTICLES = {"de", "het", "een", "mijn", "m'n", "je", "jouw"}

UNITS = {"seconde", "seconden", "minuut", "minuten", "kwartier", "uur", "uren", "procent", "graad", "graden"}
NUMBERS = {
    "nul", "één", "twee", "drie", "vier", "vijf", "zes", "zeven", "acht", "negen", "tien", "elf", "twaalf", "dertien",
    "veertien", "vijftien", "zestien", "zeventien", "achttien", "negentien", "twintig", "dertig", "veertig", "vijftig",
    "zestig", "zeventig", "tachtig", "negentig", "honderd", "duizend", "half", "halve", "anderhalf", "anderhalve",
    "kwart", "driekwart",
}
"""Number words. Not "een": "vijf minuten en een timer van tien" is two
timers; it is a number before a unit ("een uur en een kwartier")."""

_COMPOUND = re.compile(r"(?:een|twee|drie|vier|vijf|zes|zeven|acht|negen)(?:en|ën)(?:twintig|dertig|veertig|vijftig|zestig"
                       r"|zeventig|tachtig|negentig)")
_PREPOSITIONS = {"in", "op", "naar", "bij", "aan", "van", "met", "voor"}


def both(first: str, second: str) -> str:
    """Two sentences as one: "Staande lamp uitgezet." and "Kleine lamp
    uitgezet." are "Staande lamp en kleine lamp uitgezet."; "Licht in de
    keuken aan." and "Licht in de woonkamer aan." are "Licht in de keuken en de
    woonkamer aan."; "Tv aangezet." and "Volume op 50 procent gezet." are "Tv
    aangezet en volume op 50 procent gezet."."""
    a, b = first.strip(), second.strip()
    if a == b:
        return a
    if _sentences(a) != 1 or _sentences(b) != 1:
        return f"{a} {b}"
    end = b[-1] if b[-1] in ".!?" else "."
    a, b = a.rstrip(".!?"), b.rstrip(".!?")
    aw, bw = a.split(), b.split()
    # What both end with -- the verb -- said once, at the end.
    tail = 0
    while tail < min(len(aw), len(bw)) - 1 and aw[-1 - tail].lower() == bw[-1 - tail].lower():
        tail += 1
    if tail:
        a_rest, b_rest, ending = aw[:-tail], bw[:-tail], " " + " ".join(aw[-tail:])
    else:
        a_rest, b_rest, ending = aw, bw, ""
    common = 0
    while common < min(len(a_rest), len(b_rest)) - 1 and a_rest[common].lower() == b_rest[common].lower():
        common += 1
    # What the verb acts on keeps its article: "... de rolluiken en de gordijnen".
    while common and a_rest[common - 1].lower() in ARTICLES:
        common -= 1
    # What both start with said once: what is left starts with what it acts
    # on (an article, a name) or where (a place).
    if common and (b_rest[common].lower() in ARTICLES | _PREPOSITIONS or b_rest[common][:1].isupper()):
        return f"{' '.join(a_rest)} en {' '.join(b_rest[common:])}{ending}{end}"
    return f"{' '.join(a_rest)} en {_lowered(b_rest)}{ending}{end}"


def within_an_amount(before: list[str], after: list[str]) -> bool:
    """Whether "en" joins the parts of one amount, not two commands: "een uur
    en tien minuten", "twee en een half uur", "een uur en een kwartier",
    "honderd en vijftig"."""
    if not before or not after or not (before[-1] in UNITS or _number(before[-1])):
        return False
    first = after[0]
    return _number(first) or (first in ("een", "één") and len(after) > 1 and (
        after[1] in UNITS or after[1] in ("half", "halve", "kwart")))


_HET = ("licht", "raam", "gordijn", "scherm", "hek", "slot", "kantoor", "je")
"""Names that are het-words, by their last part: "het dakraam"."""


def devices(names: list[str]) -> str:
    """The devices a command named, said again after a command that named
    nothing, for it to act on them too: "de tv en het dakraam"."""
    return " en ".join(f"{'het' if name.lower().endswith(_HET) else 'de'} {name}" for name in names)


def _number(word: str) -> bool:
    return word.isdigit() or word in NUMBERS or bool(_COMPOUND.fullmatch(word))


def alone(description: str) -> str:
    """A command that asks first, said with another: neither is done."""
    return f"Vraag me dat apart: {description}."


def _sentences(text: str) -> int:
    return sum(1 for i, c in enumerate(text) if c in ".!?" and (i == len(text) - 1 or text[i + 1] == " "))


def _lowered(words: list[str]) -> str:
    """A sentence carried on after "en": its first word lowercase, unless it
    is a name ("TV", "Staande Lamp")."""
    first = words[0]
    name = first[1:] != first[1:].lower() or (len(words) > 1 and words[1][:1].isupper())
    return " ".join([first if name else first[0].lower() + first[1:], *words[1:]])
