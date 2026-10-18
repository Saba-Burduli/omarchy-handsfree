"""Everything that touches the desktop goes through a `Desktop`.

`OmarchyDesktop` (in `omarchy.py`) talks to Hyprland, wtype, uinput and
notify-send. `DryRunDesktop` only logs, so the daemon and its tests run
anywhere, including off Linux.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Monitor:
    """A monitor in Hyprland's global layout, in logical (scaled) pixels."""

    name: str
    x: float
    y: float
    width: float
    height: float

    @property
    def rect(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.width, self.height)


class Desktop(Protocol):
    def run_shell(self, command: str) -> None: ...
    def open_url(self, url: str) -> None: ...
    def launch_app(self, app: Any) -> None: ...
    def hypr(self, args: str) -> None: ...
    def type_text(self, text: str) -> None: ...
    def key(self, combo: str) -> None: ...
    def mouse(self, op: str) -> None: ...
    def move_cursor(self, x: float, y: float) -> None: ...
    def focused_monitor(self) -> Monitor: ...
    def overlay(self, monitor: Monitor) -> Any: ...
    def notify(self, title: str, body: str = "") -> None: ...


class DryRunDesktop:
    """Logs every action instead of performing it; `calls` keeps a record."""

    def __init__(self, monitor: Monitor | None = None):
        self.monitor = monitor or Monitor("DRY-1", 0, 0, 1920, 1080)
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def _record(self, name: str, *args: Any) -> None:
        self.calls.append((name, args))
        log.info("[dry-run] %s %s", name, " ".join(repr(a) for a in args))

    def run_shell(self, command: str) -> None:
        self._record("run_shell", command)

    def open_url(self, url: str) -> None:
        self._record("open_url", url)

    def launch_app(self, app: Any) -> None:
        self._record("launch_app", getattr(app, "desktop_id", app))

    def hypr(self, args: str) -> None:
        self._record("hypr", args)

    def type_text(self, text: str) -> None:
        self._record("type_text", text)

    def key(self, combo: str) -> None:
        self._record("key", combo)

    def mouse(self, op: str) -> None:
        self._record("mouse", op)

    def move_cursor(self, x: float, y: float) -> None:
        # Gaze moves the pointer many times a second; keep it out of the log.
        self.calls.append(("move_cursor", (x, y)))

    def focused_monitor(self) -> Monitor:
        return self.monitor

    def overlay(self, monitor: Monitor):
        from .overlay_client import NullOverlay

        self._record("overlay", monitor.name)
        self.last_overlay = NullOverlay()
        return self.last_overlay

    def notify(self, title: str, body: str = "") -> None:
        self._record("notify", title, body)
