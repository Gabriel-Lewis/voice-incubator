"""Two commands said together (voice_incubator/compound.py), in Italian, with
English's names (voice_incubator/languages/en/compound.py): the words that
join them, and how what both say is said as one sentence.

"E" also joins the parts of an amount or a time -- "un'ora e mezza", "due
minuti e trenta secondi", "le sette e un quarto" -- where it joins no
commands (``within_an_amount``)."""

from __future__ import annotations

JOINERS = ("e poi", "e dopo", "e", "ed", "poi")
"""Where one command ends and the next begins; the longest first."""

ARTICLES = {"il", "lo", "la", "l'", "i", "gli", "le", "un", "uno", "una", "un'"}

UNITS = {
    "secondo", "secondi", "minuto", "minuti", "ora", "ore", "percento", "cento", "grado", "gradi", "quarto",
    "quarti", "mezzo", "mezza",
}
NUMBERS = {
    "zero", "uno", "una", "un", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove", "dieci", "undici",
    "dodici", "tredici", "quattordici", "quindici", "sedici", "diciassette", "diciotto", "diciannove", "venti",
    "trenta", "quaranta", "cinquanta", "sessanta", "settanta", "ottanta", "novanta", "cento", "mille", "mezzo",
    "mezza", "quarto", "quarti",
}

_PARTS = ("mezzo", "mezza", "quarto", "quarti")
"""What follows "e" in an amount without a number of its own: "e mezzo", "e
un quarto", "e tre quarti"."""


def both(first: str, second: str) -> str:
    """Two sentences as one: "Ho spento la luce." and "Ho spento la TV." are
    "Ho spento la luce e la TV."; "Ho acceso la luce." and "Ho spento la
    TV." are "Ho acceso la luce e ho spento la TV."."""
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
    # What the verb acts on keeps its article: "... la luce e la TV".
    while common and _article(aw[common - 1]):
        common -= 1
    # Only the whole verb said once: what is left starts with what it acts
    # on (an article, a name) -- "ho acceso ... e spento la TV" isn't said.
    if common and (_article(bw[common]) or bw[common][:1].isupper()):
        return f"{a} e {' '.join(bw[common:])}{end}"
    return f"{a} e {_lowered(bw)}{end}"


def _article(word: str) -> bool:
    """An article, alone ("la") or joined to its noun ("l'ingresso")."""
    lowered = word.lower()
    return lowered in ARTICLES or lowered.startswith(("l'", "un'"))


def within_an_amount(before: list[str], after: list[str]) -> bool:
    """Whether "e" joins the parts of one amount, not two commands: "un'ora
    e mezza", "1 ora e 30 secondi", "le sette e un quarto", "due e mezzo"."""
    if not before or not after or not (_unit(before[-1]) or _number(before[-1])):
        return False
    first = after[0]
    if first in ("un", "una", "uno"):  # "e un quarto", "e un minuto"; not "e un timer"
        return len(after) > 1 and (_unit(after[1]) or after[1] in _PARTS)
    return _number(first) or first in _PARTS


def _unit(word: str) -> bool:
    """A unit, alone or after an elided article ("un'ora", "mezz'ora")."""
    return word in UNITS or word.split("'")[-1] in UNITS


def devices(names: list[str]) -> str:
    """The devices a command named, said again after a command that named
    nothing, for it to act on them too: "la TV e la Piantana" (the article
    a guess at the name's gender; articles are fillers to the matcher)."""
    from .speech import join  # pylint: disable=import-outside-toplevel

    return join([f"{_the(name)}{name}" for name in names])


def _the(name: str) -> str:
    """"la " before a name that ends in -a (or is the TV), "l'" before a
    vowel, "lo " before s and a consonant or z, else "il "."""
    first = name.split()[0].lower() if name.split() else ""
    if first[:1] in "aeiouàèéìòùh" and first:
        return "l'"
    if first.endswith("a") or first in ("tv", "tivù", "radio"):
        return "la "
    if first.startswith(("z", "gn", "ps", "x", "y")) or (first[:1] == "s" and first[1:2] not in "aeiouàèéìòù"):
        return "lo "
    return "il "


def _number(word: str) -> bool:
    if word.isdigit() or word in NUMBERS:
        return True
    from .skills.numbers import parse_num  # pylint: disable=import-outside-toplevel

    return word.isalpha() and parse_num(word) is not None


def alone(description: str) -> str:
    """A command that asks first, said with another: neither is done."""
    return f"Chiedimi di {description} in una richiesta a parte."


def _sentences(text: str) -> int:
    return sum(1 for i, c in enumerate(text) if c in ".!?" and (i == len(text) - 1 or text[i + 1] == " "))


def _lowered(words: list[str]) -> str:
    """A sentence carried on after "e": its first word lowercase, unless it is
    a name ("TV", "Lampada piccola")."""
    first = words[0]
    name = first[1:] != first[1:].lower() or (len(words) > 1 and words[1][:1].isupper())
    return " ".join([first if name else first[0].lower() + first[1:], *words[1:]])
