"""Installed applications, read from .desktop files (what Walker shows)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from .text import normalize, similarity


@dataclass(frozen=True)
class AppEntry:
    desktop_id: str
    name: str
    keywords: tuple[str, ...] = ()


def application_dirs() -> list[Path]:
    data_home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local/share")
    data_dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    return [Path(d) / "applications" for d in [data_home, *data_dirs.split(":")] if d]


def parse_desktop_file(path: Path, desktop_id: str) -> AppEntry | None:
    fields: dict[str, str] = {}
    in_entry = False
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return None
    for line in lines:
        line = line.strip()
        if line.startswith("["):
            in_entry = line == "[Desktop Entry]"
            continue
        if in_entry and "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            fields.setdefault(key.strip(), value.strip())
    if fields.get("Type") != "Application" or "Name" not in fields:
        return None
    if fields.get("NoDisplay", "").lower() == "true" or fields.get("Hidden", "").lower() == "true":
        return None
    keywords = tuple(k for k in fields.get("Keywords", "").split(";") if k)
    return AppEntry(desktop_id, fields["Name"], keywords)


class AppIndex:
    def __init__(self, entries: list[AppEntry], threshold: float = 80):
        self.entries = entries
        self.threshold = threshold
        self._names = [(normalize(e.name), e) for e in entries]

    @classmethod
    def scan(cls, dirs: list[Path] | None = None, threshold: float = 80) -> "AppIndex":
        seen: dict[str, AppEntry] = {}
        for base in dirs or application_dirs():
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*.desktop")):
                desktop_id = str(path.relative_to(base)).replace(os.sep, "-")
                if desktop_id in seen:  # earlier dirs (user's) win, per the XDG spec
                    continue
                entry = parse_desktop_file(path, desktop_id)
                if entry:
                    seen[desktop_id] = entry
        return cls(list(seen.values()), threshold)

    def find(self, spoken: str) -> tuple[AppEntry, float] | None:
        """Best app for a spoken name with a 0-100 score; 100 means exact."""
        spoken = normalize(spoken)
        if not spoken:
            return None
        best: tuple[AppEntry, float] | None = None
        for name, entry in self._names:
            stem = normalize(entry.desktop_id.removesuffix(".desktop").replace("-", " ").replace(".", " "))
            if spoken in (name, stem):
                return entry, 100.0
            score = max(similarity(spoken, name), similarity(spoken, stem))
            if any(normalize(k) == spoken for k in entry.keywords):
                score = max(score, 90.0)
            if score >= self.threshold and (best is None or score > best[1]):
                best = (entry, score)
        return best


class LazyAppIndex:
    """Rescans at most once a minute so newly installed apps show up."""

    def __init__(self, ttl: float = 60.0, threshold: float = 80):
        self.ttl = ttl
        self.threshold = threshold
        self._index: AppIndex | None = None
        self._loaded = 0.0

    def find(self, spoken: str) -> tuple[AppEntry, float] | None:
        if self._index is None or time.monotonic() - self._loaded > self.ttl:
            self._index = AppIndex.scan(threshold=self.threshold)
            self._loaded = time.monotonic()
        return self._index.find(spoken)
