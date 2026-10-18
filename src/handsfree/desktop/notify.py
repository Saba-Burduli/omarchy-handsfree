"""Desktop notifications via notify-send (shown by mako on Omarchy)."""

from __future__ import annotations

import logging
import subprocess

log = logging.getLogger(__name__)


class Notifier:
    """Reuses one notification so rapid feedback doesn't stack up."""

    def __init__(self) -> None:
        self._id: str | None = None

    def show(self, title: str, body: str = "") -> None:
        args = ["notify-send", "--app-name=Hands-free", "--urgency=low", "--expire-time=2500", "--print-id"]
        if self._id:
            args.append(f"--replace-id={self._id}")
        try:
            out = subprocess.run(args + [title, body], capture_output=True, text=True, timeout=3)
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.warning("notify-send failed: %s", exc)
            return
        self._id = out.stdout.strip() or None
