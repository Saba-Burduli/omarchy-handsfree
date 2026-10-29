"""Text helpers shared by the intent parser and the app index."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

try:
    from rapidfuzz import fuzz as _fuzz
except ImportError:  # optional; difflib is close enough for short phrases
    _fuzz = None

_EDGE_PUNCT = re.compile(r"^[^\w']+|[^\w']+$")
_FILLERS = {"please", "okay", "ok", "um", "uh", "ugh", "oh", "hey", "so", "and", "now", "alright"}

NUMBER_WORDS = {
    "zero": 0, "one": 1, "won": 1, "two": 2, "to": 2, "too": 2, "three": 3, "four": 4,
    "for": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "ate": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}


@dataclass(frozen=True)
class Tokens:
    raw: list[str]   # words as spoken, for typed text and search queries
    norm: list[str]  # lowercase, edge punctuation stripped, for matching


def normalize(text: str) -> str:
    return " ".join(tokenize(text).norm)


def tokenize(text: str, strip_fillers: bool = False) -> Tokens:
    raw: list[str] = []
    norm: list[str] = []
    for word in text.replace("’", "'").split():
        cleaned = _EDGE_PUNCT.sub("", word).lower()
        if cleaned:
            raw.append(word)
            norm.append(cleaned)
    if strip_fillers:
        while norm and norm[0] in _FILLERS:
            raw, norm = raw[1:], norm[1:]
        while norm and norm[-1] == "please":
            raw, norm = raw[:-1], norm[:-1]
    return Tokens(raw, norm)


def parse_number(words: list[str]) -> int | None:
    if len(words) != 1:
        return None
    word = words[0]
    if word.isdigit():
        return int(word)
    return NUMBER_WORDS.get(word)


def similarity(a: str, b: str) -> float:
    """0-100 similarity of two normalized strings."""
    if _fuzz is not None:
        return float(_fuzz.ratio(a, b))
    return difflib.SequenceMatcher(None, a, b).ratio() * 100
