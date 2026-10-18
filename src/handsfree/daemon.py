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
from .intents.actions import Executor
from .intents.apps import LazyAppIndex
from .intents.parser import Parser
from .ipc import ControlServer

log = logging.getLogger(__name__)


class CommandError(Exception):
    """A control request that can't be carried out; reported to the caller."""


class Daemon:
    def __init__(self, config: Config, desktop: Desktop):
        self.config = config
        self.desktop = desktop
        self._lock = threading.RLock()
        self._stopping = threading.Event()
        self.state: dict[str, Any] = {
            "voice": "off",  # off | continuous (push-to-talk works in both)
            "listening": False,
            "dictation": False,
            "gaze": False,
            "grid": False,
            "last": "",
        }
        voice = config.section("voice")
        self.parser = Parser(
            config.commands,
            apps=LazyAppIndex(),
            threshold=float(voice.get("fuzzy_threshold", 82)),
        )
        self.executor = Executor(desktop, self.internal)
        self.voice = self._make_voice_worker(voice)
        self._server = ControlServer(socket_path(), self.handle_request)

    def _make_voice_worker(self, settings: dict[str, Any]):
        from .audio.worker import VoiceWorker

        return VoiceWorker(
            settings,
            on_text=self.handle_text,
            on_listening=lambda on: self._set(listening=on),
            on_error=self._voice_failed,
        )

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
        self.voice.shutdown()
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
        try:
            result = handler(request.get("arg"))
        except CommandError as exc:
            return {"ok": False, "error": str(exc)}
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

    def _cmd_listen(self, _arg: Any) -> str:
        self._require("microphone")
        return self.voice.listen_once()

    def _cmd_voice(self, mode: Any) -> str:
        return self.set_voice(self._toggle(mode, self.state["voice"] == "continuous"))

    def _cmd_dictation(self, mode: Any) -> str:
        return self.set_dictation(self._toggle(mode, self.state["dictation"]))

    @staticmethod
    def _toggle(mode: Any, current: bool) -> bool:
        if mode == "on":
            return True
        if mode == "off":
            return False
        if mode == "toggle":
            return not current
        raise CommandError(f"expected on, off or toggle, not {mode!r}")

    def _require(self, device: str) -> None:
        if not getattr(self._consent(), device):
            self._notify(f"{device.capitalize()} access is off", "Run `handsfree-ctl setup` to allow it.")
            raise CommandError(f"{device} access not granted; run `handsfree-ctl setup`")

    # -- voice ---------------------------------------------------------------

    def set_voice(self, on: bool) -> str:
        if on:
            self._require("microphone")
        self.voice.set_continuous(on)
        self._set(voice="continuous" if on else "off")
        self._notify("Listening continuously" if on else "Stopped listening")
        return "voice on" if on else "voice off"

    def _voice_failed(self, exc: Exception) -> None:
        self._set(voice="off", listening=False)
        self._notify("Voice control stopped", str(exc))

    def handle_text(self, text: str) -> str:
        text = text.strip()
        if not text:
            return "nothing heard"
        log.info("heard: %s", text)
        self._set(last=text)
        intent = self.parser.parse(text)
        if self.state["dictation"] and not (intent and intent.exact and intent.command.get("dictation")):
            return self._dictate(text)
        if intent is None:
            self._notify("Not understood", f"“{text}”")
            return f"not understood: {text}"
        try:
            result = self.executor.execute(intent)
        except Exception as exc:
            log.exception("command failed: %s", text)
            self._notify(f"Failed: “{text}”", str(exc))
            return f"failed: {exc}"
        log.info("-> %s", result)
        self._notify(f"“{text}”", result)
        return result

    def _dictate(self, text: str) -> str:
        if self.config.section("desktop").get("dictation_trailing_space", True):
            text += " "
        try:
            self.desktop.type_text(text)
        except Exception as exc:
            log.exception("dictation failed")
            self._notify("Dictation failed", str(exc))
            return f"failed: {exc}"
        return f'typed "{text}"'

    def set_dictation(self, on: bool) -> str:
        self._set(dictation=on)
        if on:
            hint = "Say \u201cstop dictation\u201d to finish."
            if self.state["voice"] != "continuous":
                hint += " Use push-to-talk or \u201cstart listening\u201d."
            self._notify("Dictation on", hint)
        else:
            self._notify("Dictation off")
        return "dictation on" if on else "dictation off"

    def internal(self, name: str, slots: dict[str, Any]) -> str:
        handler = getattr(self, f"_internal_{name}", None)
        if handler is None:
            raise ValueError(f"unknown internal command {name!r}")
        return handler(slots)

    def _internal_voice_on(self, _slots: dict[str, Any]) -> str:
        return self.set_voice(True)

    def _internal_voice_off(self, _slots: dict[str, Any]) -> str:
        return self.set_voice(False)

    def _internal_dictation_on(self, _slots: dict[str, Any]) -> str:
        return self.set_dictation(True)

    def _internal_dictation_off(self, _slots: dict[str, Any]) -> str:
        return self.set_dictation(False)
