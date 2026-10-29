"""Hyprland IPC over its request socket (same protocol `hyprctl` uses).

Talking to the socket directly avoids spawning `hyprctl` for every pointer
move while gaze tracking runs at camera frame rate.
"""

from __future__ import annotations

import json
import logging
import os
import socket
from pathlib import Path
from typing import Any

from . import Monitor

log = logging.getLogger(__name__)


def _socket_path() -> Path:
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not signature:
        raise RuntimeError("HYPRLAND_INSTANCE_SIGNATURE is not set; is Hyprland running?")
    runtime = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    for base in (Path(runtime) / "hypr", Path("/tmp/hypr")):
        path = base / signature / ".socket.sock"
        if path.exists():
            return path
    raise RuntimeError(f"Hyprland socket for {signature} not found")


def logical_monitor(data: dict[str, Any]) -> Monitor:
    """Convert a `hyprctl -j monitors` entry to logical layout coordinates."""
    scale = float(data.get("scale") or 1.0)
    width, height = data["width"] / scale, data["height"] / scale
    if int(data.get("transform", 0)) % 2:  # 90/270 degree rotations swap axes
        width, height = height, width
    return Monitor(data["name"], float(data["x"]), float(data["y"]), width, height)


def _lua_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def to_lua(args: str) -> str:
    """Translate a classic dispatcher ("workspace 2") to Hyprland's Lua API.

    Hyprland 0.55+ with a Lua config (Omarchy 4) evaluates `dispatch` as Lua,
    e.g. hl.dsp.focus({ workspace = "2" }). commands.toml keeps the classic
    form so it works on both; anything starting with "hl." passes through.
    """
    args = args.strip()
    if args.startswith("hl."):
        return args
    name, _, rest = args.partition(" ")
    rest = rest.strip()
    if name == "movecursor":
        x, y = rest.split()
        return f"hl.dsp.cursor.move({{ x = {int(float(x))}, y = {int(float(y))} }})"
    if name == "killactive":
        return "hl.dsp.window.close()"
    if name == "fullscreen":
        mode = "maximized" if rest == "1" else "fullscreen"
        return f'hl.dsp.window.fullscreen({{ mode = "{mode}", action = "toggle" }})'
    if name == "togglefloating":
        return 'hl.dsp.window.float({ action = "toggle" })'
    if name == "workspace":
        return f"hl.dsp.focus({{ workspace = {_lua_string(rest)} }})"
    if name == "movetoworkspace":
        return f"hl.dsp.window.move({{ workspace = {_lua_string(rest)} }})"
    if name == "movetoworkspacesilent":
        return f"hl.dsp.window.move({{ workspace = {_lua_string(rest)}, follow = false }})"
    if name == "movefocus":
        return f"hl.dsp.focus({{ direction = {_lua_string(rest)} }})"
    if name == "exec":
        return f"hl.dsp.exec_cmd({_lua_string(rest)})"
    raise ValueError(f"no Lua form known for dispatcher {name!r}; write it as hl.dsp...(...) in commands.toml")


class Hyprland:
    def __init__(self) -> None:
        self._path: Path | None = None
        self._lua: bool | None = None

    def request(self, command: str) -> str:
        if self._path is None:
            self._path = _socket_path()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(2.0)
            sock.connect(str(self._path))
            sock.sendall(command.encode())
            chunks = []
            while chunk := sock.recv(65536):
                chunks.append(chunk)
        return b"".join(chunks).decode(errors="replace")

    @property
    def lua(self) -> bool:
        """Whether dispatchers must be Lua (probed once with a no-op)."""
        if self._lua is None:
            self._lua = self.request("dispatch hl.dsp.no_op()").strip() == "ok"
            log.info("Hyprland dispatch syntax: %s", "Lua" if self._lua else "classic")
        return self._lua

    def dispatch(self, args: str) -> None:
        command = to_lua(args) if self.lua else args
        reply = self.request(f"dispatch {command}").strip()
        if reply != "ok":
            raise RuntimeError(f"hyprctl dispatch {command}: {reply}")

    def monitors(self) -> list[dict[str, Any]]:
        return json.loads(self.request("j/monitors"))

    def focused_monitor(self) -> Monitor:
        monitors = self.monitors()
        focused = next((m for m in monitors if m.get("focused")), monitors[0])
        return logical_monitor(focused)

    def move_cursor(self, x: float, y: float) -> None:
        self.dispatch(f"movecursor {round(x)} {round(y)}")
