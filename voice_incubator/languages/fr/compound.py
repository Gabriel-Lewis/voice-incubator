"""Two commands said together (voice_incubator/compound.py), in French, with
English's names (voice_incubator/languages/en/compound.py): the words that
join them, and how what both say is said as one sentence.

"Et" also joins the parts of one amount -- "vingt et une minutes", "une heure
et demie", "soixante et onze" -- where it joins no commands."""

from __future__ import annotations

JOINERS = ("et ensuite", "et puis", "ensuite", "puis", "et")
"""Where one command ends and the next begins; the longest first."""

ARTICLES = {"le", "la", "les", "l'", "un", "une", "des", "mon", "ma", "mes", "ton", "ta", "tes", "votre", "vos"}

UNITS = {"seconde", "secondes", "minute", "minutes", "heure", "heures", "pourcent", "degré", "degrés"}
NUMBERS = {
    "zéro", "un", "une", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze",
    "treize", "quatorze", "quinze", "seize", "vingt", "trente", "quarante", "cinquante", "soixante", "septante",
    "huitante", "octante", "nonante", "cent", "cents", "mille", "demi", "demie", "quart", "quarts",
}

_TENS = {"vingt", "trente", "quarante", "cinquante", "soixante"}
"""Tens said with "et un" ("vingt et un") and, soixante, "et onze"."""


def both(first: str, second: str) -> str:
    """Two sentences as one: "J'ai éteint la lumière." and "J'ai éteint la
    télé." are "J'ai éteint la lumière et la télé."; "J'ai allumé la
    lumière." and "J'ai éteint la télé." are "J'ai allumé la lumière et j'ai
    éteint la télé."."""
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
    # What the verb acts on keeps its article: "... la lumière et la télé".
    while common and aw[common - 1].lower() in ARTICLES:
        common -= 1
    # Only the whole verb said once: what is left starts with what it acts
    # on (an article, a name) -- "j'ai allumé ... et éteint la télé" is said
    # whole.
    if common and (bw[common].lower() in ARTICLES or bw[common][:1].isupper()):
        return f"{a} et {' '.join(bw[common:])}{end}"
    return f"{a} et {_lowered(bw)}{end}"


def within_an_amount(before: list[str], after: list[str]) -> bool:
    """Whether "et" joins the parts of one amount, not two commands: "une
    heure et demie", "1 heure et 30 secondes", "vingt et une minutes",
    "soixante et onze" -- not "cinq minutes et un minuteur de dix"."""
    if not before or not after or not (before[-1] in UNITS or _number(before[-1])):
        return False
    first = after[0]
    if first in ("un", "une"):
        # An article as often as a number: one only after tens, or before a
        # unit ("une heure et une minute").
        return before[-1] in _TENS or (len(after) > 1 and (after[1] in UNITS or after[1] in ("demi", "demie", "quart")))
    return _number(first)


def devices(names: list[str]) -> str:
    """The devices a command named, said again after a command that named
    nothing, for it to act on them too: "Télé et Lampadaire" (an article
    before a name is filler, so none is guessed)."""
    return " et ".join(names)


def _number(word: str) -> bool:
    return word.isdigit() or word in NUMBERS


def alone(description: str) -> str:
    """A command that asks first, said with another: neither is done."""
    of = f"d'{description}" if description[:1].lower() in "aeiouyéèêàâîôh" else f"de {description}"
    return f"Demandez-moi {of} séparément."


def _sentences(text: str) -> int:
    return sum(1 for i, c in enumerate(text) if c in ".!?" and (i == len(text) - 1 or text[i + 1] == " "))


def _lowered(words: list[str]) -> str:
    """A sentence carried on after "et": its first word lowercase, unless
    it is a name ("TV", "Lampe de bureau")."""
    first = words[0]
    name = first[1:] != first[1:].lower() or (len(words) > 1 and words[1][:1].isupper())
    return " ".join([first if name else first[0].lower() + first[1:], *words[1:]])
