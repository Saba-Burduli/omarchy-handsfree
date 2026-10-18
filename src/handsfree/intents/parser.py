"""Turn a transcript into the best matching command from commands.toml.

Patterns are word sequences with slots, e.g. "open {site}". Candidates are
ranked by: exact match > fuzzy slot value > fuzzy whole phrase, then by how
many literal words matched (so "open claude code" beats "open {site}"), then
by file order.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from .text import Tokens, parse_number, similarity, tokenize

_SLOT = re.compile(r"^\{(\w+)\}$")
_TRAILING_PUNCT = ".!?,;:"


class AppFinder(Protocol):
    def find(self, spoken: str) -> tuple[Any, float] | None: ...


@dataclass(frozen=True)
class Slot:
    name: str


Pattern = list[str | Slot]


@dataclass
class Intent:
    command: dict[str, Any]
    slots: dict[str, Any] = field(default_factory=dict)
    text: str = ""
    exact: bool = True


def compile_pattern(phrase: str) -> Pattern:
    out: Pattern = []
    for word in phrase.split():
        match = _SLOT.match(word)
        if match:
            out.append(Slot(match.group(1)))
        else:
            norm = tokenize(word).norm
            out.append(norm[0] if norm else word.lower())
    return out


def _bindings(pattern: Pattern, words: list[str], i: int = 0, j: int = 0) -> list[dict[str, tuple[int, int]]]:
    """Every way to align the pattern with the words; slots take 1+ words."""
    if i == len(pattern):
        return [{}] if j == len(words) else []
    part = pattern[i]
    if isinstance(part, str):
        if j < len(words) and words[j] == part:
            return _bindings(pattern, words, i + 1, j + 1)
        return []
    results = []
    for end in range(j + 1, len(words) + 1):
        for rest in _bindings(pattern, words, i + 1, end):
            results.append({part.name: (j, end), **rest})
    return results


class Parser:
    def __init__(self, commands: dict[str, Any], apps: AppFinder | None = None, threshold: float = 82):
        self.sites = {" ".join(tokenize(k).norm): v for k, v in commands.get("sites", {}).items()}
        self.apps = apps
        self.threshold = threshold
        self._patterns: list[tuple[dict[str, Any], Pattern]] = []
        for command in commands.get("command", []):
            phrases = command["say"] if isinstance(command["say"], list) else [command["say"]]
            for phrase in phrases:
                self._patterns.append((command, compile_pattern(phrase)))

    def parse(self, text: str) -> Intent | None:
        tokens = tokenize(text, strip_fillers=True)
        if not tokens.norm:
            return None
        best: tuple[tuple, Intent] | None = None
        for index, (command, pattern) in enumerate(self._patterns):
            for rank, intent in self._candidates(command, pattern, tokens, index):
                if best is None or rank > best[0]:
                    best = (rank, intent)
        if best is None:
            return None
        best[1].text = text
        return best[1]

    def _candidates(self, command: dict[str, Any], pattern: Pattern, tokens: Tokens, index: int):
        literals = sum(isinstance(p, str) for p in pattern)
        for binding in _bindings(pattern, tokens.norm):
            slots: dict[str, Any] = {}
            scores: list[float] = []
            for name, (start, end) in binding.items():
                resolved = self._resolve(name, tokens.raw[start:end], tokens.norm[start:end])
                if resolved is None:
                    break
                slots[name], score = resolved
                scores.append(score)
            else:
                exact = all(s >= 100 for s in scores)
                rank = (3 if exact else 2, literals, min(scores, default=100.0), -index)
                yield rank, Intent(command, slots, exact=exact)
        if literals == len(pattern):
            score = similarity(" ".join(tokens.norm), " ".join(pattern))  # type: ignore[arg-type]
            if self.threshold <= score < 100:
                yield (1, literals, score, -index), Intent(command, {}, exact=False)

    def _resolve(self, name: str, raw: list[str], norm: list[str]) -> tuple[Any, float] | None:
        spoken = " ".join(norm)
        if name == "site":
            if spoken in self.sites:
                return self.sites[spoken], 100.0
            scored = [(similarity(spoken, key), url) for key, url in self.sites.items()]
            score, url = max(scored, default=(0.0, ""))
            return (url, score) if score >= self.threshold else None
        if name == "app":
            return self.apps.find(spoken) if self.apps else None
        if name == "n":
            number = parse_number(norm)
            return (str(number), 100.0) if number is not None else None
        if name == "key":
            return spoken, 100.0
        value = " ".join(raw).rstrip(_TRAILING_PUNCT)
        return (value, 100.0) if value else None
