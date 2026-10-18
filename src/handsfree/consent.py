"""Explicit opt-in for the microphone and camera.

Linux has no per-app permission prompt for these devices, so handsfree keeps
its own record of what the user agreed to and refuses to open a device
without it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import state_dir


def consent_path() -> Path:
    return state_dir() / "consent.json"


@dataclass
class Consent:
    microphone: bool = False
    camera: bool = False

    @classmethod
    def load(cls, path: Path | None = None) -> "Consent":
        path = path or consent_path()
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            return cls()
        return cls(microphone=bool(data.get("microphone")), camera=bool(data.get("camera")))

    def save(self, path: Path | None = None) -> None:
        path = path or consent_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n")
