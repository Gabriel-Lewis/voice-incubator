"""Two commands said together, in Spanish, with English's names (see
voice_incubator/languages/en/compound.py and voice_incubator/compound.py): the
words that join them, and how what both say is said as one sentence.

"Y" also joins the parts of a number and of an amount -- "treinta y cinco",
"una hora y media", "las siete y cuarto", "cinco minutos y treinta
segundos" -- which join no commands."""

from __future__ import annotations

from .speech import _and, _gender, join

JOINERS = ("y luego", "y después", "y", "e", "luego", "después")
"""Where one command ends and the next begins; the longest first. "E" is "y"
before an "i" sound: "apaga la tele e ilumina el pasillo"."""

ARTICLES = {"el", "la", "los", "las", "un", "una", "mi", "mis", "tu", "tus", "en", "a", "al", "de", "del"}
"""What what a verb acts on starts with, kept when the verb is said once
(prepositions too: "... en la cocina y en el salón")."""

UNITS = {"segundo", "segundos", "minuto", "minutos", "hora", "horas", "ciento", "grado", "grados"}
NUMBERS = {
    "cero", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce", "trece",
    "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno", "veintiún",
    "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete", "veintiocho",
    "veintinueve", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa", "cien", "ciento",
    "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos", "setecientos", "ochocientos",
    "novecientos", "mil", "media", "medio", "cuarto", "cuartos",
}
"""Numbers said in words, and the parts of one; not "un" and "una", which
are as often an article ("un temporizador de una hora y una alarma")."""

_ONE = ("un", "una", "uno")


def both(first: str, second: str) -> str:
    """Two sentences as one: "He apagado las luces." and "He apagado la
    tele." are "He apagado las luces y la tele."; "He encendido las luces." and
    "He apagado la tele." are "He encendido las luces y he apagado la tele."."""
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
    # What the verb acts on keeps its article (and its preposition): "... las
    # luces y la tele", "... en la cocina y en el salón".
    while common and aw[common - 1].lower() in ARTICLES:
        common -= 1
    # Nor half a name: "Lámpara de pie" and "Lámpara pequeña" share a word.
    while common > 1 and aw[common - 1][:1].isupper() and not bw[common][:1].isupper():
        common -= 1
    # Only the whole verb said once: what is left starts with what it acts
    # on (an article, a name).
    if common and (bw[common].lower() in ARTICLES or bw[common][:1].isupper()):
        rest = " ".join(bw[common:])
        return f"{a} {_and(rest)} {rest}{end}"
    rest = _lowered(bw)
    return f"{a} {_and(rest)} {rest}{end}"


def within_an_amount(before: list[str], after: list[str]) -> bool:
    """Whether "y" joins the parts of one amount, not two commands: "una hora
    y media", "1 hora y 30 segundos", "treinta y cinco", "las siete y
    cuarto"."""
    if not before or not after or not (before[-1] in UNITS or before[-1] in _ONE or _number(before[-1])):
        return False
    first = after[0]
    return _number(first) or (first in _ONE and len(after) > 1 and (after[1] in UNITS or after[1] in ("media", "cuarto")))


def devices(names: list[str]) -> str:
    """The devices a command named, said again after a command that named
    nothing, for it to act on them too: "la Lámpara de pie y el Ventilador"."""
    articles = {("m", False): "el", ("f", False): "la", ("m", True): "los", ("f", True): "las"}
    return join([f"{articles[_gender(name.split())]} {name}" for name in names])


def _number(word: str) -> bool:
    return word.isdigit() or word in NUMBERS


def alone(description: str) -> str:
    """A command that asks first, said with another: neither is done."""
    return f"Para {description}, pídemelo por separado."


def _sentences(text: str) -> int:
    return sum(1 for i, c in enumerate(text) if c in ".!?" and (i == len(text) - 1 or text[i + 1] == " "))


def _lowered(words: list[str]) -> str:
    """A sentence carried on after "y": its first word lowercase, unless it
    is a name ("Lámpara de pie")."""
    first = words[0]
    name = first[1:] != first[1:].lower() or (len(words) > 1 and words[1][:1].isupper())
    return " ".join([first if name else first[0].lower() + first[1:], *words[1:]])
