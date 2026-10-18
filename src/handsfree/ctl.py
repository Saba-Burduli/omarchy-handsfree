"""`handsfree-ctl`: control the daemon (bind these to Hyprland keys)."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .config import socket_path
from .ipc import request


def _send(cmd: str, arg: Any = None) -> int:
    try:
        response = request(socket_path(), {"cmd": cmd, "arg": arg})
    except (FileNotFoundError, ConnectionRefusedError):
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="handsfree-ctl", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("listen", help="push-to-talk: listen for one command (press again to stop early)")
    voice = sub.add_parser("voice", help="continuous listening")
    voice.add_argument("mode", choices=["on", "off", "toggle"])
    gaze = sub.add_parser("gaze", help="eye tracking moves the pointer")
    gaze.add_argument("mode", choices=["on", "off", "toggle"])
    sub.add_parser("calibrate", help="calibrate eye tracking for the focused monitor")
    dictation = sub.add_parser("dictation", help="type everything you say")
    dictation.add_argument("mode", choices=["on", "off", "toggle"])
    say = sub.add_parser("say", help="run a command as if it was spoken")
    say.add_argument("text", nargs="+")
    sub.add_parser("status", help="print the daemon state")
    sub.add_parser("stop", help="stop the daemon")
    args = parser.parse_args(argv)

    if args.cmd == "say":
        return _send("say", " ".join(args.text))
    if hasattr(args, "mode"):
        return _send(args.cmd, args.mode)
    return _send(args.cmd)


if __name__ == "__main__":
    sys.exit(main())
