"""Turkish-aware lowercasing, accent folding and a light suffix stemmer for search."""

from __future__ import annotations

import re
import unicodedata

_FOLD = str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
                       "â": "a", "î": "i", "û": "u"})

# Folded (ASCII) inflectional suffixes: plural, case, possessive, copula.
# Derivational suffixes are left alone because they change the meaning.
_SUFFIXES = sorted({
    "lar", "ler", "lari", "leri", "larin", "lerin", "lara", "lere",
    "larda", "lerde", "lardan", "lerden",
    "da", "de", "ta", "te", "dan", "den", "tan", "ten",
    "nda", "nde", "ndan", "nden", "na", "ne", "ni", "nu", "nin", "nun",
    "ya", "ye", "yi", "yu", "yla", "yle", "la", "le",
    "in", "un", "im", "um", "imiz", "umuz", "iniz", "unuz",
    "si", "su", "sini", "sunu", "sinin", "sunun",
    "ki", "dir", "dur", "tir", "tur",
    "a", "e", "i", "u",
}, key=len, reverse=True)

# Final consonant softening: kitap -> kitabı, renk -> rengi, git -> gidiyor.
_SOFT = {"p": "b", "b": "p", "t": "d", "d": "t", "k": "g", "g": "k"}

STOPWORDS = frozenset(
    "ve veya ile bir bu su o da de mi icin gibi ama the a an and or of to in on for".split()
)


def lower(text: str) -> str:
    return text.replace("İ", "i").replace("I", "ı").lower()


def fold(text: str) -> str:
    text = lower(text).translate(_FOLD)
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", fold(text))


def stem(word: str) -> str:
    word = fold(word)
    for _ in range(2):
        for suffix in _SUFFIXES:
            rest = len(word) - len(suffix)
            if word.endswith(suffix) and rest >= (4 if len(suffix) == 1 else 3):
                word = word[:rest]
                break
        else:
            break
    return word


def _stems(term: str) -> tuple[str, ...]:
    base = stem(term)
    if len(base) >= 4 and base[-1] in _SOFT:
        return base, base[:-1] + _SOFT[base[-1]]
    return (base,)


class Term:
    """A query term with its stems precomputed, for scanning many tokens."""

    def __init__(self, text: str):
        self.folded = fold(text)
        self.stems = _stems(self.folded)

    def kind(self, token: str) -> str | None:
        """'exact' if the folded forms are equal, 'stem' if token looks like an inflection."""
        if token == self.folded:
            return "exact"
        if token.startswith(self.stems):
            return "stem"
        return None


def match_kind(term: str, token: str) -> str | None:
    return Term(term).kind(fold(token))


def matches(term: str, token: str) -> bool:
    return match_kind(term, token) is not None
