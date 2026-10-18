"""Execute a parsed intent on the desktop."""

from __future__ import annotations

import re
import shlex
from typing import Any, Callable
from urllib.parse import quote_plus

from ..desktop import Desktop
from .parser import Intent

ACTIONS = ("run", "url", "app", "hypr", "type", "key", "mouse", "internal")
RAW_SLOTS = {"site"}  # already URLs; never quote them inside URL templates

InternalHandler = Callable[[str, dict[str, Any]], str]


def fill(template: str, slots: dict[str, Any], quote: Callable[[str], str]) -> str:
    def substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in slots:
            raise KeyError(f"command uses {{{name}}} but its phrase has no such slot")
        value = str(slots[name])
        return value if name in RAW_SLOTS and quote is quote_plus else quote(value)

    return re.sub(r"\{(\w+)\}", substitute, template)


def _same(value: str) -> str:
    return value


class Executor:
    def __init__(self, desktop: Desktop, internal: InternalHandler | None = None):
        self.desktop = desktop
        self.internal = internal

    def execute(self, intent: Intent) -> str:
        for action in ACTIONS:
            if action in intent.command:
                return getattr(self, f"_{action}")(intent.command[action], intent.slots)
        raise ValueError(f"command {intent.command.get('say')!r} has no action")

    def _run(self, template: str, slots: dict[str, Any]) -> str:
        command = fill(template, slots, shlex.quote)
        self.desktop.run_shell(command)
        return f"ran {command}"

    def _url(self, template: str, slots: dict[str, Any]) -> str:
        url = fill(template, slots, quote_plus)
        self.desktop.open_url(url)
        return f"opened {url}"

    def _app(self, _template: str, slots: dict[str, Any]) -> str:
        app = slots["app"]
        self.desktop.launch_app(app)
        return f"launched {app.name}"

    def _hypr(self, template: str, slots: dict[str, Any]) -> str:
        args = fill(template, slots, _same)
        self.desktop.hypr(args)
        return f"hyprland: {args}"

    def _type(self, template: str, slots: dict[str, Any]) -> str:
        text = fill(template, slots, _same)
        self.desktop.type_text(text)
        return f'typed "{text}"'

    def _key(self, template: str, slots: dict[str, Any]) -> str:
        combo = fill(template, slots, _same)
        self.desktop.key(combo)
        return f"pressed {combo}"

    def _mouse(self, op: str, _slots: dict[str, Any]) -> str:
        self.desktop.mouse(op)
        return op.replace("_", " ")

    def _internal(self, name: str, slots: dict[str, Any]) -> str:
        if self.internal is None:
            raise ValueError(f"no handler for internal command {name!r}")
        return self.internal(name, slots)
