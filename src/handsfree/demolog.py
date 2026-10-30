"""Opt-in command log for editing demo videos. Off unless HANDSFREE_DEMO_LOG is set.

HANDSFREE_DEMO_LOG=<path> (or 1 for $XDG_RUNTIME_DIR/handsfree-demo.jsonl)
appends one JSON line per handled command, written once its result has
settled (a new window has appeared and stopped moving):

  {"t": 12.3, "t_done": 13.1, "heard": "open neovim", "action": "...", "ok": true,
   "window": {"x", "y", "w", "h", "class"}, "monitor": {"x", "y", "w", "h", "scale"}}

`t` is when the action ran, in seconds since HANDSFREE_DEMO_T0 (Unix time,
e.g. when the screen recorder started), else since the daemon started.
Window coordinates are Hyprland's logical layout; monitor w/h are pixels.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)

WINDOW_TIMEOUT = 4.0  # launches: how long to wait for the new window
CHANGE_TIMEOUT = 0.8  # other commands: how long to watch for a window change
STABLE = 0.3  # a window counts as settled once unchanged this long


class DemoLog:
    def __init__(self, path: Path, t0: float, query: Callable[[str], str]):
        self.path = path
        self.t0 = t0
        self._query = query
        self._write_lock = threading.Lock()

    @classmethod
    def from_env(cls, env: dict[str, str] = os.environ) -> "DemoLog | None":
        value = env.get("HANDSFREE_DEMO_LOG", "")
        if not value or value == "0":
            return None
        if value == "1":
            path = Path(env.get("XDG_RUNTIME_DIR", "/tmp")) / "handsfree-demo.jsonl"
        else:
            path = Path(value)
        t0 = float(env.get("HANDSFREE_DEMO_T0") or time.time())
        from .desktop.hypr import Hyprland

        log.info("demo log: %s", path)
        return cls(path, t0, Hyprland().request)

    def snapshot(self) -> dict[str, Any] | None:
        """The active window's rect, or None if there is none (or no Hyprland)."""
        try:
            win = json.loads(self._query("j/activewindow") or "{}")
        except Exception:
            return None
        if not win or "at" not in win:
            return None
        (x, y), (w, h) = win["at"], win["size"]
        return {"x": x, "y": y, "w": w, "h": h, "class": win.get("class", "")}

    def _monitor(self) -> dict[str, Any] | None:
        try:
            monitors = json.loads(self._query("j/monitors"))
            m = next((m for m in monitors if m.get("focused")), monitors[0])
        except Exception:
            return None
        return {"x": m["x"], "y": m["y"], "w": m["width"], "h": m["height"], "scale": m.get("scale", 1)}

    def record(self, heard: str, action: str, ok: bool, before: dict[str, Any] | None,
               started: float, launches: bool = False) -> None:
        """Log in the background once the result settles; never blocks the caller."""
        threading.Thread(
            target=self._settle_and_write, args=(heard, action, ok, before, started, launches),
            name="demo-log", daemon=True,
        ).start()

    def _settle_and_write(self, heard, action, ok, before, started, launches=False, sleep=time.sleep) -> None:
        window = self.snapshot()
        deadline = time.time() + (WINDOW_TIMEOUT if launches and ok else CHANGE_TIMEOUT)
        stable_since = None
        while time.time() < deadline:
            sleep(0.1)
            current = self.snapshot()
            if current != window:
                window, stable_since = current, time.time()
            elif window != before and stable_since is None:
                stable_since = time.time()
            if stable_since is not None and window != before and time.time() - stable_since >= STABLE:
                break
        self.write({
            "t": round(started - self.t0, 3),
            "t_done": round(time.time() - self.t0, 3),
            "heard": heard,
            "action": action,
            "ok": ok,
            "window": window,
            "monitor": self._monitor(),
        })

    def write(self, entry: dict[str, Any]) -> None:
        line = json.dumps(entry) + "\n"
        with self._write_lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as f:
                f.write(line)
