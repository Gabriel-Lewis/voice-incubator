"""Two commands said together (voice_incubator/compound.py), in German, with
English's names (see voice_incubator/languages/en/compound.py): the words that
join them, and how what both say is said as one sentence.

German says what was done last ("Licht ausgeschaltet."), so two sentences
that end alike share their end: "Licht ausgeschaltet." and "Fernseher
ausgeschaltet." are "Licht und Fernseher ausgeschaltet."."""

from __future__ import annotations

JOINERS = ("und dann", "und danach", "und", "dann", "danach")
"""Where one command ends and the next begins; the longest first."""

ARTICLES = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer", "mein", "meine", "meinen",
    "dein", "deine", "deinen",
}

UNITS = {"sekunde", "sekunden", "minute", "minuten", "stunde", "stunden", "prozent", "grad"}
NUMBERS = {
    "null", "eins", "ein", "eine", "zwei", "zwo", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun", "zehn",
    "elf", "zwölf", "dreizehn", "vierzehn", "fünfzehn", "sechzehn", "siebzehn", "achtzehn", "neunzehn", "zwanzig",
    "dreißig", "dreissig", "vierzig", "fünfzig", "sechzig", "siebzig", "achtzig", "neunzig", "hundert", "tausend",
    "halb", "halbe", "halben", "viertel", "anderthalb", "eineinhalb",
}

_LOWER = {
    "ich", "es", "er", "sie", "wir", "du", "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "alle",
    "alles", "nichts", "kein", "keine", "ja", "nein", "gerade", "jetzt", "dort", "hier", "mein", "meine", "dein",
    "deine", "wird", "werden", "ist", "sind", "so", "da", "auf", "in", "im", "am", "um", "für", "zur", "zum", "noch",
}
"""Words a sentence may start with that aren't nouns: lowercase after "und"
(a noun keeps its capital: "und Fernseher ausgeschaltet")."""


def both(first: str, second: str) -> str:
    """Two sentences as one: "Licht ausgeschaltet." and "Fernseher
    ausgeschaltet." are "Licht und Fernseher ausgeschaltet."; "Ich spiele
    Jazz." and "Ich spiele Rock." are "Ich spiele Jazz und Rock."; "Licht
    eingeschaltet." and "Fernseher ausgeschaltet." are "Licht eingeschaltet
    und Fernseher ausgeschaltet."."""
    a, b = first.strip(), second.strip()
    if a == b:
        return a
    if _sentences(a) != 1 or _sentences(b) != 1:
        return f"{a} {b}"
    end = b[-1] if b[-1] in ".!?" else "."
    a, b = a.rstrip(".!?"), b.rstrip(".!?")
    aw, bw = a.split(), b.split()
    # The same end -- what was done -- said once.
    same = 0
    while same < min(len(aw), len(bw)) - 1 and aw[-1 - same].lower() == bw[-1 - same].lower():
        same += 1
    if same:
        return f"{' '.join(aw[:-same])} und {_lowered(bw[:-same])} {' '.join(aw[-same:])}{end}"
    # The same start, said once, when what is left starts with what it acts
    # on (an article, a name).
    common = 0
    while common < min(len(aw), len(bw)) - 1 and aw[common].lower() == bw[common].lower():
        common += 1
    while common and aw[common - 1].lower() in ARTICLES:
        common -= 1
    if common and (bw[common].lower() in ARTICLES or bw[common][:1].isupper()):
        return f"{a} und {' '.join(bw[common:])}{end}"
    return f"{a} und {_lowered(bw)}{end}"


def within_an_amount(before: list[str], after: list[str]) -> bool:
    """Whether "und" joins the parts of one amount, not two commands: "eine
    Stunde und dreißig Minuten", "fünf und zwanzig", "eine Stunde und eine
    halbe"."""
    if not before or not after or not (before[-1] in UNITS or _number(before[-1])):
        return False
    first = after[0]
    return _number(first) and first not in ("ein", "eine") or (
        first in ("ein", "eine", "einer") and len(after) > 1 and (after[1] in UNITS or after[1] in ("halbe", "halb", "viertel")))


def devices(names: list[str]) -> str:
    """The devices a command named, said again after a command that named
    nothing, for it to act on them too: "Fernseher und Stehlampe" (an article
    is filler, and would need each one's gender)."""
    return " und ".join(names)


def _number(word: str) -> bool:
    return word.isdigit() or word in NUMBERS or (word.endswith("zig") and "und" in word)


def alone(description: str) -> str:
    """A command that asks first, said with another: neither is done."""
    return f"Bitte sag mir einzeln, dass ich {description} soll."


def _sentences(text: str) -> int:
    return sum(1 for i, c in enumerate(text) if c in ".!?" and (i == len(text) - 1 or text[i + 1] == " "))


def _lowered(words: list[str]) -> str:
    """A sentence carried on after "und": its first word lowercase, unless it
    is a noun or a name ("Fernseher", "Kleine Lampe")."""
    first = words[0]
    return " ".join([first[0].lower() + first[1:] if first.lower() in _LOWER else first, *words[1:]])
