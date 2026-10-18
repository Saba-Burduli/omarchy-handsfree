"""Drive the GTK overlay process (see overlay.py) from the daemon."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

SCRIPT = Path(__file__).with_name("overlay.py")


class Overlay:
    def __init__(self, monitor_name: str, python: str = "/usr/bin/python3",
                 layer_shell_lib: str = "/usr/lib/libgtk4-layer-shell.so"):
        env = dict(os.environ)
        if layer_shell_lib and Path(layer_shell_lib).exists():
            env["LD_PRELOAD"] = layer_shell_lib
        else:
            log.warning("%s not found; install gtk4-layer-shell", layer_shell_lib)
        self._proc = subprocess.Popen(
            [python, str(SCRIPT), "--monitor", monitor_name],
            stdin=subprocess.PIPE,
            text=True,
            env=env,
        )

    def _send(self, message: dict[str, Any]) -> None:
        if self._proc.poll() is not None or self._proc.stdin is None:
            raise RuntimeError("overlay exited; check that python-gobject and gtk4-layer-shell are installed")
        self._proc.stdin.write(json.dumps(message) + "\n")
        self._proc.stdin.flush()

    def dot(self, x: float, y: float, label: str = "") -> None:
        self._send({"mode": "dot", "x": x, "y": y, "label": label})

    def grid(self, cells: list[tuple[float, float, float, float]]) -> None:
        self._send({"mode": "grid", "cells": [list(c) for c in cells]})

    def clear(self) -> None:
        self._send({"mode": "clear"})

    def close(self) -> None:
        if self._proc.stdin:
            try:
                self._proc.stdin.close()
            except BrokenPipeError:
                pass
        try:
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proc.kill()


class NullOverlay:
    """Dry-run stand-in that remembers what it would have drawn."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.closed = False

    def dot(self, x: float, y: float, label: str = "") -> None:
        self.messages.append({"mode": "dot", "x": x, "y": y, "label": label})

    def grid(self, cells: list[tuple[float, float, float, float]]) -> None:
        self.messages.append({"mode": "grid", "cells": [list(c) for c in cells]})

    def clear(self) -> None:
        self.messages.append({"mode": "clear"})

    def close(self) -> None:
        self.closed = True
