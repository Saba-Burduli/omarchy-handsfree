"""Parse spoken or written key combos into evdev key names (without KEY_)."""

from __future__ import annotations

import re

ALIASES = {
    "ctrl": "LEFTCTRL", "control": "LEFTCTRL", "shift": "LEFTSHIFT",
    "alt": "LEFTALT", "option": "LEFTALT",
    "super": "LEFTMETA", "meta": "LEFTMETA", "windows": "LEFTMETA", "win": "LEFTMETA",
    "command": "LEFTMETA", "cmd": "LEFTMETA",
    "enter": "ENTER", "return": "ENTER", "escape": "ESC", "esc": "ESC", "tab": "TAB",
    "space": "SPACE", "spacebar": "SPACE", "backspace": "BACKSPACE", "delete": "DELETE",
    "del": "DELETE", "insert": "INSERT", "home": "HOME", "end": "END",
    "up": "UP", "down": "DOWN", "left": "LEFT", "right": "RIGHT",
    "pageup": "PAGEUP", "pagedown": "PAGEDOWN",
    "minus": "MINUS", "dash": "MINUS", "equal": "EQUAL", "equals": "EQUAL",
    "slash": "SLASH", "backslash": "BACKSLASH", "period": "DOT", "dot": "DOT",
    "comma": "COMMA", "semicolon": "SEMICOLON", "apostrophe": "APOSTROPHE",
    "grave": "GRAVE", "backtick": "GRAVE",
}
PAIRS = {
    ("page", "up"): "PAGEUP", ("page", "down"): "PAGEDOWN", ("caps", "lock"): "CAPSLOCK",
    ("print", "screen"): "SYSRQ", ("back", "space"): "BACKSPACE", ("space", "bar"): "SPACE",
}
DIGITS = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
          "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"}
_FKEY = re.compile(r"^f([1-9]|1[0-9]|2[0-4])$")


def _name(word: str) -> str:
    if word in ALIASES:
        return ALIASES[word]
    if word in DIGITS:
        return DIGITS[word]
    if len(word) == 1 and word.isalnum():
        return word.upper()
    if _FKEY.match(word):
        return word.upper()
    raise ValueError(f"unknown key {word!r}")


def parse_combo(spoken: str) -> list[str]:
    """'ctrl+shift+t', 'Control L.' or 'page down' -> ['LEFTCTRL', 'L'] etc."""
    words = [w.strip(".,!?;:") for w in re.split(r"[\s+\-]+", spoken.lower())]
    words = [w for w in words if w]
    names: list[str] = []
    i = 0
    while i < len(words):
        pair = tuple(words[i:i + 2])
        if pair in PAIRS:
            names.append(PAIRS[pair])
            i += 2
        else:
            names.append(_name(words[i]))
            i += 1
    if not names:
        raise ValueError("no key given")
    return names
