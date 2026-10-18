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


class Hyprland:
    def __init__(self) -> None:
        self._path: Path | None = None

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

    def dispatch(self, args: str) -> None:
        reply = self.request(f"dispatch {args}").strip()
        if reply != "ok":
            log.warning("hyprctl dispatch %s: %s", args, reply)

    def monitors(self) -> list[dict[str, Any]]:
        return json.loads(self.request("j/monitors"))

    def focused_monitor(self) -> Monitor:
        monitors = self.monitors()
        focused = next((m for m in monitors if m.get("focused")), monitors[0])
        return logical_monitor(focused)

    def move_cursor(self, x: float, y: float) -> None:
        self.dispatch(f"movecursor {round(x)} {round(y)}")
