"""`handsfree-ctl doctor`: check everything the daemon depends on."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .consent import Consent
from .gaze.engine import model_path


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    required: bool = True


def _check(name: str, ok: bool, fail: str, required: bool = True) -> Check:
    """A check whose hint only matters when it fails."""
    return Check(name, ok, "" if ok else fail, required)


def _module(name: str, extra: str) -> Check:
    found = importlib.util.find_spec(name) is not None
    return Check(f"python module {name}", found, "" if found else f"reinstall with the [{extra}] extra")


def _command(name: str, why: str) -> Check:
    path = shutil.which(name)
    return Check(f"command {name}", path is not None, path or f"missing; needed for {why}")


def run_checks(config: Config | None = None) -> list[Check]:
    config = config or Config.load()
    gaze = config.section("gaze")
    consent = Consent.load()
    checks = [
        _check("Hyprland session", bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")),
               fail="HYPRLAND_INSTANCE_SIGNATURE not set (run inside Hyprland / uwsm)"),
        _command("wtype", "typing and dictation"),
        _command("notify-send", "feedback notifications"),
        _command("omarchy-launch-browser", "opening sites (or set desktop.url_opener)"),
        _command("uwsm", "launching apps (or set desktop.app_launcher)"),
        _check("/dev/uinput writable", os.access("/dev/uinput", os.W_OK),
               fail="clicks and keys need the udev rule from install.sh (log out and in after installing)"),
        _module("faster_whisper", "voice"),
        _module("sounddevice", "voice"),
        _module("evdev", "input"),
        _module("mediapipe", "gaze"),
        _module("cv2", "gaze"),
    ]
    if config.section("voice").get("wake_word"):
        checks.append(_module("openwakeword", "wake"))
    model = model_path(gaze)
    checks.append(Check("face landmarker model", model.exists(), str(model) if model.exists() else f"missing: {model}"))
    lib = Path(gaze.get("layer_shell_lib", "/usr/lib/libgtk4-layer-shell.so"))
    checks.append(Check("gtk4-layer-shell", lib.exists(), str(lib) if lib.exists() else "pacman -S gtk4-layer-shell"))
    python = gaze.get("overlay_python", "/usr/bin/python3")
    try:
        probe = subprocess.run(
            [python, "-c", "import gi; gi.require_version('Gtk4LayerShell', '1.0'); import cairo"],
            capture_output=True, text=True, timeout=10,
        )
        overlay_ok, detail = probe.returncode == 0, (probe.stderr.strip().splitlines() or [""])[-1]
    except OSError as exc:
        overlay_ok, detail = False, str(exc)
    checks.append(_check("overlay Python (PyGObject + cairo)", overlay_ok,
                         fail=detail or "pacman -S python-gobject python-cairo"))
    videos = sorted(Path("/dev").glob("video*"))
    checks.append(Check("webcam", bool(videos), ", ".join(map(str, videos)) or "no /dev/video* device", required=False))
    checks.append(_check("microphone consent", consent.microphone, fail="run handsfree-ctl setup", required=False))
    checks.append(_check("camera consent", consent.camera, fail="run handsfree-ctl setup", required=False))
    return checks


def report(checks: list[Check]) -> int:
    for check in checks:
        mark = "ok  " if check.ok else ("FAIL" if check.required else "warn")
        print(f"[{mark}] {check.name}" + (f"  - {check.detail}" if check.detail else ""))
    return 0 if all(c.ok or not c.required for c in checks) else 1
