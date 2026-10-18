"""Waybar custom-module output: a privacy indicator for the mic and camera.

The module shows an icon only while a device can be in use, so an empty
module means the microphone and camera are both closed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .config import state_file

# Nerd Font (Material Design) glyphs, which Omarchy's Waybar font includes.
MIC = "\U000F036C"
EYE = "\U000F0208"
PENCIL = "\U000F03EB"
GRID = "\U000F0570"


def _alive(pid: Any) -> bool:
    try:
        os.kill(int(pid), 0)
    except (TypeError, ValueError, ProcessLookupError):
        return False
    except PermissionError:
        return True
    return True


def read_state(path: Path | None = None) -> dict[str, Any] | None:
    try:
        state = json.loads((path or state_file()).read_text())
    except (OSError, ValueError):
        return None
    # A crashed daemon leaves its state file behind; don't show stale icons.
    return state if _alive(state.get("pid")) else None


def status(state: dict[str, Any] | None) -> dict[str, Any]:
    if state is None:
        return {"text": "", "tooltip": "Hands-free is not running", "class": "stopped"}
    icons: list[str] = []
    classes: list[str] = []
    lines: list[str] = []
    if state.get("listening"):
        icons.append(MIC)
        classes.append("listening")
        lines.append("Listening now")
    elif state.get("voice") == "continuous":
        icons.append(MIC)
        classes.append("voice")
        lines.append("Listening continuously")
    else:
        lines.append("Voice: push-to-talk (microphone closed)")
    if state.get("dictation"):
        icons.append(PENCIL)
        classes.append("dictation")
        lines.append("Dictation on")
    if state.get("gaze"):
        icons.append(EYE)
        classes.append("gaze")
        lines.append("Eye tracking on (camera open)")
    else:
        lines.append("Eye tracking off (camera closed)")
    if state.get("grid"):
        icons.append(GRID)
        classes.append("grid")
    if state.get("last"):
        lines.append(f"Last heard: “{state['last']}”")
    return {"text": " ".join(icons), "tooltip": "\n".join(lines), "class": classes or "idle"}
