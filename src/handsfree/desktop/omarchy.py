"""The real desktop backend for Omarchy (Hyprland on Wayland)."""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Any

from . import Monitor
from .hypr import Hyprland
from .keys import parse_combo
from .notify import Notifier

log = logging.getLogger(__name__)


def _spawn(args: list[str]) -> None:
    # Detach so launched apps outlive a daemon restart.
    subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


class OmarchyDesktop:
    def __init__(self, settings: dict[str, Any], gaze_settings: dict[str, Any]):
        self.settings = settings
        self.gaze_settings = gaze_settings
        self.hyprland = Hyprland()
        self.notifier = Notifier()
        self._input = None

    def _virtual_input(self):
        if self._input is None:
            from .uinput import VirtualInput

            self._input = VirtualInput(int(self.settings.get("scroll_steps", 5)))
        return self._input

    def warm_up(self) -> None:
        """Create the virtual input devices now: the first one can take seconds
        to appear, which would otherwise delay the first click or key press."""
        if os.access("/dev/uinput", os.W_OK):
            try:
                self._virtual_input()
            except Exception as exc:
                log.warning("virtual input unavailable: %s", exc)

    def run_shell(self, command: str) -> None:
        _spawn(["sh", "-c", command])

    def open_url(self, url: str) -> None:
        _spawn(list(self.settings.get("url_opener", ["xdg-open"])) + [url])

    def launch_app(self, app: Any) -> None:
        _spawn(list(self.settings.get("app_launcher", ["uwsm", "app", "--"])) + [app.desktop_id])

    def hypr(self, args: str) -> None:
        self.hyprland.dispatch(args)

    def type_text(self, text: str) -> None:
        # wtype handles any Unicode via the virtual-keyboard protocol; stdin
        # avoids text that starts with "-" being read as an option.
        subprocess.run(["wtype", "-"], input=text, text=True, check=True, timeout=30)

    def key(self, combo: str) -> None:
        self._virtual_input().key_combo(parse_combo(combo))

    def mouse(self, op: str) -> None:
        self._virtual_input().mouse(op)

    def move_cursor(self, x: float, y: float) -> None:
        self.hyprland.move_cursor(x, y)

    def focused_monitor(self) -> Monitor:
        return self.hyprland.focused_monitor()

    def overlay(self, monitor: Monitor):
        from .overlay_client import Overlay

        return Overlay(
            monitor.name,
            python=self.gaze_settings.get("overlay_python", "/usr/bin/python3"),
            layer_shell_lib=self.gaze_settings.get("layer_shell_lib", "/usr/lib/libgtk4-layer-shell.so"),
        )

    def notify(self, title: str, body: str = "") -> None:
        self.notifier.show(title, body)
