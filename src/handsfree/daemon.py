"""The hands-free daemon: owns the voice and gaze workers and runs commands."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from typing import Any

from .config import Config, socket_path, state_file
from .consent import Consent
from .desktop import Desktop
from .ipc import ControlServer

log = logging.getLogger(__name__)


class Daemon:
    def __init__(self, config: Config, desktop: Desktop):
        self.config = config
        self.desktop = desktop
        self._lock = threading.RLock()
        self._stopping = threading.Event()
        self.state: dict[str, Any] = {
            "voice": "off",  # off | push | continuous
            "listening": False,
            "dictation": False,
            "gaze": False,
            "grid": False,
            "last": "",
        }
        self._server = ControlServer(socket_path(), self.handle_request)

    # -- lifecycle -----------------------------------------------------------

    def run(self) -> None:
        self._server.start()
        self._publish()
        log.info("handsfree ready on %s", socket_path())
        self._stopping.wait()
        self._shutdown()

    def stop(self) -> None:
        self._stopping.set()

    def _shutdown(self) -> None:
        self._server.close()
        state_file().unlink(missing_ok=True)
        self._signal_waybar()

    # -- state ---------------------------------------------------------------

    def _set(self, **changes: Any) -> None:
        with self._lock:
            self.state.update(changes)
        self._publish()

    def _publish(self) -> None:
        with self._lock:
            snapshot = dict(self.state)
        path = state_file()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(snapshot))
        os.replace(tmp, path)
        self._signal_waybar()

    def _signal_waybar(self) -> None:
        signal = int(self.config.section("desktop").get("waybar_signal", 0))
        if signal:
            subprocess.run(["pkill", f"-RTMIN+{signal}", "waybar"], check=False, capture_output=True)

    def _notify(self, title: str, body: str = "") -> None:
        if self.config.section("desktop").get("notify", True):
            self.desktop.notify(title, body)

    @staticmethod
    def _consent() -> Consent:
        # Re-read every time so `handsfree-ctl setup` applies without a restart.
        return Consent.load()

    # -- control socket ------------------------------------------------------

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        cmd = str(request.get("cmd", ""))
        handler = getattr(self, f"_cmd_{cmd}", None)
        if handler is None:
            return {"ok": False, "error": f"unknown command: {cmd!r}"}
        result = handler(request.get("arg"))
        if isinstance(result, dict):
            return {"ok": True, **result}
        return {"ok": True, "message": result or ""}

    def _cmd_status(self, _arg: Any) -> dict[str, Any]:
        with self._lock:
            return {"state": dict(self.state)}

    def _cmd_say(self, text: Any) -> str:
        return self.handle_text(str(text or ""))

    def _cmd_stop(self, _arg: Any) -> str:
        self.stop()
        return "stopping"

    # -- speech --------------------------------------------------------------

    def handle_text(self, text: str) -> str:
        text = text.strip()
        if not text:
            return "nothing heard"
        log.info("heard: %s", text)
        self._set(last=text)
        return f"heard: {text}"
