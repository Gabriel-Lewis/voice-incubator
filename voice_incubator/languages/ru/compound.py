"""Two commands said together (voice_incubator/compound.py), in Russian, with
English's names (voice_incubator/languages/en/compound.py): the words that
join them ("и", "а потом", "потом", "и затем"), and how what both say is said
as one sentence.

"И" also joins the parts of an amount ("час и десять минут") and things said
together ("добавь яблоки и бананы"), which a command explains whole. Russian
has no articles: what stays with what a verb acts on is a possessive or the
preposition of a place ("Свет выключен на кухне и в спальне")."""

from __future__ import annotations

JOINERS = ("а потом", "и потом", "а затем", "и затем", "потом", "затем", "и")
"""Where one command ends and the next begins; the longest first."""

ARTICLES = {"в", "во", "на", "мой", "моя", "мое", "мои", "мою", "ваш", "ваша", "ваше", "ваши", "вашу"}
"""What stays with the words after it when two sentences share their
start: a place's preposition, a possessive."""

UNITS = {
    "секунда", "секунды", "секунду", "секунд", "минута", "минуты", "минуту", "минут", "час", "часа", "часов",
    "процент", "процента", "процентов", "градус", "градуса", "градусов",
}
NUMBERS = {
    "ноль", "один", "одна", "одну", "одно", "два", "две", "три", "четыре", "пять", "шесть", "семь", "восемь",
    "девять", "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать", "шестнадцать",
    "семнадцать", "восемнадцать", "девятнадцать", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят",
    "семьдесят", "восемьдесят", "девяносто", "сто", "двести", "триста", "четыреста", "пятьсот", "тысяча",
    "тысячи", "полчаса", "полтора", "полторы", "половина", "половиной", "четверть",
}


def both(first: str, second: str) -> str:
    """Two sentences as one: "Свет выключен на кухне." and "Свет выключен в
    спальне." are "Свет выключен на кухне и в спальне."; "Включено: Торшер."
    and "Включено: Телевизор." are "Включено: Торшер и Телевизор."; "Свет
    включён." and "Громкость 50 процентов." are "Свет включён и громкость 50
    процентов."."""
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
    # What the verb acts on keeps its preposition: "... на кухне и в спальне".
    while common and aw[common - 1].lower() in ARTICLES:
        common -= 1
    # Only the whole start said once: what is left starts with what it acts
    # on (a place's preposition, a name).
    if common and (bw[common].lower() in ARTICLES or bw[common][:1].isupper()):
        return f"{a} и {' '.join(bw[common:])}{end}"
    if ":" in a or ":" in b:
        return f"{a}. {b}{end}"  # "Включено: Торшер. Яркость на кухне: 50 процентов."
    return f"{a} и {_lowered(bw)}{end}"


def within_an_amount(before: list[str], after: list[str]) -> bool:
    """Whether "и" joins the parts of one amount, not two commands: "час и
    десять минут", "5 минут и 30 секунд", "полтора часа и пять минут"."""
    if not before or not after or not (before[-1] in UNITS or _number(before[-1])):
        return False
    return _number(after[0]) or after[0] in UNITS


def devices(names: list[str]) -> str:
    """The devices a command named, said again after a command that named
    nothing, for it to act on them too: "Торшер и Ночник" (a name is heard
    in any case, and Russian has no article to say it with)."""
    return " и ".join(names)


def _number(word: str) -> bool:
    return word.isdigit() or word in NUMBERS


def alone(description: str) -> str:
    """A command that asks first, said with another: neither is done."""
    return f"Попросите меня {description} отдельно."


def _sentences(text: str) -> int:
    return sum(1 for i, c in enumerate(text) if c in ".!?" and (i == len(text) - 1 or text[i + 1] == " "))


def _lowered(words: list[str]) -> str:
    """A sentence carried on after "и": its first word lowercase, unless
    it is a name ("Торшер", "Настольная лампа")."""
    first = words[0]
    name = first[1:] != first[1:].lower() or (len(words) > 1 and words[1][:1].isupper())
    return " ".join([first if name else first[0].lower() + first[1:], *words[1:]])
