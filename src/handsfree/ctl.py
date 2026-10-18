"""`handsfree-ctl`: control the daemon (bind these to Hyprland keys)."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .config import socket_path
from .consent import Consent
from .ipc import request

SETUP_TEXT = """\
omarchy-handsfree uses your microphone and webcam to control the desktop.

  * Everything runs on this computer. No audio or video leaves it.
  * The microphone is only open while you push-to-talk, or while continuous
    listening is on. The camera is only open while eye tracking is on.
  * The Waybar icon shows when either device is in use.
  * Change your mind any time by running `handsfree-ctl setup` again.
"""


def _send(cmd: str, arg: Any = None, quiet_if_down: bool = False) -> int:
    try:
        response = request(socket_path(), {"cmd": cmd, "arg": arg})
    except (FileNotFoundError, ConnectionRefusedError):
        if not quiet_if_down:
            print("handsfree is not running (systemctl --user start handsfree)", file=sys.stderr)
        return 1
    if not response.get("ok"):
        print(response.get("error", "request failed"), file=sys.stderr)
        return 1
    if "state" in response:
        print(json.dumps(response["state"], indent=2))
    elif response.get("message"):
        print(response["message"])
    return 0


def _ask(question: str, current: bool) -> bool:
    answer = input(f"{question} [{'Y/n' if current else 'y/N'}] ").strip().lower()
    return current if not answer else answer in ("y", "yes")


def setup() -> int:
    print(SETUP_TEXT)
    consent = Consent.load()
    try:
        consent.microphone = _ask("Allow the microphone for voice commands?", consent.microphone)
        consent.camera = _ask("Allow the webcam for eye tracking?", consent.camera)
    except (EOFError, KeyboardInterrupt):
        print("\nNothing changed.")
        return 1
    consent.save()
    # Turn off anything that just lost its permission.
    if not consent.microphone:
        _send("voice", "off", quiet_if_down=True)
    if not consent.camera:
        _send("gaze", "off", quiet_if_down=True)
    print(f"\nMicrophone: {'allowed' if consent.microphone else 'off'}")
    print(f"Camera:     {'allowed' if consent.camera else 'off'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="handsfree-ctl", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("listen", help="push-to-talk: listen for one command (press again to stop early)")
    voice = sub.add_parser("voice", help="continuous listening")
    voice.add_argument("mode", choices=["on", "off", "toggle"])
    gaze = sub.add_parser("gaze", help="eye tracking moves the pointer")
    gaze.add_argument("mode", choices=["on", "off", "toggle"])
    sub.add_parser("calibrate", help="calibrate eye tracking for the focused monitor")
    sub.add_parser("grid", help="show or hide the numbered mouse grid")
    dictation = sub.add_parser("dictation", help="type everything you say")
    dictation.add_argument("mode", choices=["on", "off", "toggle"])
    say = sub.add_parser("say", help="run a command as if it was spoken")
    say.add_argument("text", nargs="+")
    sub.add_parser("status", help="print the daemon state")
    sub.add_parser("stop", help="stop the daemon")
    sub.add_parser("setup", help="allow or revoke microphone and camera access")
    sub.add_parser("doctor", help="check dependencies and permissions")
    sub.add_parser("waybar", help="print the Waybar module JSON")
    args = parser.parse_args(argv)

    if args.cmd == "setup":
        return setup()
    if args.cmd == "doctor":
        from .doctor import report, run_checks

        return report(run_checks())
    if args.cmd == "waybar":
        from .waybar import read_state, status

        print(json.dumps(status(read_state()), ensure_ascii=False), flush=True)
        return 0
    if args.cmd == "say":
        return _send("say", " ".join(args.text))
    if hasattr(args, "mode"):
        return _send(args.cmd, args.mode)
    return _send(args.cmd)


if __name__ == "__main__":
    sys.exit(main())
